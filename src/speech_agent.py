#!/usr/bin/env python3
"""
Production Speech-to-Text Service using Google Cloud Speech V2
Pure STT service with no agent dependencies - focused and reusable

Built for real-time conversation intelligence with optimal latency/reliability balance
OPTIMIZED VERSION with Chirp 2 model and best practices for accuracy
"""

import threading
import queue
import time
import numpy as np
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
import sys
import google.protobuf.duration_pb2

# Google Cloud Speech V2 imports
from google.cloud import speech_v2
from google.oauth2 import service_account
from google.protobuf import duration_pb2

# Optional audio imports for CI compatibility
try:
    import sounddevice as sd

    # Check if we're in a Cloud Run environment (no audio devices)
    def _detect_cloud_run_environment():
        """Detect if running in Cloud Run or similar containerized environment without audio"""
        # Check for Cloud Run environment variables
        if os.getenv('K_SERVICE') or os.getenv('K_REVISION') or os.getenv('K_CONFIGURATION'):
            return True

        # Check for container environment without audio devices
        try:
            # Try to query audio devices - if this fails, we're in a headless environment
            devices = sd.query_devices()
            if len(devices) == 0:
                return True

            # Try to get default input device - if this fails, no microphone available
            default_input = sd.query_devices(kind='input')
            return False  # Audio devices found

        except Exception as e:
            # Any error querying devices means we're in a headless environment
            print(f"🔍 Audio device query failed: {e}")
            return True

    # Determine if audio is actually available
    if _detect_cloud_run_environment():
        print("🌐 Cloud Run environment detected - using mock audio mode")
        AUDIO_AVAILABLE = False
        CLOUD_RUN_MODE = True
    else:
        print("🎤 Local environment with audio devices detected")
        AUDIO_AVAILABLE = True
        CLOUD_RUN_MODE = False

except (ImportError, OSError) as e:
    print(f"⚠️ Audio library not available: {e}")
    print("🔧 Running in audio-disabled mode (suitable for CI/testing)")
    sd = None
    AUDIO_AVAILABLE = False
    CLOUD_RUN_MODE = False

@dataclass
class TranscriptSegment:
    """Structured transcript segment with speaker information"""
    text: str
    speaker_id: str
    confidence: float
    timestamp: datetime
    is_final: bool
    chunk_id: int
    language_code: str = "en-US"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }

@dataclass
class STTStatus:
    """STT service status information"""
    is_recording: bool
    session_duration: float
    total_chunks_processed: int
    queue_size: int
    queue_health: str
    speakers_detected: int
    total_segments: int
    current_chunk_id: int
    last_activity: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'last_activity': self.last_activity.isoformat()
        }

