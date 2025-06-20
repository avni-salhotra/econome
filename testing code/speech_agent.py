import asyncio
import threading
import queue
import time
import numpy as np
from typing import Dict, Any, Optional, Generator, List
#
from google.cloud import speech_v1 as speech
import sounddevice as sd
from scipy.io import wavfile
import os

class Agent:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

class ProductionStreamingSTTAgent(Agent):
    """Production-ready real-time streaming STT with fault tolerance"""

    def __init__(self, credentials_path="speech-credentials.json"):
        super().__init__(
            name="ProductionStreamingSTTAgent",
            description="Production-ready real-time streaming speech transcription"
        )
        # Audio configuration (industry standard)
        self.sample_rate = 16000
        self.chunk_size = int(self.sample_rate / 10)  # 100ms chunks
        self.channels = 1  # Mono for STT
        self.dtype = np.int16

        # Session management
        self.streaming_limit = 240  # 4 minutes (Google's limit)
        self.max_queue_size = 50    # REDUCED - prevent overflow

        # Initialize Google Cloud Speech
        if os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            self._client = speech.SpeechClient()
            self._real_speech = True
            print("✓ Google Cloud Speech-to-Text v1 initialized")
        else:
            print("⚠ No credentials found - mock mode")
            self._real_speech = False

        # Threading and state management
        self._audio_queue = queue.Queue(maxsize=self.max_queue_size)
        self._is_recording = False
        self._session_start_time = None
        self._current_transcript = ""
        self._speaker_segments = []
        self._session_count = 0

        # Threads
        self._recording_thread = None
        self._streaming_thread = None
        
        # FIXED: Generator control
        self._should_generate = True

    def _get_streaming_config(self) -> speech.StreamingRecognitionConfig:
        """Get optimized streaming configuration"""
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.sample_rate,
            language_code="en-US",
            enable_automatic_punctuation=True,
            diarization_config=speech.SpeakerDiarizationConfig(
                enable_speaker_diarization=True,
                min_speaker_count=1,
                max_speaker_count=6
            )
        )
        return speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,
            single_utterance=False
        )
    
    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Sounddevice callback for audio capture"""
        if status:
            print(f"⚠️ Audio callback status: {status}")

        if self._is_recording:
            # Convert to bytes for Google Cloud Speech
            audio_bytes = (indata * 32767).astype(np.int16).tobytes()

            try:
                # FIXED: More aggressive queue management
                if self._audio_queue.qsize() < self.max_queue_size:
                    self._audio_queue.put(audio_bytes, block=False)
                else:
                    # Clear some space and add new frame
                    try:
                        for _ in range(5):  # Remove multiple old frames
                            self._audio_queue.get(block=False)
                        self._audio_queue.put(audio_bytes, block=False)
                    except queue.Empty:
                        pass
            except queue.Full:
                # Silently drop frames if queue is full
                pass
    
    def _request_generator(self) -> Generator[speech.StreamingRecognizeRequest, None, None]:
        """FIXED: Generate streaming requests with proper termination"""
        # First request: send streaming config
        streaming_config = self._get_streaming_config()
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        
        # Reset generator control
        self._should_generate = True
        
        # Subsequent requests: send audio data
        while self._is_recording and self._should_generate:
            try:
                # Get audio chunk with timeout
                chunk = self._audio_queue.get(timeout=0.5)
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                # No audio available, but keep the generator alive
                continue
            except Exception as e:
                print(f"❌ Audio generation error: {e}")
                break
    
    def _handle_streaming_responses(self, responses) -> None:
        """Process streaming responses from Google Cloud Speech"""
        try:
            for response in responses:
                if not self._is_recording:
                    break
                    
                if not response.results:
                    continue
                    
                result = response.results[0]
                if not result.alternatives:
                    continue
                
                transcript = result.alternatives[0].transcript
                confidence = result.alternatives[0].confidence or 0.0
                is_final = result.is_final
                
                # Extract speaker information
                speaker_tag = 1  # Default
                if hasattr(result.alternatives[0], 'words') and result.alternatives[0].words:
                    first_word = result.alternatives[0].words[0]
                    if hasattr(first_word, 'speaker_tag'):
                        speaker_tag = first_word.speaker_tag + 1
                
                if is_final:
                    # Final result - add to transcript
                    speaker_line = f"Speaker {speaker_tag}: {transcript}"
                    self._current_transcript += speaker_line + "\n"
                    
                    self._speaker_segments.append({
                        "speaker": speaker_tag,
                        "text": transcript,
                        "confidence": confidence,
                        "timestamp": time.time(),
                        "is_final": True
                    })
                    
                    print(f"🎭 {speaker_line}")
                else:
                    # Interim result - show in progress
                    print(f"🔄 Speaker {speaker_tag}: {transcript} (interim)")
                    
        except Exception as e:
            print(f"❌ Response handling error: {e}")
    
    def _run_streaming_recognition(self) -> None:
        """FIXED: Run streaming recognition with proper request handling"""
        if not self._real_speech:
            print("🔄 Mock streaming recognition (no credentials)")
            return
            
        try:
            print("🔄 Starting streaming recognition...")
            
            # FIXED: Use proper parameter name 'requests' (plural)
            request_generator = self._request_generator()
            responses = self._client.streaming_recognize(requests=request_generator)
            
            # Process responses
            self._handle_streaming_responses(responses)
            
        except Exception as e:
            print(f"❌ Streaming recognition error: {e}")
    
    def _session_timer(self) -> None:
        """Monitor session duration and restart if needed"""
        while self._is_recording:
            if self._session_start_time:
                elapsed = time.time() - self._session_start_time
                if elapsed >= self.streaming_limit:
                    print(f"⏰ Session limit reached ({self.streaming_limit}s) - restarting...")
                    self._restart_streaming_session()
            time.sleep(1.0)  # Check every second
    
    def _restart_streaming_session(self) -> None:
        """Restart streaming session (Google's endless streaming pattern)"""
        print("🔄 Restarting streaming session...")

        # Stop current streaming
        self._should_generate = False
        
        # Stop current streaming thread
        if self._streaming_thread and self._streaming_thread.is_alive():
            self._streaming_thread.join(timeout=2.0)

        # Brief pause
        time.sleep(0.1)

        # Reset session timer
        self._session_start_time = time.time()
        self._session_count += 1

        # Start new streaming thread
        self._streaming_thread = threading.Thread(
            target=self._run_streaming_recognition,
            daemon=True
        )
        self._streaming_thread.start()

        print(f"✅ Session #{self._session_count} restarted")
    
    def start_recording(self) -> Dict[str, Any]:
        """Start live audio recording and transcription"""
        if self._is_recording:
            return {
                "status": "error",
                "message": "Already recording",
                "is_recording": True
            }

        try:
            print("🎤 Starting live audio recording...")

            # Clear previous state
            self._current_transcript = ""
            self._speaker_segments = []
            self._session_count = 0
            
            # FIXED: Clear audio queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

            # Start recording
            self._is_recording = True
            self._session_start_time = time.time()

            # Start audio stream with sounddevice
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback,
                blocksize=self.chunk_size
            )
            self._stream.start()

            # Start streaming recognition thread
            if self._real_speech:
                self._streaming_thread = threading.Thread(
                    target=self._run_streaming_recognition,
                    daemon=True
                )
                self._streaming_thread.start()

                # Start session timer for automatic restart
                self._timer_thread = threading.Thread(
                    target=self._session_timer,
                    daemon=True
                )
                self._timer_thread.start()

            print("✅ Live recording started successfully")

            return {
                "status": "success",
                "message": "Live recording started",
                "is_recording": True,
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "session_limit": f"{self.streaming_limit}s"
            }

        except Exception as e:
            self._is_recording = False
            return {
                "status": "error",
                "message": f"Failed to start recording: {e}",
                "is_recording": False
            }
    
    def stop_recording(self) -> Dict[str, Any]:
        """Stop live audio recording"""
        if not self._is_recording:
            return {
                "status": "error",
                "message": "Not currently recording",
                "is_recording": False
            }

        try:
            print("⏹️ Stopping live recording...")

            # Stop recording
            self._is_recording = False
            self._should_generate = False  # FIXED: Stop generator

            # Stop audio stream
            if hasattr(self, '_stream') and self._stream:
                self._stream.stop()
                self._stream.close()

            # Wait for threads to finish (with proper timeout)
            if self._streaming_thread and self._streaming_thread.is_alive():
                self._streaming_thread.join(timeout=2.0)
                if self._streaming_thread.is_alive():
                    print("⚠️ Streaming thread still alive after timeout")

            session_duration = time.time() - self._session_start_time if self._session_start_time else 0

            print("✅ Recording stopped successfully")

            return {
                "status": "success",
                "message": "Recording stopped",
                "is_recording": False,
                "session_duration": f"{session_duration:.1f}s",
                "total_sessions": self._session_count + 1,
                "final_transcript": self._current_transcript,
                "speakers_detected": len(set(seg["speaker"] for seg in self._speaker_segments)),
                "total_segments": len(self._speaker_segments)
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Error stopping recording: {e}",
                "is_recording": False
            }
    
    def get_live_status(self) -> Dict[str, Any]:
        """Get current recording status and live transcript"""
        session_duration = 0
        if self._session_start_time and self._is_recording:
            session_duration = time.time() - self._session_start_time

        return {
            "status": "success",
            "is_recording": self._is_recording,
            "session_duration": f"{session_duration:.1f}s",
            "session_limit": f"{self.streaming_limit}s",
            "current_session": self._session_count + 1,
            "queue_size": self._audio_queue.qsize(),
            "current_transcript": self._current_transcript,
            "speakers_detected": len(set(seg["speaker"] for seg in self._speaker_segments)),
            "total_segments": len(self._speaker_segments),
            "recent_segments": self._speaker_segments[-5:] if self._speaker_segments else [],
            # Added for UI polling
            "partial_transcript_chunks": self._get_recent_transcript_chunks(),
            "session_health": self._get_session_health()
        }
    
    def _get_recent_transcript_chunks(self) -> List[Dict[str, Any]]:
        """Get recent transcript chunks for UI polling"""
        recent_chunks = []
        for segment in self._speaker_segments[-3:]:  # Last 3 segments
            recent_chunks.append({
                "speaker": segment["speaker"],
                "text": segment["text"][:100] + "..." if len(segment["text"]) > 100 else segment["text"],
                "timestamp": segment["timestamp"],
                "confidence": segment["confidence"]
            })
        return recent_chunks
    
    def _get_session_health(self) -> Dict[str, Any]:
        """Get session health metrics"""
        queue_health = "healthy"
        if self._audio_queue.qsize() > self.max_queue_size * 0.8:
            queue_health = "warning"
        elif self._audio_queue.qsize() > self.max_queue_size * 0.95:
            queue_health = "critical"

        session_health = "healthy"
        if self._session_start_time:
            elapsed = time.time() - self._session_start_time
            if elapsed > self.streaming_limit * 0.9:
                session_health = "restarting_soon"

        return {
            "queue_health": queue_health,
            "session_health": session_health,
            "streaming_active": self._streaming_thread.is_alive() if self._streaming_thread else False
        }
    
    def refresh_credentials(self) -> Dict[str, Any]:
        """Refresh Google Cloud credentials (for long sessions)"""
        try:
            # Force credential refresh
            self._client = speech.SpeechClient()
            return {
                "status": "success",
                "message": "Credentials refreshed successfully"
            }
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to refresh credentials: {e}"
            }
    
    def save_transcript(self, filename: Optional[str] = None) -> Dict[str, Any]:
        """Save current transcript to file"""
        if not self._current_transcript:
            return {
                "status": "error",
                "message": "No transcript available to save"
            }
        
        if not filename:
            timestamp = int(time.time())
            filename = f"transcript_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Transcript - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(self._current_transcript)
                f.write(f"\n\nSessions: {self._session_count + 1}\n")
                f.write(f"Speakers detected: {len(set(seg['speaker'] for seg in self._speaker_segments))}\n")
                f.write(f"Total segments: {len(self._speaker_segments)}\n")
            
            return {
                "status": "success",
                "message": f"Transcript saved to {filename}",
                "filename": filename,
                "transcript_length": len(self._current_transcript)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to save transcript: {e}"
            }
    
    def process(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing interface"""
        action = command.get("action", "status")
        
        if action == "start":
            return self.start_recording()
        elif action == "stop":
            return self.stop_recording()
        elif action == "status":
            return self.get_live_status()
        elif action == "save":
            filename = command.get("filename")
            return self.save_transcript(filename)
        elif action == "refresh_credentials":
            return self.refresh_credentials()
        else:
            return {
                "status": "error",
                "message": f"Unknown action: {action}",
                "available_actions": ["start", "stop", "status", "save", "refresh_credentials"]
            }

# USAGE EXAMPLES AND TESTING
if __name__ == "__main__":
    # Test the agent
    agent = ProductionStreamingSTTAgent()
    
    print("🧪 Testing Production Streaming STT Agent")
    print("Available commands:")
    print("  start - Start live recording")
    print("  stop  - Stop recording") 
    print("  status - Get current status")
    print("  save  - Save transcript to file")