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
        """Callback from sounddevice to add audio data to the queue."""
        if status:
            print(f"⚠️ Audio callback status: {status}")
        
        # Only queue if recording is active
        if self._is_recording and not self._stop_event.is_set():
            try:
                self._audio_queue.put_nowait(indata.copy())
            except queue.Full:
                self._handle_error("audio_queue_full", "Audio queue is full, dropping audio chunk.")

    def _process_audio_chunks(self) -> None:
        """
        Processes audio chunks from the queue for the lifetime of a single
        streaming session. Exits when a stream restart is needed or when stopped.
        """
        while not self._restart_stream_event.is_set() and not self._stop_event.is_set():
            try:
                # Check for stream timeout
                if self._should_restart_stream():
                    print("🔄 Stream time limit reached, signaling restart.")
                    self._restart_stream_event.set()
                    continue

                self._send_audio_to_stream()
                self._log_thread_heartbeat()

            except Exception as e:
                self._handle_error("process_audio_chunks_error", e)
                self._restart_stream_event.set() # Signal restart on error

    def _start_streaming_recognition(self) -> None:
        """Manages the lifecycle of streaming recognition sessions."""
        self._stop_event.clear()
        self._stream_restart_count = 0

        while not self._stop_event.is_set():
            self._restart_stream_event.clear()
            
            # Create a new session
            if not self._create_streaming_session():
                self._handle_error("stream_creation_failed", "Could not create streaming session.")
                break

            # Each session gets its own processing thread
            session_thread = threading.Thread(target=self._process_audio_chunks)
            session_thread.start()
            session_thread.join() # Wait for the session to end (restart or stop)

            if self._stop_event.is_set():
                print("🛑 Stop event received, terminating streaming recognition.")
                break
            
            # If we are here, it means a restart was triggered
            print("🔄 Restarting streaming session...")
            self._stream_restart_count += 1
            self._last_stream_restart = time.time()
            # The loop will now create a new session

        print("✅ Streaming recognition fully terminated.")

    def _create_streaming_session(self) -> bool:
        """
        Initializes a new streaming recognition client and starts the
        response processing thread.
        """
        with self._stream_lock:
            try:
                print("🚀 Creating new streaming session...")
                if not self._has_credentials:
                    print("⚠️ Mock mode: skipping stream creation.")
                    return True # In mock mode, we can proceed

                # Generate the streaming requests
                requests = self._audio_chunk_generator()
                
                # Get the streaming client
                self._streaming_client = self.speech_client.streaming_recognize(
                    requests=requests,
                    config=self._streaming_config
                )
                self._stream_active = True
                self._stream_start_time = time.time()
                
                # Start a thread to process responses from this stream
                self._response_thread = threading.Thread(target=self._process_streaming_responses)
                self._response_thread.start()
                
                print(f"✅ Streaming session #{self._stream_restart_count + 1} created successfully")
                return True

            except Exception as e:
                self._handle_error("create_stream_error", e)
                self._stream_active = False
                return False

    def _audio_chunk_generator(self):
        """
        A generator that yields audio chunks from the queue.
        This is the main input to the Google Cloud Speech API.
        """
        # First request must be the config
        yield speech_v2.StreamingRecognizeRequest(recognizer=self.recognizer)
        
        print("🎧 Starting audio chunk generator...")

        while self._is_recording and not self._restart_stream_event.is_set() and not self._stop_event.is_set():
            try:
                # Use a timeout to allow the loop to check for stop/restart events
                chunk = self._audio_queue.get(timeout=0.1)
                
                # Convert float32 to int16 for LINEAR16 encoding
                if chunk.dtype == np.float32:
                    chunk = (chunk * 32767).astype(np.int16)
                
                yield speech_v2.StreamingRecognizeRequest(audio=chunk.tobytes())
                
                # Latency diagnostic
                current_ts = time.time()
                if self._prev_chunk_ts:
                    latency = (current_ts - self._prev_chunk_ts) * 1000
                    if latency > 200: # If latency is > 200ms
                         print(f"🕒 High audio chunk latency: {latency:.2f} ms")
                self._prev_chunk_ts = current_ts

            except queue.Empty:
                # This is normal, just means no audio was available in the last 0.1s
                continue
            except Exception as e:
                print(f"❌ Error in audio chunk generator: {e}")
                self._handle_error("audio_generator_error", e)
                break
        
        print("🚪 Audio chunk generator finished.")


    def _process_streaming_responses(self) -> None:
        """
        Processes responses from the current streaming recognition session.
        This runs in a dedicated thread per session.
        """
        print("🎧 Starting streaming response processing...")
        if not self._streaming_client:
            print("⚠️ No streaming client available for response processing.")
            return

        try:
            for response in self._streaming_client:
                self._handle_streaming_response(response)
        except Exception as e:
            # Check if this is an expected "stream closed" error or something else
            if "RST_STREAM" in str(e) or "channel closed" in str(e):
                print("🚪 Stream closed normally.")
            else:
                self._handle_error("streaming_response_error", e)
        finally:
            with self._stream_lock:
                self._stream_active = False
            print("🏁 Streaming response processing finished")

    def _handle_streaming_response(self, response: speech_v2.StreamingRecognizeResponse) -> None:
        """Handles a single response from the Speech API."""
        if not response.results:
            return

        for result in response.results:
            if not result.alternatives:
                continue
            
            transcript_text = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence
            
            # Filter out empty or whitespace-only transcripts
            if not transcript_text.strip():
                continue

            # Log raw event for debugging
            print(f"🎤 Raw STT Event: is_final={result.is_final}, text='{transcript_text}'")

            # Create a structured segment
            segment = TranscriptSegment(
                text=transcript_text,
                speaker_id="speaker_0", # Diarization not implemented in this version
                confidence=confidence,
                timestamp=datetime.now(),
                is_final=result.is_final,
                chunk_id=self._chunk_counter
            )
            
            # Fire callback and append to internal log
            if self._transcript_callback:
                try:
                    self._transcript_callback(segment)
                except Exception as e:
                    self._handle_error("transcript_callback_error", e)

            # Only add final segments to the persistent transcript log
            if result.is_final:
                self._segments.append(segment)

    def _should_restart_stream(self) -> bool:
        """Check if the stream has been active for too long."""
        if not self._stream_start_time:
            return False
        
        elapsed = time.time() - self._stream_start_time
        return elapsed > self._stream_duration_limit

    def _restart_streaming_session(self) -> None:
        """DEPRECATED: This logic is now handled by the main recognition loop."""
        # This method is kept for backward compatibility but should not be used.
        # The new design handles this in _start_streaming_recognition.
        print("⚠️ _restart_streaming_session is deprecated.")
        self._restart_stream_event.set()


    def _send_audio_to_stream(self) -> None:
        """DEPRECATED: This logic is now handled by the _audio_chunk_generator."""
        # This method is kept for backward compatibility but should not be used.
        pass

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
                target=self._start_streaming_recognition,
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
                "has_credentials": self._has_credentials,
                "timestamp": datetime.now().isoformat()
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
        """Stops the recording and transcription session."""
        print("🛑 Stopping recording...")
        
        if not self._is_recording:
            print("⚠️ Recording already stopped.")
            return {"status": "already_stopped"}

        # Signal all loops to stop
        self._stop_event.set()
        self._is_recording = False

        # Stop the audio input stream
        if AUDIO_AVAILABLE and hasattr(self, '_audio_stream'):
            try:
                self._audio_stream.stop()
                self._audio_stream.close()
                print("🔇 Audio stream stopped")
            except Exception as e:
                print(f"⚠️ Error stopping audio stream: {e}")
        elif not AUDIO_AVAILABLE:
            print("🔇 Mock audio processing stopped")

        # Ensure the response thread is also joined if it exists and is alive
        if hasattr(self, '_response_thread') and self._response_thread and self._response_thread.is_alive():
             self._response_thread.join(timeout=2.0)

        # Final cleanup
        with self._stream_lock:
            if self._stream_active:
                print("🔄 Forcing streaming session shutdown after grace period")
                self._stream_active = False

        # Wait for processing thread to finish
        if self._processing_thread and self._processing_thread.is_alive():
            print("⏳ Waiting for processing thread to terminate...")
            self._processing_thread.join(timeout=5.0)
            if self._processing_thread.is_alive():
                print("⚠️ Processing thread did not terminate in time.")
        
        # Clear any remaining audio buffers
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