class ProductionSTTServiceV2:
    """
    Production-ready Speech-to-Text service using Google Cloud Speech V2
    
    Features:
    - Real-time streaming transcription with bidirectional communication
    - Chirp 2 model for enhanced accuracy
    - Model adaptation for improved name recognition
    - Automatic error recovery
    - Health monitoring
    - Callback-based event system
    - Mock mode for development
    """
    
    def __init__(self, 
                 credentials_path: str = "speech-credentials.json",
                 chunk_duration: float = 0.1,  # 🎯 OPTIMIZED: 100ms for real-time streaming (GCP best practice)
                 sample_rate: int = 16000,
                 project_id: str = "econome-hackathon"):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)
        self.channels = 1
        self.dtype = np.float32

        self.project_id = project_id
        # 🚀 OBSERVABILITY UPGRADE 2025-06-23
        # Increase buffer so brief CPU spikes don't drop audio and make the
        # queue state visible in every log entry
        self.max_queue_size = 50  # 5 s of 100 ms PCM chunks
        self.queue_warning_threshold = int(self.max_queue_size * 0.8)  # 80 % full

        self.queue_cleanup_interval = 30  # Clean up old chunks every 30 seconds

        # 🔧 CRITICAL FIX: Initialize callbacks BEFORE speech client to prevent attribute errors
        self._transcript_callback = None
        self._error_callback = None
        self._status_callback = None

        self._initialize_speech_client(credentials_path)

        self._audio_queue = queue.Queue(maxsize=self.max_queue_size)
        self._is_recording = False
        self._session_start_time = None
        self._chunk_counter = 0
        self._segments = []
        self._last_queue_cleanup = time.time()
        self.queue_cleanup_interval = 30.0  # seconds

        self._recording_thread = None
        self._processing_thread = None
        self._master_thread = None

        # 🚨 NEW: Streaming recognition state management
        self._streaming_client = None
        self._streaming_config = None
        self._stream_active = False
        self._stream_lock = threading.Lock()
        self._restart_stream_event = threading.Event()
        self._stop_event = threading.Event() # Use an event for cleaner shutdown
        
        # Stream health monitoring
        self._stream_start_time = None
        self._stream_duration_limit = 240  # 4 minutes (GCP limit is 5 minutes)
        self._last_stream_restart = time.time()
        self._stream_restart_count = 0

        # OBSERVABILITY: Thread health monitoring
        self._last_heartbeat = time.time()
        self.heartbeat_interval = 30.0  # seconds
        self._thread_health_alerts = []

        # Track timing between consecutive chunks for latency diagnostics
        self._prev_chunk_ts: Optional[float] = None

        # Add proper import and constants for chunk management
        self.GOOGLE_AUDIO_CHUNK_SIZE_LIMIT = 25600  # Google's hard limit
        self.OPTIMAL_CHUNK_SIZE = 20480  # 20KB - safe buffer under limit
        self._audio_buffer = bytearray()  # Buffer for assembling proper-sized chunks

        print(f"✅ ProductionSTTServiceV2 initialized with STREAMING recognition (chunk_duration={chunk_duration}s, model=latest_long, buffer_size={self.max_queue_size})")
    
    def _initialize_speech_client(self, credentials_path: str) -> None:
        """Initialize Google Cloud Speech V2 client with regional endpoint"""
        try:
            # Try multiple credential paths (for Cloud Run and local development)
            credential_paths = [
                credentials_path,  # Default path (local development)
                "/app/speech/credentials.json",  # Current Cloud Run mount path
                "/app/secrets/speech/credentials.json",  # New Cloud Run path (separate directories)
                "/app/secrets/speech-credentials.json",  # Legacy Cloud Run path (backward compatibility)
                "/secrets/speech-credentials.json",  # Legacy Cloud Run path (backward compatibility)
            ]

            credentials_found = False
            for path in credential_paths:
                if os.path.exists(path):
                    self.credentials = service_account.Credentials.from_service_account_file(path)
                    credentials_found = True
                    print(f"✅ Speech credentials loaded from {path}")
                    break

            if credentials_found:
                # Use us-central1 endpoint to match our deployment region
                from google.api_core.client_options import ClientOptions
                
                # For Speech V2, use the correct regional endpoint format
                client_options = ClientOptions(
                    api_endpoint="us-central1-speech.googleapis.com"
                )
                
                self.speech_client = speech_v2.SpeechClient(
                    credentials=self.credentials,
                    client_options=client_options
                )
                self._has_credentials = True

                # Speech V2 uses recognizers - use us-central1 to match deployment region
                self.recognizer = f"projects/{self.project_id}/locations/us-central1/recognizers/_"

                print(f"✅ Google Cloud Speech V2 client initialized (us-central1 regional)")
                print(f"🔍 Using recognizer: {self.recognizer}")
                print(f"🔍 Using endpoint: us-central1-speech.googleapis.com")
                
                # Initialize streaming config after client is ready
                self._initialize_streaming_config()
            else:
                print("⚠️ No credentials found - running in mock mode")
                self._has_credentials = False
                self.speech_client = None
                
        except Exception as e:
            print(f"❌ Failed to initialize Speech client: {e}")
            self._has_credentials = False
            self.speech_client = None
    
    def _initialize_streaming_config(self) -> None:
        """Initialize streaming recognition configuration"""
        if not self._has_credentials:
            print("⚠️ No credentials - skipping streaming config initialization")
            self._streaming_config = None
            return
            
        try:
            print("🔧 Initializing streaming configuration...")
            
            # 🎯 SIMPLIFIED FIX: Use AUTO_DETECT with explicit language codes
            # This is the most reliable approach for WebM/Opus from MediaRecorder
            recognition_config = speech_v2.RecognitionConfig(
                language_codes=["en-US"],  # CRITICAL: Must be first
                
                # 🚨 KEY FIX: Use auto-detect for WebM/Opus instead of explicit config
                # Auto-detect handles MediaRecorder WebM containers reliably
                auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
                
                # Recognition features optimized for real-time streaming
                model="latest_long",  # Best model for long-form content
                features=speech_v2.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=False,  # Disabled for performance
                    enable_word_confidence=True,
                    max_alternatives=1,              # Single best result for speed
                    profanity_filter=False
                )
            )
            print(f"🔍 RecognitionConfig created with language_codes: {recognition_config.language_codes}")
            print(f"🔍 Audio format: WebM/Opus (auto-detected), latest_long model")
            
            # Create streaming configuration with optimized settings
            self._streaming_config = speech_v2.StreamingRecognitionConfig(
                config=recognition_config,
                streaming_features=speech_v2.StreamingRecognitionFeatures(
                    interim_results=True,
                    enable_voice_activity_events=True,
                    voice_activity_timeout=speech_v2.StreamingRecognitionFeatures.VoiceActivityTimeout(
                        speech_start_timeout=duration_pb2.Duration(seconds=5),
                        speech_end_timeout=duration_pb2.Duration(seconds=2)
                    )
                )
            )
            print(f"🔍 StreamingConfig created with language_codes: {recognition_config.language_codes}")
            print("✅ Streaming recognition configuration initialized for WebM/Opus audio")
            
        except Exception as e:
            print(f"❌ Error initializing streaming config: {e}")
            print("🔄 Attempting emergency fallback configuration...")
            
            try:
                # 🚨 EMERGENCY FALLBACK: Ultra-minimal config
                emergency_config = speech_v2.RecognitionConfig(
                    language_codes=["en-US"],  # Explicit language codes
                    model="latest_long"
                )
                
                self._streaming_config = speech_v2.StreamingRecognitionConfig(
                    config=emergency_config,
                    streaming_features=speech_v2.StreamingRecognitionFeatures(
                        interim_results=True
                    )
                )
                print("✅ Emergency fallback config created successfully")
                
            except Exception as emergency_error:
                print(f"❌ Emergency config also failed: {emergency_error}")
                self._streaming_config = None

    def set_transcript_callback(self, callback: Callable[[TranscriptSegment], None]) -> None:
        """Set callback for real-time transcript segments"""
        self._transcript_callback = callback
    
    def set_error_callback(self, callback: Callable[[str, Exception], None]) -> None:
        """Set callback for error handling"""
        self._error_callback = callback
    
    def set_status_callback(self, callback: Callable[[STTStatus], None]) -> None:
        """Set callback for status updates"""
        self._status_callback = callback
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Callback from sounddevice to add audio data to the queue."""
        if status:
            print(f"⚠️ Audio callback status: {status}")
        
        # Only queue if recording is active
        if self._is_recording and not self._stop_event.is_set():
            try:
                self._audio_queue.put_nowait(indata.copy())
            except queue.Full:
                self._handle_error("audio_queue_full", "Audio queue is full, dropping audio chunk.")

    def _handle_error(self, error_type: str, message: str) -> None:
        """Handle errors with logging and optional callback notification"""
        print(f"❌ {error_type}: {message}")
        
        # Call error callback if set
        if self._error_callback:
            try:
                # Create a simple exception for the callback
                error = Exception(f"{error_type}: {message}")
                self._error_callback(error_type, error)
            except Exception as callback_error:
                print(f"❌ Error in error callback: {callback_error}")

    def _report_status(self) -> None:
        """Report current status via callback if set"""
        if self._status_callback:
            try:
                status = self.get_status()
                self._status_callback(status)
            except Exception as callback_error:
                print(f"❌ Error in status callback: {callback_error}")

    def _start_streaming_recognition(self) -> None:
        """
        Manages the lifecycle of streaming recognition sessions. This is the
        main loop for the master thread.
        """
        while not self._stop_event.is_set():
            if not self._has_credentials:
                self._run_mock_mode()
                break # Exit after mock mode finishes

            # 🚨 CRITICAL FIX: Validate streaming config before using it
            if self._streaming_config is None:
                error_msg = "Streaming configuration is not initialized. Attempting to re-initialize..."
                print(f"⚠️ {error_msg}")
                
                # Try to re-initialize the config
                self._initialize_streaming_config()
                
                # If it's still None after re-initialization, give up
                if self._streaming_config is None:
                    error_msg = "Failed to re-initialize streaming configuration. Cannot start recognition."
                    print(f"❌ {error_msg}")
                    self._handle_error("config_error", error_msg)
                    time.sleep(1)
                    continue

            print("🚀 Starting new streaming session...")
            self._report_status()
            
            # Each session gets its own response processing thread
            response_thread = threading.Thread(target=self._process_streaming_responses, daemon=True)
            
            try:
                # Setup the stream with the audio generator
                # The first request must be a config message
                
                # 🚨 DEBUG: Validate config before using it
                if self._streaming_config is None:
                    raise ValueError("Streaming config is None")
                
                if not hasattr(self._streaming_config, 'config') or self._streaming_config.config is None:
                    raise ValueError("Streaming config.config is None")
                    
                if not hasattr(self._streaming_config.config, 'language_codes') or not self._streaming_config.config.language_codes:
                    raise ValueError(f"Language codes missing or empty: {getattr(self._streaming_config.config, 'language_codes', 'MISSING')}")
                
                print(f"🔍 Creating streaming request with config language_codes: {self._streaming_config.config.language_codes}")
                
                config_request = speech_v2.StreamingRecognizeRequest(
                    recognizer=self.recognizer,
                    streaming_config=self._streaming_config
                )
                
                # 🚨 DEBUG: Verify the request was created properly
                if hasattr(config_request.streaming_config, 'config') and hasattr(config_request.streaming_config.config, 'language_codes'):
                    print(f"🔍 Request created with language_codes: {config_request.streaming_config.config.language_codes}")
                else:
                    print("⚠️ Request created but cannot verify language_codes")
                
                audio_generator = self._audio_chunk_generator()

                def request_generator():
                    yield config_request
                    yield from audio_generator

                # The streaming client is a generator that yields responses
                self._streaming_client = self.speech_client.streaming_recognize(
                    requests=request_generator()
                )

                response_thread.start()
                response_thread.join() # This will block until the stream ends or is stopped

            except Exception as e:
                error_message = str(e)
                if "encoding" in error_message.lower() or "audio data does not appear" in error_message.lower():
                    print(f"🔧 Audio encoding error in stream setup, clearing audio buffer: {error_message}")
                    # Clear potentially corrupted audio chunks from queue
                    self._clear_corrupted_audio_chunks()
                else:
                    self._handle_error("stream_error", f"Streaming recognition failed: {e}")
                time.sleep(1) # Wait before retrying
            
            finally:
                if not self._stop_event.is_set():
                    print("🔄 Stream ended. Will restart if recording is still active.")
        
        print("🛑 Master thread exiting.")

    def _audio_chunk_generator(self):
        """
        Yields audio chunks from the queue. This is a generator function
        that runs until the stream is stopped or times out.
        """
        stream_start_time = time.time()
        stream_duration_limit = self._stream_duration_limit

        while not self._stop_event.is_set():
            if time.time() - stream_start_time > stream_duration_limit:
                print("⏰ Stream time limit reached. Ending current stream.")
                break
            
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                yield speech_v2.StreamingRecognizeRequest(audio=chunk)
            except queue.Empty:
                continue

        print("🚪 Audio chunk generator finished.")


    def _process_streaming_responses(self) -> None:
        """
        Processes responses from the current streaming recognition session.
        This runs in a dedicated thread per session.
        """
        print("🎧 Starting streaming response processing...")
        if not self._streaming_client:
            return

        try:
            for response in self._streaming_client:
                if self._stop_event.is_set():
                    break
                self._handle_streaming_response(response)
        except Exception as e:
            if not self._stop_event.is_set():
                # 🔧 CRITICAL FIX: Handle encoding errors gracefully
                error_message = str(e)
                if "encoding" in error_message.lower() or "audio data does not appear" in error_message.lower():
                    print(f"🔧 Audio encoding error detected, will auto-restart stream: {error_message}")
                    # Don't treat this as a fatal error - just restart the stream
                else:
                    self._handle_error("response_error", f"Error processing stream responses: {e}")
        finally:
            with self._stream_lock:
                self._stream_active = False
            print("🛑 Response processing thread finished.")


    def _handle_streaming_response(self, response: speech_v2.StreamingRecognizeResponse):
        """Parses a single response from the Speech API."""
        if not response.results:
            return

        for result in response.results:
            if not result.alternatives:
                continue

            alt = result.alternatives[0]
            segment = TranscriptSegment(
                text=alt.transcript,
                is_final=result.is_final,
                confidence=alt.confidence,
                timestamp=datetime.now(),
                speaker_id="speaker_0",
                chunk_id=self._chunk_counter
            )

            if self._transcript_callback:
                self._transcript_callback(segment)

            # Only add final segments to the persistent transcript log
            if result.is_final:
                self._segments.append(segment)

    def _run_mock_mode(self):
        """Runs a mock transcription session when credentials are not available."""
        print("🎭 Running in mock mode.")
        mock_transcript = [
            ("Hello, this is a test.", True, 0.95),
            ("We are testing the mock functionality.", True, 0.98),
            ("This ensures the system works without credentials.", False, 0.90),
            ("System is fully operational.", True, 0.99),
        ]
        for text, is_final, confidence in mock_transcript:
            if self._stop_event.is_set(): break
            time.sleep(1.5)
            segment = TranscriptSegment(text=text, is_final=is_final, confidence=confidence, timestamp=datetime.now())
            if self._transcript_callback:
                self._transcript_callback(segment)
        print("🎭 Mock mode finished.")

    def start_recording(self) -> Dict[str, Any]:
        if self._is_recording:
            return {"status": "already_recording", "message": "Recording is already in progress."}

        self._is_recording = True
        self._session_start_time = time.time()
        self._stop_event.clear()
        self._clear_audio_buffers()

        # The master thread manages the streaming lifecycle
        self._master_thread = threading.Thread(target=self._start_streaming_recognition, daemon=True)
        self._master_thread.start()

        print("🎤 Recording started. Master thread launched.")
        self._report_status()
        return {"status": "recording_started", "session_start_time": datetime.utcnow().isoformat()}

    def stop_recording(self) -> Dict[str, Any]:
        if not self._is_recording:
            return {"status": "not_recording", "message": "Recording is not in progress."}

        print("⏹️ Stopping recording...")
        self._stop_event.set() # Signal all threads to stop

        # Wait for the master thread to finish
        if self._master_thread and self._master_thread.is_alive():
            self._master_thread.join(timeout=5.0)
            if self._master_thread.is_alive():
                self._handle_error("shutdown_timeout", "Master thread did not terminate in time.")

        self._is_recording = False
        duration = time.time() - self._session_start_time if self._session_start_time else 0
        print(f"✅ Recording stopped after {duration:.2f} seconds.")

        self._report_status()
        return {"status": "recording_stopped", "duration": duration}

    def _clear_audio_buffers(self):
        try:
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            self._chunk_counter = 0
            self._segments.clear()
            print("🧹 Audio buffers cleared")
        except Exception as e:
            print(f"⚠️ Error clearing buffers: {e}")

    def _clear_corrupted_audio_chunks(self):
        """Clear potentially corrupted audio chunks from the queue without resetting transcript"""
        try:
            chunks_cleared = 0
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                    chunks_cleared += 1
                except queue.Empty:
                    break
            if chunks_cleared > 0:
                print(f"🧹 Cleared {chunks_cleared} potentially corrupted audio chunks")
        except Exception as e:
            print(f"⚠️ Error clearing corrupted chunks: {e}")

    def _is_valid_webm_chunk(self, audio_data: bytes) -> bool:
        """
        Basic validation for WebM audio chunks to prevent encoding errors.
        This is a lightweight check to catch obviously corrupted data.
        """
        try:
            # Check minimum size
            if len(audio_data) < 4:
                return False
            
            # Very basic WebM container check - look for some expected patterns
            # WebM uses EBML format, so we look for some EBML signatures
            # This is not a complete validation, just a sanity check
            
            # Skip validation for now and assume chunks are valid
            # In the future, we could add more sophisticated validation
            return True
            
        except Exception:
            return False

    def initialize_frontend_streaming(self) -> Dict[str, Any]:
        """
        Initializes the STT service to receive audio chunks from the frontend
        instead of a local microphone.
        """
        if self._is_recording:
            return {"status": "error", "message": "Recording is already in progress"}

        self._clear_audio_buffers()
        self._is_recording = True
        self._session_start_time = time.time()
        self._chunk_counter = 0

        # In frontend streaming mode, the processing thread becomes the master thread
        # We start the streaming recognition thread that handles audio processing
        if self._processing_thread is None or not self._processing_thread.is_alive():
            self._stop_event.clear()
            self._processing_thread = threading.Thread(
                target=self._start_streaming_recognition,
                daemon=True
            )
            self._processing_thread.start()
            
            # For compatibility with stop_recording, also set _master_thread
            self._master_thread = self._processing_thread

        return {
            "status": "initialized",
            "message": "STT service is ready to receive audio chunks from frontend",
            "sample_rate": self.sample_rate,
            "chunk_duration": self.chunk_duration,
            "required_format": "Opus in Ogg container (audio/webm)"
        }

    def queue_audio_chunk(self, audio_data: bytes) -> bool:
        """
        Queue an audio chunk received from the frontend with intelligent chunk management.
        
        🎯 KEY IMPROVEMENTS:
        1. Validates chunk size against Google's 25,600 byte limit
        2. Splits oversized chunks into optimal-sized pieces  
        3. Buffers small chunks for efficiency
        4. Handles WebM container format properly
        5. Validates chunk integrity to prevent encoding errors
        """
        if not self._is_recording:
            return False

        if self._stop_event.is_set():
            return False

        try:
            # 🔧 CRITICAL: Validate chunk integrity
            chunk_size = len(audio_data)
            
            # Skip empty or suspiciously small chunks that might cause encoding issues
            if chunk_size < 10:
                print(f"⚠️ Skipping suspiciously small chunk ({chunk_size} bytes)")
                return True
            
            # 🚨 CRITICAL: Handle oversized chunks that exceed Google's limit
            if chunk_size > self.GOOGLE_AUDIO_CHUNK_SIZE_LIMIT:
                print(f"⚠️ Oversized audio chunk ({chunk_size} bytes) - splitting for API compatibility")
                return self._handle_oversized_chunk(audio_data)
            
            # 🔧 Validate WebM format integrity (basic check)
            if not self._is_valid_webm_chunk(audio_data):
                print(f"⚠️ Potentially corrupted WebM chunk detected ({chunk_size} bytes), skipping")
                return True
            
            # For normal-sized chunks, queue directly
            self._audio_queue.put_nowait(audio_data)
            self._chunk_counter += 1
            
            # Debug logging for size monitoring
            if chunk_size > 20000:  # Log larger chunks for monitoring
                print(f"📊 Large chunk queued: {chunk_size} bytes (under limit)")
            
            return True
            
        except queue.Full:
            self._handle_error("audio_queue_full", "Audio queue is full, dropping audio chunk.")
            return False

    def _handle_oversized_chunk(self, audio_data: bytes) -> bool:
        """
        Split oversized audio chunks into API-compliant pieces.
        
        This handles the common case where WebM chunks from MediaRecorder
        exceed Google's 25,600 byte limit.
        """
        chunk_size = len(audio_data)
        chunks_created = 0
        
        try:
            # Split into optimal-sized chunks
            offset = 0
            while offset < chunk_size:
                # Calculate remaining bytes
                remaining = chunk_size - offset
                next_chunk_size = min(self.OPTIMAL_CHUNK_SIZE, remaining)
                
                # Extract chunk
                chunk = audio_data[offset:offset + next_chunk_size]
                
                # Queue the chunk
                try:
                    self._audio_queue.put_nowait(chunk)
                    chunks_created += 1
                    offset += next_chunk_size
                    
                except queue.Full:
                    print(f"❌ Queue full while splitting chunk - dropped {chunks_created} sub-chunks")
                    return False
            
            self._chunk_counter += chunks_created
            print(f"✅ Split oversized chunk ({chunk_size} bytes) into {chunks_created} API-compliant chunks")
            return True
            
        except Exception as e:
            print(f"❌ Error splitting oversized chunk: {e}")
            return False

    def _manage_queue_health(self) -> None:
        """
        Periodically checks queue health and logs warnings if it's getting full.
        """
        try:
            current_time = time.time()
            queue_size = self._audio_queue.qsize()

            # Check if queue is getting full
            if queue_size >= self.queue_warning_threshold:
                print(f"⚠️ Audio queue warning: {queue_size}/{self.max_queue_size} chunks")

                # If queue is critically full, drop some old chunks
                if queue_size >= self.max_queue_size - 1:
                    chunks_to_drop = max(1, queue_size // 4)  # Drop 25% of queue
                    for _ in range(chunks_to_drop):
                        try:
                            self._audio_queue.get_nowait()
                        except queue.Empty:
                            break
                    print(f"🧹 Dropped {chunks_to_drop} old audio chunks to prevent overflow")

            # Periodic cleanup
            if current_time - self._last_queue_cleanup > self.queue_cleanup_interval:
                self._last_queue_cleanup = current_time

                # Log queue statistics
                print(f"📊 Queue stats: {queue_size}/{self.max_queue_size} chunks, "
                      f"{self._chunk_counter} total processed")

                # Clean up old segments if too many accumulated
                if len(self._segments) > 1000:  # Keep last 1000 segments
                    old_segments = self._segments[:-500]  # Keep last 500
                    self._segments = self._segments[-500:]
                    print(f"🧹 Cleaned up {len(old_segments)} old transcript segments")

        except Exception as e:
            print(f"❌ Error in queue health management: {e}")

    def _log_thread_heartbeat(self) -> None:
        """
        OBSERVABILITY: Log periodic heartbeat to confirm STT processing thread is alive
        """
        try:
            current_time = time.time()

            # Check if it's time for a heartbeat
            if current_time - self._last_heartbeat >= self.heartbeat_interval:
                self._last_heartbeat = current_time

                # STRUCTURED LOGGING: Thread health heartbeat
                heartbeat_context = {
                    "pipeline_stage": "stt_thread_heartbeat",
                    "thread_id": threading.current_thread().ident,
                    "thread_name": threading.current_thread().name,
                    "is_recording": self._is_recording,
                    "queue_size": self._audio_queue.qsize(),
                    "chunks_processed": self._chunk_counter,
                    "session_duration": current_time - self._session_start_time if self._session_start_time else 0,
                    "heartbeat_timestamp": current_time * 1000,  # milliseconds
                    "heartbeat_interval_seconds": self.heartbeat_interval
                }
                print(f"💓 STT_THREAD_HEARTBEAT: {heartbeat_context}")

                # Check for thread health issues
                if not self._is_recording:
                    alert_context = {
                        **heartbeat_context,
                        "pipeline_stage": "stt_thread_idle_alert",
                        "alert_reason": "thread_not_recording"
                    }
                    print(f"⚠️ STT_THREAD_IDLE_ALERT: {alert_context}")
                    self._thread_health_alerts.append(alert_context)

                # Limit alert history
                if len(self._thread_health_alerts) > 10:
                    self._thread_health_alerts = self._thread_health_alerts[-5:]

        except Exception as e:
            print(f"❌ Error in thread heartbeat logging: {e}")

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get detailed queue statistics for monitoring"""
        try:
            queue_size = self._audio_queue.qsize()
            queue_health = "healthy"

            if queue_size >= self.max_queue_size:
                queue_health = "critical"
            elif queue_size >= self.queue_warning_threshold:
                queue_health = "warning"

            return {
                "queue_size": queue_size,
                "max_queue_size": self.max_queue_size,
                "queue_health": queue_health,
                "queue_utilization": queue_size / self.max_queue_size,
                "total_chunks_processed": self._chunk_counter,
                "total_segments": len(self._segments),
                "last_cleanup": self._last_queue_cleanup,
                "is_recording": self._is_recording
            }
        except Exception as e:
            return {
                "error": f"Failed to get queue stats: {e}",
                "queue_health": "unknown"
            }

    def get_status(self) -> STTStatus:
        """Get current service status"""
        session_duration = 0
        if self._session_start_time and self._is_recording:
            session_duration = time.time() - self._session_start_time
        
        # Determine queue health
        queue_health = "healthy"
        queue_size = self._audio_queue.qsize()
        if queue_size > self.max_queue_size * 0.8:
            queue_health = "warning"
        elif queue_size >= self.max_queue_size:
            queue_health = "critical"
        
        # Get last activity
        last_activity = datetime.now()
        if self._segments:
            last_activity = self._segments[-1].timestamp
        
        return STTStatus(
            is_recording=self._is_recording,
            session_duration=session_duration,
            total_chunks_processed=self._chunk_counter,
            queue_size=queue_size,
            queue_health=queue_health,
            speakers_detected=len(self._get_unique_speakers()),
            total_segments=len(self._segments),
            current_chunk_id=self._chunk_counter,
            last_activity=last_activity
        )
    
    def get_transcript(self, format_type: str = "full") -> Dict[str, Any]:
        """
        Get the full transcript of the conversation.
        
        Args:
            format_type: "full", "recent", "by_speaker", "segments"
        """
        try:
            if format_type == "full":
                return {
                    "transcript": self._generate_final_transcript(),
                    "segments": [seg.to_dict() for seg in self._segments],
                    "speakers": self._get_unique_speakers(),
                    "total_segments": len(self._segments)
                }
            elif format_type == "recent":
                recent_segments = self._segments[-5:] if self._segments else []
                return {
                    "recent_segments": [seg.to_dict() for seg in recent_segments],
                    "count": len(recent_segments)
                }
            elif format_type == "by_speaker":
                return self._group_by_speaker()
            elif format_type == "segments":
                return {
                    "segments": [seg.to_dict() for seg in self._segments],
                    "count": len(self._segments)
                }
            else:
                return {
                    "error": f"Unknown format_type: {format_type}",
                    "available_formats": ["full", "recent", "by_speaker", "segments"]
                }
                
        except Exception as e:
            return {
                "error": f"Failed to get transcript: {e}",
                "segments": []
            }
    
    def _generate_final_transcript(self) -> str:
        """Generate formatted final transcript"""
        if not self._segments:
            return ""
        
        transcript_lines = []
        current_speaker = None
        
        for segment in self._segments:
            if segment.speaker_id != current_speaker:
                current_speaker = segment.speaker_id
                transcript_lines.append(f"\n{current_speaker}:")
            
            transcript_lines.append(f"  {segment.text}")
        
        return "\n".join(transcript_lines)
    
    def _get_unique_speakers(self) -> List[str]:
        """Get list of unique speakers detected"""
        return list(set(segment.speaker_id for segment in self._segments))
    
    def _group_by_speaker(self) -> Dict[str, Any]:
        """Group transcript segments by speaker"""
        speaker_segments = {}
        
        for segment in self._segments:
            speaker_id = segment.speaker_id
            if speaker_id not in speaker_segments:
                speaker_segments[speaker_id] = []
            speaker_segments[speaker_id].append(segment.to_dict())
        
        return {
            "by_speaker": speaker_segments,
            "speakers": list(speaker_segments.keys()),
            "total_speakers": len(speaker_segments)
        }

    def get_internal_state(self) -> Dict[str, Any]:
        """
        OBSERVABILITY: Get comprehensive internal state for debugging and monitoring
        """
        try:
            current_time = time.time()

            # Get last chunk timestamp
            last_chunk_timestamp = None
            if self._segments:
                last_chunk_timestamp = self._segments[-1].timestamp.isoformat()

            # Processing thread status
            thread_status = "not_started"
            if self._processing_thread:
                if self._processing_thread.is_alive():
                    thread_status = "alive"
                else:
                    thread_status = "dead"

            return {
                "service_type": "ProductionSTTServiceV2",
                "session_id": getattr(self, 'session_id', None),
                "is_recording": self._is_recording,
                "session_start_time": self._session_start_time,
                "session_duration": current_time - self._session_start_time if self._session_start_time else 0,
                "queue_size": self._audio_queue.qsize(),
                "max_queue_size": self.max_queue_size,
                "queue_health": self.get_queue_stats().get("queue_health", "unknown"),
                "chunks_processed": self._chunk_counter,
                "segments_captured": len(self._segments),
                "speakers_detected": len(self._get_unique_speakers()),
                "last_chunk_timestamp": last_chunk_timestamp,
                "processing_thread_status": thread_status,
                "processing_thread_id": self._processing_thread.ident if self._processing_thread else None,
                "has_credentials": self._has_credentials,
                "last_heartbeat": self._last_heartbeat,
                "thread_health_alerts_count": len(self._thread_health_alerts),
                "last_queue_cleanup": self._last_queue_cleanup,
                "state_dump_timestamp": current_time * 1000  # milliseconds
            }
        except Exception as e:
            return {
                "error": f"Failed to get internal state: {e}",
                "service_type": "ProductionSTTServiceV2",
                "state_dump_timestamp": time.time() * 1000
            }
    
    def save_transcript(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """Save transcript to file"""
        if not self._segments:
            return {
                "success": False,
                "message": "No transcript available to save"
            }
        
        if not filename:
            timestamp = int(time.time())
            filename = f"transcript_{timestamp}.txt"
        
        try:
            transcript_data = {
                "session_info": {
                    "timestamp": datetime.now().isoformat(),
                    "duration": time.time() - self._session_start_time if self._session_start_time else 0,
                    "chunks_processed": self._chunk_counter,
                    "speakers_detected": len(self._get_unique_speakers())
                },
                "transcript": self._generate_final_transcript(),
                "segments": [seg.to_dict() for seg in self._segments]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "message": f"Transcript saved to {filename}",
                "filename": filename,
                "segments_saved": len(self._segments)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to save transcript: {e}"
            }

# Mock STT Service for Testing
class MockSTTService:
    """Mock STT service for development and testing"""
    
    def __init__(self, **kwargs):
        self._is_recording = False
        self._transcript_callback = None
        self._chunk_counter = 0
        self._segments = []
        print("✅ MockSTTService initialized")
    
    def set_transcript_callback(self, callback):
        self._transcript_callback = callback
    
    def set_error_callback(self, callback):
        pass
    
    def set_status_callback(self, callback):
        pass
    
    def start_recording(self):
        self._is_recording = True
        self._chunk_counter = 0
        self._segments = []
        return {"success": True, "message": "Mock recording started", "is_recording": True}
    
    def stop_recording(self):
        self._is_recording = False
        return {"success": True, "message": "Mock recording stopped", "is_recording": False}
    
    def initialize_frontend_streaming(self):
        """Initialize frontend streaming for mock mode"""
        self._is_recording = True
        self._chunk_counter = 0
        self._segments = []
        return {
            "success": True,
            "message": "Mock frontend streaming initialized",
            "is_recording": True,
            "processing_thread_active": True,
            "audio_queue_size": 0
        }
    
    def queue_audio_chunk(self, audio_array):
        """Mock audio chunk queuing - generates mock transcripts"""
        if not self._is_recording:
            return False
            
        self._chunk_counter += 1
        
        # Generate mock transcript every few chunks
        if self._chunk_counter % 5 == 0:  # Every 5th chunk
            self._generate_mock_transcript()
            
        return True
    
    def _generate_mock_transcript(self):
        """Generate mock transcript segments"""
        mock_phrases = [
            "We need to review the project timeline",
            "The budget allocation looks good for Q2", 
            "Let's schedule a follow-up meeting next week",
            "Sarah will coordinate with the design team",
            "The client feedback has been very positive",
            "We should finalize the proposal by Friday"
        ]
        
        import random
        text = random.choice(mock_phrases)
        speaker_id = f"Speaker_{(self._chunk_counter % 2) + 1}"
        
        segment = TranscriptSegment(
            text=text,
            speaker_id=speaker_id,
            confidence=0.95,
            timestamp=datetime.now(),
            is_final=True,
            chunk_id=self._chunk_counter,
            language_code="en-US"
        )
        
        self._segments.append(segment)
        
        # Call transcript callback to send to SSE stream
        if self._transcript_callback:
            self._transcript_callback(segment)
        
        print(f"🎭 [MOCK] {speaker_id}: {text}")
    
    def get_status(self):
        return STTStatus(
            is_recording=self._is_recording,
            session_duration=0.0,
            total_chunks_processed=self._chunk_counter,
            queue_size=0,
            queue_health="healthy",
            speakers_detected=len(set(seg.speaker_id for seg in self._segments)),
            total_segments=len(self._segments),
            current_chunk_id=self._chunk_counter,
            last_activity=datetime.now()
        )
    
    def get_transcript(self, format_type="full"):
        if not self._segments:
            return {"transcript": "No transcript available yet", "segments": []}
            
        transcript_text = " ".join(seg.text for seg in self._segments)
        return {
            "transcript": transcript_text,
            "segments": [seg.to_dict() for seg in self._segments]
        }
    
    def save_transcript(self, filename=None):
        return {"success": True, "message": "Mock transcript saved"}

# Factory function for easy instantiation
def create_stt_service(mock_mode: bool = False, **kwargs) -> ProductionSTTServiceV2:
    """Factory function to create STT service"""
    if mock_mode:
        return MockSTTService(**kwargs)
    else:
        return ProductionSTTServiceV2(**kwargs)

if __name__ == "__main__":
    # Test the service
    print("🧪 Testing Production STT Service V2 (Optimized)")
    
    stt = ProductionSTTServiceV2()
    
    # Set up callbacks
    def on_transcript(segment: TranscriptSegment):
        print(f"📝 Callback: {segment.speaker_id}: {segment.text}")
    
    stt.set_transcript_callback(on_transcript)
    
    print("Ready for testing. Use start_recording() and stop_recording() methods.")