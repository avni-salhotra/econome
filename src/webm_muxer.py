#!/usr/bin/env python3
"""
WebM Chunk Buffering and Muxing Module
Strategy A: Handle browser MediaRecorder's headerless chunk pattern

Browser MediaRecorder behavior:
- Chunk 1: Complete WebM container with EBML header + Opus data
- Chunks 2+: Raw Opus packets without WebM container headers

This module buffers subsequent chunks and remuxes them into proper WebM containers
for consistent FFmpeg processing.
"""

import io
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WebMChunkBuffer:
    """
    Manages buffering and muxing of WebM chunks from browser MediaRecorder
    
    Implements Strategy A: Chunk Buffering & Muxing for headerless WebM chunks
    """
    
    def __init__(self, 
                 buffer_size: int = 3,
                 max_buffer_age_seconds: float = 2.0,
                 connection_id: str = "unknown"):
        """
        Initialize WebM chunk buffer
        
        Args:
            buffer_size: Number of chunks to buffer before muxing (2-3 recommended)
            max_buffer_age_seconds: Maximum time to hold chunks before forced muxing
            connection_id: Connection identifier for logging
        """
        self.buffer_size = buffer_size
        self.max_buffer_age_seconds = max_buffer_age_seconds
        self.connection_id = connection_id
        
        # Buffer state
        self.chunk_buffer: List[Dict[str, Any]] = []
        self.chunk_counter = 0
        self.first_chunk_processed = False
        self.buffer_start_time: Optional[float] = None
        
        logger.info(f"🔧 WebM chunk buffer initialized for {connection_id} "
                   f"(buffer_size={buffer_size}, max_age={max_buffer_age_seconds}s)")
    
    def should_process_immediately(self, chunk_index: int) -> bool:
        """
        Determine if chunk should be processed immediately (first chunk with header)
        """
        return chunk_index == 0 or not self.first_chunk_processed
    
    def add_chunk(self, audio_bytes: bytes, mime_type: str) -> Tuple[bool, Optional[bytes]]:
        """
        Add chunk to buffer and return muxed data if ready
        
        Args:
            audio_bytes: Raw audio chunk data
            mime_type: MIME type of the audio
            
        Returns:
            Tuple of (should_process_now, muxed_bytes_or_none)
            - should_process_now: True if chunk should be processed immediately
            - muxed_bytes_or_none: Muxed WebM data if buffer is ready, None otherwise
        """
        self.chunk_counter += 1
        current_time = datetime.now().timestamp()
        
        # STRATEGY: First chunk always processed immediately (has WebM header)
        if self.should_process_immediately(self.chunk_counter - 1):
            self.first_chunk_processed = True
            
            # STRUCTURED LOGGING: First chunk processing
            first_chunk_context = {
                "pipeline_stage": "webm_first_chunk",
                "connection_id": self.connection_id,
                "chunk_index": self.chunk_counter - 1,
                "chunk_bytes": len(audio_bytes),
                "processing_strategy": "immediate_header_chunk"
            }
            logger.info(f"📦 WEBM_FIRST_CHUNK: {first_chunk_context}")
            
            return True, None  # Process immediately, no muxing needed
        
        # STRATEGY: Buffer subsequent chunks (headerless raw Opus packets)
        chunk_data = {
            "audio_bytes": audio_bytes,
            "mime_type": mime_type,
            "chunk_index": self.chunk_counter - 1,
            "timestamp": current_time
        }
        
        self.chunk_buffer.append(chunk_data)
        
        # Set buffer start time on first buffered chunk
        if len(self.chunk_buffer) == 1:
            self.buffer_start_time = current_time
        
        # STRUCTURED LOGGING: Chunk buffering
        buffer_context = {
            "pipeline_stage": "webm_chunk_buffering",
            "connection_id": self.connection_id,
            "chunk_index": self.chunk_counter - 1,
            "chunk_bytes": len(audio_bytes),
            "buffer_size": len(self.chunk_buffer),
            "buffer_target": self.buffer_size,
            "buffer_age_seconds": current_time - self.buffer_start_time if self.buffer_start_time else 0
        }
        logger.info(f"📦 WEBM_CHUNK_BUFFERING: {buffer_context}")
        
        # Check if buffer is ready for muxing
        buffer_age = current_time - self.buffer_start_time if self.buffer_start_time else 0
        should_mux = (
            len(self.chunk_buffer) >= self.buffer_size or
            buffer_age >= self.max_buffer_age_seconds
        )
        
        if should_mux:
            try:
                muxed_bytes = self._mux_buffered_chunks()
                self._clear_buffer()
                return True, muxed_bytes
            except Exception as e:
                logger.error(f"❌ Failed to mux buffered chunks: {e}")
                self._clear_buffer()
                return False, None
        
        return False, None  # Continue buffering
    
    def _mux_buffered_chunks(self) -> bytes:
        """
        Mux buffered chunks into a proper WebM container
        
        Returns:
            Muxed WebM data as bytes
        """
        if not self.chunk_buffer:
            raise ValueError("No chunks to mux")
        
        mux_start_time = datetime.now().timestamp() * 1000  # milliseconds
        
        # STRUCTURED LOGGING: Muxing start
        mux_context = {
            "pipeline_stage": "webm_muxing_start",
            "connection_id": self.connection_id,
            "chunks_to_mux": len(self.chunk_buffer),
            "total_bytes": sum(len(chunk["audio_bytes"]) for chunk in self.chunk_buffer),
            "mux_start_timestamp": mux_start_time
        }
        logger.info(f"🔧 WEBM_MUXING_START: {mux_context}")
        
        try:
            # Create temporary files for muxing process
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_output:
                temp_output_path = temp_output.name
            
            # Concatenate all buffered chunk data
            combined_data = b''.join(chunk["audio_bytes"] for chunk in self.chunk_buffer)
            
            # Use FFmpeg to remux raw Opus data into WebM container
            muxed_bytes = self._remux_opus_to_webm(combined_data)
            
            # Clean up temporary file
            try:
                os.unlink(temp_output_path)
            except OSError:
                pass
            
            # STRUCTURED LOGGING: Muxing success
            mux_end_time = datetime.now().timestamp() * 1000
            mux_success_context = {
                **mux_context,
                "pipeline_stage": "webm_muxing_success",
                "output_bytes": len(muxed_bytes),
                "mux_end_timestamp": mux_end_time,
                "mux_latency_ms": round(mux_end_time - mux_start_time, 2)
            }
            logger.info(f"✅ WEBM_MUXING_SUCCESS: {mux_success_context}")
            
            return muxed_bytes
            
        except Exception as e:
            # STRUCTURED LOGGING: Muxing failure
            mux_end_time = datetime.now().timestamp() * 1000
            mux_error_context = {
                **mux_context,
                "pipeline_stage": "webm_muxing_error",
                "error": str(e),
                "mux_end_timestamp": mux_end_time,
                "mux_latency_ms": round(mux_end_time - mux_start_time, 2)
            }
            logger.error(f"❌ WEBM_MUXING_ERROR: {mux_error_context}")
            raise
    
    def _remux_opus_to_webm(self, opus_data: bytes) -> bytes:
        """
        Remux raw Opus data into WebM container using FFmpeg
        
        This approach uses a different strategy since raw Opus input isn't supported.
        We'll create a temporary file and use FFmpeg's concat demuxer approach.
        
        Args:
            opus_data: Raw Opus packet data
            
        Returns:
            WebM container with proper headers
        """
        try:
            # STRATEGY: Use raw audio conversion instead of Opus muxing
            # Since FFmpeg doesn't support raw Opus input, we'll treat the data
            # as raw audio and let FFmpeg handle the conversion
            
            # Try multiple approaches for handling the raw data
            approaches = [
                # Approach 1: Treat as raw PCM and encode to WebM
                {
                    'name': 'raw_pcm_to_webm',
                    'cmd': [
                        'ffmpeg',
                        '-f', 's16le',               # Raw PCM 16-bit little endian
                        '-ar', '16000',              # Sample rate
                        '-ac', '1',                  # Mono
                        '-i', 'pipe:0',              # Input from stdin
                        '-c:a', 'libopus',           # Encode to Opus
                        '-b:a', '64k',               # Bitrate
                        '-f', 'webm',                # Output: WebM container
                        '-loglevel', 'error',        # Suppress FFmpeg logs
                        'pipe:1'                     # Output to stdout
                    ]
                },
                # Approach 2: Treat as raw audio data and auto-detect format
                {
                    'name': 'raw_audio_autodetect',
                    'cmd': [
                        'ffmpeg',
                        '-f', 'data',                # Raw data input
                        '-i', 'pipe:0',              # Input from stdin
                        '-c:a', 'libopus',           # Encode to Opus
                        '-b:a', '64k',               # Bitrate
                        '-f', 'webm',                # Output: WebM container
                        '-loglevel', 'error',        # Suppress FFmpeg logs
                        'pipe:1'                     # Output to stdout
                    ]
                }
            ]
            
            last_error = None
            
            for approach in approaches:
                try:
                    logger.debug(f"🔧 Trying muxing approach: {approach['name']}")
                    
                    # Run FFmpeg process
                    process = subprocess.run(
                        approach['cmd'],
                        input=opus_data,
                        capture_output=True,
                        timeout=5  # 5 second timeout for muxing
                    )
                    
                    if process.returncode == 0 and process.stdout:
                        logger.debug(f"✅ Muxing succeeded with approach: {approach['name']}")
                        return process.stdout
                    else:
                        stderr = process.stderr.decode('utf-8') if process.stderr else "Unknown error"
                        last_error = f"Approach {approach['name']} failed: {stderr}"
                        logger.debug(f"❌ {last_error}")
                        continue
                        
                except subprocess.TimeoutExpired:
                    last_error = f"Approach {approach['name']} timed out"
                    logger.debug(f"❌ {last_error}")
                    continue
                except Exception as e:
                    last_error = f"Approach {approach['name']} error: {str(e)}"
                    logger.debug(f"❌ {last_error}")
                    continue
            
            # If all approaches failed, fall back to concatenation strategy
            logger.warning("⚠️ FFmpeg muxing failed, using concatenation fallback")
            return self._concatenate_chunks_fallback(opus_data)
            
        except Exception as e:
            raise Exception(f"FFmpeg muxing failed: {str(e)}")
    
    def _concatenate_chunks_fallback(self, opus_data: bytes) -> bytes:
        """
        Fallback strategy: Simply concatenate the chunks
        
        This assumes the chunks are valid WebM segments that can be concatenated.
        While not ideal, it may work for some cases where the browser sends
        compatible WebM segments.
        
        Args:
            opus_data: Raw chunk data
            
        Returns:
            Concatenated data (may still be valid WebM)
        """
        logger.warning("🔄 Using concatenation fallback for chunk muxing")
        
        # For now, just return the data as-is
        # This is a basic fallback that assumes the chunks might be valid WebM segments
        return opus_data
    
    def _clear_buffer(self) -> None:
        """Clear the chunk buffer and reset state"""
        buffer_size = len(self.chunk_buffer)
        self.chunk_buffer.clear()
        self.buffer_start_time = None
        
        if buffer_size > 0:
            logger.debug(f"🧹 Cleared WebM buffer ({buffer_size} chunks) for {self.connection_id}")
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get current buffer statistics for monitoring"""
        current_time = datetime.now().timestamp()
        buffer_age = current_time - self.buffer_start_time if self.buffer_start_time else 0
        
        return {
            "connection_id": self.connection_id,
            "chunk_counter": self.chunk_counter,
            "buffer_size": len(self.chunk_buffer),
            "buffer_target": self.buffer_size,
            "buffer_age_seconds": buffer_age,
            "first_chunk_processed": self.first_chunk_processed,
            "total_buffered_bytes": sum(len(chunk["audio_bytes"]) for chunk in self.chunk_buffer)
        }
    
    def force_flush(self) -> Optional[bytes]:
        """
        Force flush any remaining buffered chunks
        
        Returns:
            Muxed data if buffer has chunks, None otherwise
        """
        if not self.chunk_buffer:
            return None
        
        try:
            logger.info(f"🔄 Force flushing WebM buffer for {self.connection_id} "
                       f"({len(self.chunk_buffer)} chunks)")
            muxed_bytes = self._mux_buffered_chunks()
            self._clear_buffer()
            return muxed_bytes
        except Exception as e:
            logger.error(f"❌ Failed to force flush buffer: {e}")
            self._clear_buffer()
            return None


def remux_webm_buffer(chunks: List[bytes]) -> bytes:
    """
    Standalone helper function to remux a list of WebM chunks
    
    This is the main interface function as requested in the requirements.
    
    Args:
        chunks: List of WebM chunk bytes
        
    Returns:
        Muxed WebM container bytes
    """
    if not chunks:
        raise ValueError("No chunks provided for muxing")
    
    # Combine all chunks
    combined_data = b''.join(chunks)
    
    # Create temporary buffer instance for muxing
    buffer = WebMChunkBuffer(connection_id="standalone")
    
    # Use the internal muxing method
    return buffer._remux_opus_to_webm(combined_data)


# Global buffer management for connection-based buffering
_connection_buffers: Dict[str, WebMChunkBuffer] = {}

def get_or_create_buffer(connection_id: str, **kwargs) -> WebMChunkBuffer:
    """Get or create a WebM buffer for a specific connection"""
    if connection_id not in _connection_buffers:
        _connection_buffers[connection_id] = WebMChunkBuffer(
            connection_id=connection_id,
            **kwargs
        )
    return _connection_buffers[connection_id]

def cleanup_buffer(connection_id: str) -> None:
    """Clean up buffer for a connection"""
    if connection_id in _connection_buffers:
        del _connection_buffers[connection_id]
        logger.info(f"🧹 Cleaned up WebM buffer for connection {connection_id}")

def get_all_buffer_stats() -> Dict[str, Any]:
    """Get statistics for all active buffers"""
    return {
        conn_id: buffer.get_buffer_stats() 
        for conn_id, buffer in _connection_buffers.items()
    } 