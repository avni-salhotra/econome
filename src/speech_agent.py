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
        self.max_queue_size = 10
        self.queue_warning_threshold = 8  # Warn when queue is 80% full
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
        self.queue_warning_threshold = int(self.max_queue_size * 0.8)  # 80% full warning

        self._recording_thread = None
        self._processing_thread = None

        # 🚨 NEW: Streaming recognition state management
        self._streaming_client = None
        self._streaming_config = None
        self._stream_active = False
        self._stream_lock = threading.Lock()
        self._restart_stream_event = threading.Event()
        
        # Stream health monitoring
        self._stream_start_time = None
        self._stream_duration_limit = 240  # 4 minutes (GCP limit is 5 minutes)
        self._last_stream_restart = time.time()
        self._stream_restart_count = 0

        # OBSERVABILITY: Thread health monitoring
        self._last_heartbeat = time.time()
        self.heartbeat_interval = 30.0  # seconds
        self._thread_health_alerts = []

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
            
            # 🎯 CRITICAL: Use explicit decoding config for Speech V2 instead of auto-detect
            # Based on our frontend audio capture: 16kHz, 16-bit, mono PCM
            recognition_config = speech_v2.RecognitionConfig(
                explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                    encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                ),
                language_codes=["en-US"],  # This must never be empty
                model="latest_long",  # Use latest_long for better transcription
            )
            
            # Debug: Print the config values
            print(f"🔍 RecognitionConfig created with language_codes: {recognition_config.language_codes}")
            print(f"🔍 Audio encoding: LINEAR16, sample_rate: 16000Hz, channels: 1")
            
            # Create streaming config
            self._streaming_config = speech_v2.StreamingRecognitionConfig(
                config=recognition_config,
                streaming_features=speech_v2.StreamingRecognitionFeatures(
                    interim_results=True,
                ),
            )
            
            # 🚨 CRITICAL: Verify streaming config was created properly
            if self._streaming_config is None:
                raise Exception("StreamingRecognitionConfig creation returned None")
            
            if self._streaming_config.config is None:
                raise Exception("StreamingRecognitionConfig.config is None")
                
            if not self._streaming_config.config.language_codes:
                raise Exception("StreamingRecognitionConfig.config.language_codes is empty")
            
            print(f"🔍 StreamingConfig created with language_codes: {self._streaming_config.config.language_codes}")
            print("✅ Streaming recognition configuration initialized with explicit encoding")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to initialize streaming config: {e}")
            print(f"❌ Exception type: {type(e).__name__}")
            print(f"❌ Exception details: {str(e)}")
            
            # 🚨 CRITICAL: Set to None and ensure we have a fallback
            self._streaming_config = None
            
            # Try to create a minimal fallback config
            try:
                print("🔄 Attempting fallback streaming config...")
                minimal_config = speech_v2.RecognitionConfig(
                    explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                        encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=16000,
                        audio_channel_count=1,
                    ),
                    language_codes=["en-US"],
                    model="default",  # Use default model as fallback
                )
                
                self._streaming_config = speech_v2.StreamingRecognitionConfig(
                    config=minimal_config,
                    streaming_features=speech_v2.StreamingRecognitionFeatures(
                        interim_results=True,
                    ),
                )
                print("✅ Fallback streaming config created successfully")
                
            except Exception as fallback_error:
                print(f"❌ Fallback config also failed: {fallback_error}")
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
        """🚨 NEW: Process audio chunks with STREAMING Google Speech V2 recognition"""
        from datetime import datetime
        print("🔄 STREAMING audio processing thread started")
        
        if not self._has_credentials:
            print("⚠️ No credentials - falling back to mock processing")
            self._mock_audio_processing()
            return
            
        # Start streaming recognition
        try:
            self._start_streaming_recognition()
        except Exception as e:
            print(f"❌ Failed to start streaming recognition: {e}")
            if self._error_callback:
                self._error_callback("streaming_start", e)
            return

        print("🏁 STREAMING audio processing thread finished")
    
    def _start_streaming_recognition(self) -> None:
        """🚨 CRITICAL: Start bidirectional streaming recognition"""
        print("🎤 Starting streaming recognition...")
        
        while self._is_recording:
            try:
                # Only (re)create the streaming session once we have *some* audio
                # in the queue. Spinning up a session with zero audio causes the
                # Speech-to-Text service to immediately abort with
                # "409 Stream timed out after receiving no more client requests".
                #
                # By waiting until the first audio chunk is available we ensure
                # the generator can deliver media within a few milliseconds of
                # sending the initial config request, eliminating the spurious
                # timeout and the rapid creation/teardown loop observed in the
                # logs.
                with self._stream_lock:
                    if not self._stream_active:
                        # Defer session creation until at least one chunk is queued
                        if self._audio_queue.qsize() == 0:
                            time.sleep(0.05)
                            continue
                        self._create_streaming_session()
                
                # Check if we need to restart the stream (GCP 5-minute limit)
                if self._should_restart_stream():
                    print("🔄 Restarting stream due to time limit")
                    self._restart_streaming_session()
                
                # Process any pending audio chunks
                self._send_audio_to_stream()
                
                # Small sleep to prevent busy waiting
                time.sleep(0.01)  # 10ms
                
            except Exception as e:
                print(f"❌ Streaming recognition error: {e}")
                if self._error_callback:
                    self._error_callback("streaming_recognition", e)
                
                # Try to restart the stream
                with self._stream_lock:
                    self._stream_active = False
                time.sleep(1.0)  # Wait before retry
    
    def _create_streaming_session(self) -> None:
        """Create a new streaming recognition session"""
        try:
            print("🚀 Creating new streaming session...")

            # 🚩 Activate stream *before* we create the gRPC call so that the
            #     _audio_chunk_generator while-loop sees _stream_active == True
            self._stream_active = True  # must be set early so generator runs
            self._stream_start_time = time.time()

            # Create streaming client
            self._streaming_client = self.speech_client.streaming_recognize(
                requests=self._audio_chunk_generator()
            )

            # Start response processing in separate thread
            response_thread = threading.Thread(
                target=self._process_streaming_responses,
                daemon=True
            )
            response_thread.start()
            
            self._stream_restart_count += 1
            
            print(f"✅ Streaming session #{self._stream_restart_count} created successfully")
            
        except Exception as e:
            print(f"❌ Failed to create streaming session: {e}")
            self._stream_active = False
            raise
    
    def _audio_chunk_generator(self):
        """🚨 CRITICAL: Generator that yields audio chunks for streaming (Speech V2 pattern)"""
        # First, send the recognizer and streaming config (Speech V2 API pattern)
        # According to V2 docs: "the first message must contain recognizer and streaming_config"
        
        # 🚨 CRITICAL: Safety check for None streaming config
        if self._streaming_config is None:
            print("❌ CRITICAL: streaming_config is None in generator!")
            print("🔄 Attempting to reinitialize streaming config...")
            self._initialize_streaming_config()
            
        # 🚨 CRITICAL: If still None after reinitializing, try one more time with minimal config
        if self._streaming_config is None:
            print("🔄 CRITICAL: Creating emergency streaming config in generator...")
            try:
                emergency_config = speech_v2.RecognitionConfig(
                    explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                        encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                        sample_rate_hertz=16000,
                        audio_channel_count=1,
                    ),
                    language_codes=["en-US"],
                    model="default",
                )
                
                self._streaming_config = speech_v2.StreamingRecognitionConfig(
                    config=emergency_config,
                    streaming_features=speech_v2.StreamingRecognitionFeatures(
                        interim_results=True,
                    ),
                )
                print("✅ Emergency streaming config created in generator")
                
            except Exception as emergency_error:
                print(f"❌ Emergency config failed: {emergency_error}")
                raise ValueError(f"Failed to create streaming config in generator: {emergency_error}")
            
        if self._streaming_config is None:
            raise ValueError("Failed to initialize streaming config - cannot proceed with streaming")
        
        print(f"🔍 STREAMING_REQUEST: recognizer={self.recognizer}")
        print(f"🔍 STREAMING_REQUEST: config.language_codes={self._streaming_config.config.language_codes}")
        
        yield speech_v2.StreamingRecognizeRequest(
            recognizer=self.recognizer,
            streaming_config=self._streaming_config
        )
        
        # Then continuously yield audio chunks
        while self._is_recording and self._stream_active:
            try:
                # Get audio chunk with timeout
                chunk_data = self._audio_queue.get(timeout=0.1)
                
                # Handle timestamped chunks
                if isinstance(chunk_data, dict) and "audio_data" in chunk_data:
                    audio_chunk = chunk_data["audio_data"]
                    chunk_id = chunk_data.get("chunk_id", self._chunk_counter)
                    
                    # Log chunk processing
                    print(f"🔍 STREAMING_CHUNK_SENT: chunk_id={chunk_id}, shape={audio_chunk.shape}")
                else:
                    audio_chunk = chunk_data
                
                # Convert to bytes
                # 🚨 CRITICAL FIX: Audio values are already in proper range from FFmpeg
                # Don't multiply by 32767 - FFmpeg already outputs int16-range values as float32
                # Just convert from float32 to int16 without scaling
                if audio_chunk.dtype == np.float32:
                    # Check if values are normalized (-1 to 1) or already scaled
                    max_val = np.abs(audio_chunk).max()
                    if max_val <= 1.0:
                        # Values are normalized, scale them
                        audio_int16 = (audio_chunk.flatten() * 32767).astype(np.int16)
                        print(f"🔍 AUDIO_SCALING: normalized->int16 (max_val: {max_val:.3f})")
                    else:
                        # Values are already scaled, just convert type
                        audio_int16 = audio_chunk.flatten().astype(np.int16)
                        print(f"🔍 AUDIO_SCALING: already_scaled->int16 (max_val: {max_val:.0f})")
                else:
                    # Already int16 or other integer type
                    audio_int16 = audio_chunk.flatten().astype(np.int16)
                    print(f"🔍 AUDIO_SCALING: direct conversion from {audio_chunk.dtype}")
                
                audio_bytes = audio_int16.tobytes()
                
                # Log audio quality for debugging
                print(f"🔍 AUDIO_BYTES_SENT: length={len(audio_bytes)}, samples={len(audio_int16)}, "
                      f"range=[{audio_int16.min()}, {audio_int16.max()}]")
                
                # 🚨 CRITICAL FIX: Split payload into ≤25 600-byte slices per API limits
                max_bytes = 25600  # Speech-to-Text V2 limit per StreamingRecognizeRequest
                for start in range(0, len(audio_bytes), max_bytes):
                    slice_bytes = audio_bytes[start:start + max_bytes]
                    yield speech_v2.StreamingRecognizeRequest(audio=slice_bytes)
                
                self._chunk_counter += 1
                
            except queue.Empty:
                # No audio available, continue
                continue
            except Exception as e:
                print(f"❌ Error in audio chunk generator: {e}")
                break
    
    def _process_streaming_responses(self) -> None:
        """🚨 CRITICAL: Process streaming responses from Google Speech API"""
        try:
            print("🎧 Starting streaming response processing...")
            
            for response in self._streaming_client:
                if not self._is_recording:
                    break
                    
                # NEW 🔴 Log API-level errors early and continue
                if hasattr(response, 'error') and response.error.code != 0:
                    print(
                        f"❌ STREAMING_ERROR: code={response.error.code} msg={response.error.message} details={response.error.details}"
                    )
                    # Raising here would unwind the thread and force a restart; instead, let
                    # upper-level timeout logic handle restarts so we can log many samples.
                    continue

                # Process the streaming response
                try:
                    self._handle_streaming_response(response)
                finally:
                    # 🔍 DEBUG: Log empty or unparsed responses for investigation
                    if not getattr(response, 'results', None):
                        print("🔍 STREAMING_DEBUG: empty results in response (event_time: {} error: {})".format(
                            getattr(response, 'speech_event_type', 'N/A'),
                            getattr(response, 'error', None)
                        ))
                
        except Exception as e:
            print(f"❌ Streaming response processing error: {e}")
            if self._error_callback:
                self._error_callback("streaming_response", e)
        finally:
            print("🏁 Streaming response processing finished")
    
    def _handle_streaming_response(self, response) -> None:
        """Handle individual streaming response"""
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
                
                # For MVP: Single speaker mode (no diarization)
                speaker_id = "Speaker_1"
                
                # Create transcript segment
                segment = TranscriptSegment(
                    text=transcript_text,
                    speaker_id=speaker_id,
                    confidence=alternative.confidence if hasattr(alternative, 'confidence') else 0.9,
                    timestamp=datetime.now(),
                    is_final=result.is_final,  # 🚨 CRITICAL: Use actual is_final from streaming
                    chunk_id=self._chunk_counter,
                    language_code="en-US"
                )
                
                # Store segment if final
                if result.is_final:
                    self._segments.append(segment)
                
                # Call transcript callback for both interim and final results
                if self._transcript_callback:
                    self._transcript_callback(segment)
                
                # Log the result
                status = "FINAL" if result.is_final else "INTERIM"
                print(f"🎤 [{status}] {speaker_id}: {transcript_text} (conf: {segment.confidence:.3f})")
                
        except Exception as e:
            print(f"❌ Error handling streaming response: {e}")
    
    def _should_restart_stream(self) -> bool:
        """Check if streaming session should be restarted"""
        if not self._stream_start_time:
            return False
            
        # Restart every 4 minutes (GCP limit is 5 minutes)
        return (time.time() - self._stream_start_time) > self._stream_duration_limit
    
    def _restart_streaming_session(self) -> None:
        """Restart the streaming session"""
        try:
            print("🔄 Restarting streaming session...")
            
            with self._stream_lock:
                self._stream_active = False
                
            # Small delay to ensure cleanup
            time.sleep(0.1)
            
            # Create new session
            self._create_streaming_session()
            
        except Exception as e:
            print(f"❌ Failed to restart streaming session: {e}")
            if self._error_callback:
                self._error_callback("stream_restart", e)
    
    def _send_audio_to_stream(self) -> None:
        """Send any pending audio chunks to the stream"""
        # This is handled by the _audio_chunk_generator
        # Just perform health monitoring here
        self._manage_queue_health()
        self._log_thread_heartbeat()

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

    # 🚨 REMOVED: _transcribe_chunk and _process_speech_response methods
    # These have been replaced with proper streaming recognition:
    # - _handle_streaming_response() now processes streaming responses
    # - _audio_chunk_generator() sends audio chunks to streaming API
    # - No more synchronous per-chunk API calls
    
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

            # STEP 2.5: 🚨 NEW: Clean up streaming session
            with self._stream_lock:
                if self._stream_active:
                    print("🔄 Stopping streaming session...")
                    self._stream_active = False
                    
                    # Give the stream a moment to clean up
                    time.sleep(0.1)

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
            # 🔍 CRITICAL DEBUG: Enhanced chunk queuing debugging
            queue_debug = {
                "is_recording": self._is_recording,
                "processing_thread_exists": self._processing_thread is not None,
                "processing_thread_alive": self._processing_thread.is_alive() if self._processing_thread else False,
                "audio_array_shape": audio_array.shape,
                "audio_array_dtype": str(audio_array.dtype),
                "audio_array_has_data": np.any(audio_array != 0),
                "current_queue_size": self._audio_queue.qsize(),
                "max_queue_size": self.max_queue_size,
                "chunk_counter": self._chunk_counter
            }
            print(f"🔍 DEBUG_QUEUE_AUDIO_CHUNK_ENTRY: {queue_debug}")
            
            if not self._is_recording:
                print("⚠️ Cannot queue audio chunk - not recording")
                return False

            # Ensure processing thread is running
            if self._processing_thread is None or not self._processing_thread.is_alive():
                print("⚠️ Processing thread not running - cannot queue audio chunk")
                return False

            # OBSERVABILITY: Add timestamp to audio chunk for queue time tracking
            from datetime import datetime
            timestamped_chunk = {
                "audio_data": audio_array,
                "enqueue_timestamp": datetime.now().timestamp() * 1000,  # milliseconds
                "chunk_id": self._chunk_counter
            }

            if not self._audio_queue.full():
                self._audio_queue.put(timestamped_chunk, block=False)
                print(f"✅ Audio chunk queued successfully (queue_size: {self._audio_queue.qsize()}/{self.max_queue_size})")
                return True
            else:
                # Queue is full, remove oldest and add new (with timeout for safety)
                try:
                    dropped_chunk = self._audio_queue.get_nowait()
                    self._audio_queue.put(timestamped_chunk, block=False)

                    # Log dropped chunk with timing info
                    if isinstance(dropped_chunk, dict) and "enqueue_timestamp" in dropped_chunk:
                        queue_time_ms = timestamped_chunk["enqueue_timestamp"] - dropped_chunk["enqueue_timestamp"]
                        print(f"⚠️ Audio queue was full - dropped oldest chunk (queue_time_ms: {queue_time_ms:.2f})")
                    else:
                        print("⚠️ Audio queue was full - dropped oldest chunk")
                    print(f"✅ Audio chunk queued after drop (queue_size: {self._audio_queue.qsize()}/{self.max_queue_size})")
                    return True
                except queue.Empty:
                    print("❌ Audio queue management failed - queue appeared full but was empty")
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