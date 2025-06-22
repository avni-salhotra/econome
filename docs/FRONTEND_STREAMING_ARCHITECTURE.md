# Frontend Streaming Architecture

## Overview

The Econome system supports two audio input modes:
1. **Backend Microphone Mode**: Server captures audio directly (local development)
2. **Frontend Streaming Mode**: Browser captures audio and streams to server (cloud deployment)

## Architecture Components

### Frontend (Browser)
- **MediaRecorder API**: Captures microphone audio in WebM/MP4 format
- **WebSocket Client**: Streams audio chunks to backend in real-time
- **Safari Compatibility**: Special handling for Safari browser limitations

### Backend (Cloud Run)
- **WebSocket Server**: Receives audio chunks from frontend
- **Audio Processing Pipeline**: Converts WebM/MP4 to PCM for speech recognition
- **STT Service Integration**: Feeds processed audio to Google Speech V2

## Audio Processing Flow

```
Frontend Browser → MediaRecorder → WebSocket → Backend Processing → STT Service → Transcription
```

### Detailed Flow

1. **Frontend Capture**:
   ```javascript
   navigator.mediaDevices.getUserMedia({audio: true})
   → MediaRecorder(stream, {mimeType: 'audio/webm;codecs=opus'})
   → ondataavailable → base64 encoding → WebSocket
   ```

2. **Backend Processing**:
   ```python
   WebSocket → base64.decode() → pydub.AudioSegment → 16kHz mono PCM → numpy array → STT queue
   ```

3. **STT Processing**:
   ```python
   Audio queue → Google Speech V2 → Transcription segments → WebSocket response
   ```

## Key Components

### STTAgent vs ProductionSTTServiceV2

- **STTAgent**: Wrapper class that manages the STT service
- **ProductionSTTServiceV2**: Core service with audio processing capabilities
- **Critical Fix**: Frontend streaming must access `stt_agent.stt_service._audio_queue`, not `stt_agent._audio_queue`

### State Management

Frontend streaming mode requires proper state initialization:
```python
stt_service = stt_agent.stt_service
stt_service._is_recording = True
stt_service._session_start_time = time.time()
stt_service._processing_thread = threading.Thread(target=stt_service._process_audio_chunks)
```

### Audio Format Handling

The system handles multiple audio formats:
- **WebM with Opus codec** (preferred for Chrome/Firefox)
- **MP4 with AAC codec** (preferred for Safari)
- **WAV** (fallback for compatibility)

## Error Handling

### Common Issues and Solutions

1. **Audio Queue Access Error**:
   - **Cause**: Accessing `_audio_queue` on STTAgent instead of STTService
   - **Fix**: Use `stt_agent.stt_service._audio_queue`

2. **pydub Processing Failure**:
   - **Cause**: WebM format requires ffmpeg for decoding
   - **Fix**: Explicit format specification in `AudioSegment.from_file()`

3. **Buffer Size Errors**:
   - **Cause**: Attempting raw processing on encoded audio
   - **Fix**: Skip raw fallback for encoded formats (WebM, MP4)

## Browser Compatibility

### Chrome/Firefox
- Full WebM support with Opus codec
- Reliable MediaRecorder API
- Standard audio constraints

### Safari
- Limited WebM support, prefers MP4
- Special audio constraints needed
- Additional permission handling required

## Deployment Considerations

### Cloud Run Environment
- No local microphone access
- Frontend streaming is the primary mode
- ffmpeg installed in container for audio processing

### Local Development
- Can use either backend or frontend mode
- Backend mode preferred for development
- Frontend mode for testing cloud compatibility

## Debugging

### Debug Information
The system provides debug information in WebSocket responses:
```json
{
  "debug_info": {
    "stt_service_available": true,
    "audio_queue_available": true,
    "processing_thread_active": true,
    "is_recording": true
  }
}
```

### Logging
- Audio processing logs include format and sample count
- Error logs include specific failure reasons and suggestions
- WebSocket logs track connection and message flow

## Performance Considerations

### Audio Chunk Size
- 500ms chunks for responsive streaming
- Balance between latency and processing efficiency
- Configurable via MediaRecorder.start(interval)

### Memory Management
- Audio queue with maximum size limit
- Automatic cleanup of old audio chunks
- Thread-safe queue operations

## Security

### Data Privacy
- Audio data processed in memory only
- No persistent storage of audio content
- Automatic cleanup after session ends

### Network Security
- WebSocket connections over HTTPS in production
- Audio data transmitted as base64 over secure connection
- Connection-specific session management
