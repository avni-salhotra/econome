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

# Google Cloud Speech V2 imports
from google.cloud import speech_v2
from google.oauth2 import service_account

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
    - Real-time transcription with configurable chunk sizes
    - Chirp 2 model for enhanced accuracy
    - Model adaptation for improved name recognition
    - Automatic error recovery
    - Health monitoring
    - Callback-based event system
    - Mock mode for development
    """
    
    def __init__(self, 
                 credentials_path: str = "speech-credentials.json",
                 chunk_duration: float = 0.5,
                 sample_rate: int = 16000,
                 project_id: str = "econome-hackathon"):
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)
        self.channels = 1
        self.dtype = np.float32

        self.project_id = project_id
        self.max_queue_size = 10
        self.queue_warning_threshold = 8  # Warn when queue is 80% full
        self.queue_cleanup_interval = 30  # Clean up old chunks every 30 seconds

        self._initialize_speech_client(credentials_path)

        self._audio_queue = queue.Queue(maxsize=self.max_queue_size)
        self._is_recording = False
        self._session_start_time = None
        self._chunk_counter = 0
        self._segments = []
        self._last_queue_cleanup = time.time()

        self._recording_thread = None
        self._processing_thread = None

        self._transcript_callback = None
        self._error_callback = None
        self._status_callback = None

        print(f"✅ ProductionSTTServiceV2 initialized (chunk_duration={chunk_duration}s, model=chirp_2, buffer_size={self.max_queue_size})")
    
    def _initialize_speech_client(self, credentials_path: str) -> None:
        """Initialize Google Cloud Speech V2 client with regional endpoint"""
        try:
            # Try multiple credential paths (for Cloud Run and local development)
            credential_paths = [
                credentials_path,  # Default path (local development)
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
                # OPTIMIZED: Use regional endpoint for better performance
                from google.api_core.client_options import ClientOptions
                client_options = ClientOptions(
                    api_endpoint="us-central1-speech.googleapis.com"
                )

                self.speech_client = speech_v2.SpeechClient(
                    credentials=self.credentials,
                    client_options=client_options
                )
                self._has_credentials = True

                # OPTIMIZED: Use regional recognizer for better performance
                self.recognizer = f"projects/{self.project_id}/locations/us-central1/recognizers/_"

                print("✅ Google Cloud Speech V2 client initialized (us-central1 region)")
            else:
                print("⚠️ No credentials found - running in mock mode")
                self._has_credentials = False
                self.speech_client = None
                
        except Exception as e:
            print(f"❌ Failed to initialize Speech client: {e}")
            self._has_credentials = False
            self.speech_client = None
    
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
        if status:
            print(f"⚠️ Audio status: {status}")
            if self._error_callback:
                self._error_callback("audio_capture", Exception(f"Audio status: {status}"))

        if self._is_recording:
            try:
                if not self._audio_queue.full():
                    self._audio_queue.put(indata.copy(), block=False)
                else:
                    try:
                        self._audio_queue.get_nowait()
                        self._audio_queue.put(indata.copy(), block=False)
                    except queue.Empty:
                        pass
            except Exception as e:
                if self._error_callback:
                    self._error_callback("audio_queue", e)
    
    def _process_audio_chunks(self) -> None:
        """Process audio chunks with Google Speech V2"""
        print("🔄 Audio processing thread started")
        chunk_count = 0

        while self._is_recording:
            try:
                # Get audio chunk with timeout
                audio_chunk = self._audio_queue.get(timeout=1.0)

                # Double-check recording status before processing
                if not self._is_recording:
                    print("🛑 Recording stopped, skipping chunk processing")
                    break

                # Process the chunk
                self._transcribe_chunk(audio_chunk)
                chunk_count += 1

                # Perform queue health management every 10 chunks
                if chunk_count % 10 == 0:
                    self._manage_queue_health()

            except queue.Empty:
                # Timeout is normal, just continue checking
                # Use this opportunity to check queue health
                self._manage_queue_health()
                continue
            except Exception as e:
                print(f"❌ Audio processing error: {e}")
                if self._error_callback:
                    self._error_callback("audio_processing", e)

        print("🏁 Audio processing thread finished")

    def _mock_audio_processing(self) -> None:
        """Mock audio processing for CI environments without audio hardware"""
        print("🔄 Mock audio processing thread started")
        while self._is_recording:
            try:
                # Simulate audio chunk processing every 2 seconds
                time.sleep(2.0)

                if not self._is_recording:
                    break

                # Generate mock transcript
                self._chunk_counter += 1
                self._generate_mock_transcript()

            except Exception as e:
                print(f"❌ Mock audio processing error: {e}")
                if self._error_callback:
                    self._error_callback("mock_audio_processing", e)

        print("🏁 Mock audio processing thread finished")

    def _transcribe_chunk(self, audio_chunk: np.ndarray) -> None:
        """Transcribe audio chunk using Google Speech V2 with Chirp 2 model"""
        try:
            # Check if recording is still active before processing
            if not self._is_recording:
                print("🛑 Recording stopped, skipping transcription")
                return

            self._chunk_counter += 1

            if not self._has_credentials:
                # Mock mode for development
                self._generate_mock_transcript()
                return

            # Convert audio to required format
            audio_int16 = (audio_chunk.flatten() * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            # OPTIMIZED: Create Speech V2 request with Chirp 2 model, without diarization_config
            request = speech_v2.RecognizeRequest(
                recognizer=self.recognizer,
                config=speech_v2.RecognitionConfig(
                    explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                        encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=self.sample_rate,
                        audio_channel_count=1,
                    ),
                    language_codes=["en-US"],
                    model="chirp_2",  # OPTIMIZED: Latest & most accurate model
                    features=speech_v2.RecognitionFeatures(
                        enable_automatic_punctuation=True,
                        enable_word_time_offsets=True,
                        enable_word_confidence=True
                    )
                ),
                content=audio_bytes
            )

            # Call Speech V2 API
            response = self.speech_client.recognize(request=request)

            # Process response
            self._process_speech_response(response)

        except Exception as e:
            print(f"❌ Transcription error for chunk {self._chunk_counter}: {e}")
            if self._error_callback:
                self._error_callback("transcription", e)
    
    def _process_speech_response(self, response) -> None:
        """Process Google Speech V2 response"""
        try:
            if not response.results:
                return
            
            for result in response.results:
                if not result.alternatives:
                    continue
                
                alternative = result.alternatives[0]
                transcript_text = alternative.transcript.strip()
                
                if not transcript_text:
                    continue
                
                # Extract speaker information
                speaker_id = "Speaker_1"  # Default
                if hasattr(alternative, 'words') and alternative.words:
                    # Get speaker tag from first word
                    first_word = alternative.words[0]
                    if hasattr(first_word, 'speaker_label') and first_word.speaker_label:
                        speaker_id = f"Speaker_{first_word.speaker_label}"
                
                # Create transcript segment
                segment = TranscriptSegment(
                    text=transcript_text,
                    speaker_id=speaker_id,
                    confidence=alternative.confidence if hasattr(alternative, 'confidence') else 0.9,
                    timestamp=datetime.now(),
                    is_final=True,  # V2 sync always returns final results
                    chunk_id=self._chunk_counter,
                    language_code="en-US"
                )
                
                # Store segment
                self._segments.append(segment)
                
                # Call transcript callback
                if self._transcript_callback:
                    self._transcript_callback(segment)
                
                print(f"🎭 {speaker_id}: {transcript_text} (conf: {segment.confidence:.3f})")
                
        except Exception as e:
            print(f"❌ Response processing error: {e}")
            # TEMPORARILY DISABLED: Error callback to fix async issues
            # if self._error_callback:
            #     self._error_callback("response_processing", e)
            print(f"⚠️ Error logged: response_processing - {e}")
    
    def _generate_mock_transcript(self) -> None:
        """Generate mock transcript for development"""
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
        
        if self._transcript_callback:
            self._transcript_callback(segment)
        
        print(f"🎭 [MOCK] {speaker_id}: {text}")
    
    def start_recording(self) -> Dict[str, Any]:
        if self._is_recording:
            return {
                "success": False,
                "message": "Already recording",
                "is_recording": True
            }

        # Check if audio is available
        if not AUDIO_AVAILABLE:
            mode_reason = "Cloud Run environment" if CLOUD_RUN_MODE else "audio not available"
            print(f"🎤 Starting mock recording ({mode_reason})...")
            self._is_recording = True
            self._session_start_time = time.time()
            self._chunk_counter = 0
            self._segments.clear()

            # Start mock processing thread
            self._processing_thread = threading.Thread(
                target=self._mock_audio_processing,
                daemon=True
            )
            self._processing_thread.start()

            return {
                "success": True,
                "message": f"Mock recording started ({mode_reason})",
                "is_recording": True,
                "sample_rate": self.sample_rate,
                "chunk_duration": self.chunk_duration,
                "has_credentials": self._has_credentials,
                "mock_mode": True,
                "cloud_run_mode": CLOUD_RUN_MODE
            }

        try:
            print("🎤 Starting live audio recording...")
            self._clear_audio_buffers()

            self._chunk_counter = 0
            self._segments.clear()

            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

            self._is_recording = True
            self._session_start_time = time.time()

            self._audio_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback,
                blocksize=self.chunk_size,
                latency='low'
            )
            self._audio_stream.start()

            self._processing_thread = threading.Thread(
                target=self._process_audio_chunks,
                daemon=True
            )
            self._processing_thread.start()

            print("✅ Recording started successfully")
            return {
                "success": True,
                "message": "Recording started",
                "is_recording": True,
                "sample_rate": self.sample_rate,
                "chunk_duration": self.chunk_duration,
                "has_credentials": self._has_credentials
            }
        except Exception as e:
            self._is_recording = False
            error_msg = f"Failed to start recording: {e}"
            print(f"❌ {error_msg}")
            # TEMPORARILY DISABLED: Error callback to fix async issues
            # if self._error_callback:
            #     self._error_callback("start_recording", e)
            print(f"⚠️ Start recording error logged: {e}")
            return {
                "success": False,
                "message": error_msg,
                "is_recording": False
            }
    
    def stop_recording(self) -> Dict[str, Any]:
        if not self._is_recording:
            return {
                "success": False,
                "message": "Not currently recording",
                "is_recording": False
            }

        try:
            print("⏹️ Stopping recording...")

            # STEP 1: Stop audio stream FIRST to prevent new audio chunks (if audio is available)
            if AUDIO_AVAILABLE and hasattr(self, '_audio_stream'):
                try:
                    self._audio_stream.stop()
                    self._audio_stream.close()
                    print("🔇 Audio stream stopped")
                except Exception as e:
                    print(f"⚠️ Error stopping audio stream: {e}")
            elif not AUDIO_AVAILABLE:
                print("🔇 Mock audio processing stopped")

            # STEP 2: Set recording flag to False to stop processing thread
            self._is_recording = False
            print("🛑 Recording flag set to False")

            # STEP 3: Wait for processing thread to finish
            if self._processing_thread and self._processing_thread.is_alive():
                print("⏳ Waiting for processing thread to finish...")
                self._processing_thread.join(timeout=3.0)
                if self._processing_thread.is_alive():
                    print("⚠️ Processing thread still alive after timeout")
                else:
                    print("✅ Processing thread finished")

            # STEP 4: Clear any remaining audio buffers
            self._clear_audio_buffers()

            session_duration = time.time() - self._session_start_time if self._session_start_time else 0
            final_transcript = self._generate_final_transcript()

            print("✅ Recording stopped successfully")
            return {
                "success": True,
                "message": "Recording stopped",
                "is_recording": False,
                "session_duration": session_duration,
                "chunks_processed": self._chunk_counter,
                "segments_captured": len(self._segments),
                "speakers_detected": len(self._get_unique_speakers()),
                "final_transcript": final_transcript
            }
        except Exception as e:
            error_msg = f"Error stopping recording: {e}"
            print(f"❌ {error_msg}")
            # TEMPORARILY DISABLED: Error callback to fix async issues
            # if self._error_callback:
            #     self._error_callback("stop_recording", e)
            print(f"⚠️ Stop recording error logged: {e}")
            return {
                "success": False,
                "message": error_msg,
                "is_recording": False
            }

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

    def initialize_frontend_streaming(self) -> Dict[str, Any]:
        """
        Initialize the STT service for frontend streaming mode

        This provides a proper interface for frontend streaming initialization
        instead of direct property access from web_api.py
        """
        try:
            # Initialize state for frontend streaming
            self._is_recording = True
            self._session_start_time = time.time()
            self._chunk_counter = 0
            self._segments.clear()

            # Clear any existing audio queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

            # Start processing thread if not already running (with proper synchronization)
            if self._processing_thread is None or not self._processing_thread.is_alive():
                import threading
                import time

                self._processing_thread = threading.Thread(
                    target=self._process_audio_chunks,
                    daemon=True
                )
                self._processing_thread.start()

                # Wait briefly to ensure thread is properly started
                time.sleep(0.1)

                # Verify thread started successfully
                if not self._processing_thread.is_alive():
                    raise Exception("Failed to start audio processing thread")

            return {
                "success": True,
                "message": "Frontend streaming mode initialized",
                "is_recording": self._is_recording,
                "processing_thread_active": self._processing_thread.is_alive(),
                "audio_queue_size": self._audio_queue.qsize()
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to initialize frontend streaming: {str(e)}",
                "error": str(e)
            }

    def queue_audio_chunk(self, audio_array: np.ndarray) -> bool:
        """
        Queue an audio chunk for processing

        Provides a proper interface for adding audio chunks instead of
        direct access to _audio_queue from web_api.py
        """
        try:
            if not self._is_recording:
                print("⚠️ Cannot queue audio chunk - not recording")
                return False

            # Ensure processing thread is running
            if self._processing_thread is None or not self._processing_thread.is_alive():
                print("⚠️ Processing thread not running - cannot queue audio chunk")
                return False

            if not self._audio_queue.full():
                self._audio_queue.put(audio_array, block=False)
                return True
            else:
                # Queue is full, remove oldest and add new (with timeout for safety)
                try:
                    self._audio_queue.get_nowait()
                    self._audio_queue.put(audio_array, block=False)
                    print("⚠️ Audio queue was full - dropped oldest chunk")
                    return True
                except queue.Empty:
                    print("❌ Audio queue management failed")
                    return False

        except Exception as e:
            print(f"❌ Error queuing audio chunk: {e}")
            return False

    def _manage_queue_health(self) -> None:
        """
        Manage audio queue health and perform cleanup

        This method monitors queue size and performs periodic cleanup
        to prevent memory issues and ensure optimal performance
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
        Get transcript in various formats
        
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
        print("✅ MockSTTService initialized")
    
    def set_transcript_callback(self, callback):
        self._transcript_callback = callback
    
    def set_error_callback(self, callback):
        pass
    
    def set_status_callback(self, callback):
        pass
    
    def start_recording(self):
        self._is_recording = True
        return {"success": True, "message": "Mock recording started", "is_recording": True}
    
    def stop_recording(self):
        self._is_recording = False
        return {"success": True, "message": "Mock recording stopped", "is_recording": False}
    
    def get_status(self):
        return STTStatus(
            is_recording=self._is_recording,
            session_duration=0.0,
            total_chunks_processed=0,
            queue_size=0,
            queue_health="healthy",
            speakers_detected=0,
            total_segments=0,
            current_chunk_id=0,
            last_activity=datetime.now()
        )
    
    def get_transcript(self, format_type="full"):
        return {"transcript": "Mock transcript", "segments": []}
    
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