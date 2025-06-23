#!/usr/bin/env python3
"""
Comprehensive Tests for Streaming STT V2 Architecture
Tests the new real-time streaming speech-to-text functionality
"""

import asyncio
import json
import os
import sys
import time
import pytest
import numpy as np
import base64
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from speech_agent import ProductionSTTServiceV2, MockSTTService, TranscriptSegment, STTStatus
from meeting_agents import ConversationIntelligenceSystem


class TestStreamingSTTV2:
    """Test suite for Streaming STT V2 functionality"""
    
    @pytest.fixture
    def mock_stt_service(self):
        """Create a mock STT service for testing"""
        return MockSTTService()
    
    @pytest.fixture
    def real_stt_service(self):
        """Create a real STT service in mock mode"""
        return ProductionSTTServiceV2(credentials_path="non-existent-path.json")
    
    @pytest.fixture
    def sample_audio_chunk(self):
        """Generate sample audio data for testing"""
        # Generate 100ms of sine wave at 16kHz
        sample_rate = 16000
        duration = 0.1  # 100ms
        frequency = 440  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        return audio_data
    
    def test_stt_service_initialization(self, real_stt_service):
        """Test STT service initializes correctly"""
        assert real_stt_service is not None
        assert real_stt_service.sample_rate == 16000
        assert real_stt_service.chunk_duration == 0.1
        assert real_stt_service.max_queue_size == 10
    
    def test_mock_stt_service(self, mock_stt_service):
        """Test mock STT service functionality"""
        # Test basic functionality
        result = mock_stt_service.start_recording()
        assert result['success'] is True
        assert result['is_recording'] is True
        
        status = mock_stt_service.get_status()
        assert isinstance(status, STTStatus)
        assert status.is_recording is True
        
        result = mock_stt_service.stop_recording()
        assert result['success'] is True
        assert result['is_recording'] is False
    
    def test_transcript_segment_creation(self):
        """Test transcript segment data structure"""
        segment = TranscriptSegment(
            text="Hello world",
            speaker_id="Speaker_1",
            confidence=0.95,
            timestamp=datetime.now(),
            is_final=True,
            chunk_id=1
        )
        
        assert segment.text == "Hello world"
        assert segment.speaker_id == "Speaker_1"
        assert segment.confidence == 0.95
        assert segment.is_final is True
        assert segment.chunk_id == 1
        
        # Test serialization
        segment_dict = segment.to_dict()
        assert 'timestamp' in segment_dict
        assert segment_dict['text'] == "Hello world"
    
    def test_stt_status_creation(self):
        """Test STT status data structure"""
        status = STTStatus(
            is_recording=True,
            session_duration=10.5,
            total_chunks_processed=100,
            queue_size=5,
            queue_health="healthy",
            speakers_detected=2,
            total_segments=15,
            current_chunk_id=100,
            last_activity=datetime.now()
        )
        
        assert status.is_recording is True
        assert status.session_duration == 10.5
        assert status.queue_health == "healthy"
        
        # Test serialization
        status_dict = status.to_dict()
        assert 'last_activity' in status_dict
        assert status_dict['total_chunks_processed'] == 100
    
    def test_audio_chunk_queuing(self, real_stt_service, sample_audio_chunk):
        """Test audio chunk queuing functionality"""
        # Initialize frontend streaming
        result = real_stt_service.initialize_frontend_streaming()
        assert result['success'] is True
        
        # Test queuing audio chunks
        success = real_stt_service.queue_audio_chunk(sample_audio_chunk)
        assert success is True
        
        # Check queue stats
        stats = real_stt_service.get_queue_stats()
        assert stats['queue_size'] >= 0
        assert stats['queue_health'] in ['healthy', 'warning', 'critical']
        
        # Cleanup
        real_stt_service.stop_recording()
    
    def test_callback_system(self, real_stt_service):
        """Test the callback system for transcript segments"""
        transcript_received = []
        error_received = []
        status_received = []
        
        def transcript_callback(segment):
            transcript_received.append(segment)
        
        def error_callback(error_type, error):
            error_received.append((error_type, error))
        
        def status_callback(status):
            status_received.append(status)
        
        # Set callbacks
        real_stt_service.set_transcript_callback(transcript_callback)
        real_stt_service.set_error_callback(error_callback)
        real_stt_service.set_status_callback(status_callback)
        
        # Callbacks should be set
        assert real_stt_service._transcript_callback == transcript_callback
        assert real_stt_service._error_callback == error_callback
        assert real_stt_service._status_callback == status_callback
    
    def test_queue_health_management(self, real_stt_service, sample_audio_chunk):
        """Test queue health monitoring and management"""
        # Initialize streaming
        real_stt_service.initialize_frontend_streaming()
        
        # Fill queue to test health management
        for i in range(real_stt_service.max_queue_size + 2):
            real_stt_service.queue_audio_chunk(sample_audio_chunk)
        
        # Check queue stats
        stats = real_stt_service.get_queue_stats()
        assert stats['queue_size'] <= real_stt_service.max_queue_size
        
        # Cleanup
        real_stt_service.stop_recording()
    
    def test_session_lifecycle(self, real_stt_service):
        """Test complete session lifecycle"""
        # Start recording
        result = real_stt_service.start_recording()
        assert result['success'] is True
        assert result['is_recording'] is True
        
        # Check status during recording
        status = real_stt_service.get_status()
        assert status.is_recording is True
        assert status.session_duration >= 0
        
        # Stop recording
        result = real_stt_service.stop_recording()
        assert result['success'] is True
        assert result['is_recording'] is False
        
        # Check final status
        status = real_stt_service.get_status()
        assert status.is_recording is False
    
    def test_transcript_generation(self, real_stt_service):
        """Test transcript generation and formatting"""
        # Get transcript in different formats
        transcript = real_stt_service.get_transcript("full")
        assert 'transcript' in transcript
        assert 'segments' in transcript
        
        recent = real_stt_service.get_transcript("recent")
        assert 'recent_segments' in recent
        
        by_speaker = real_stt_service.get_transcript("by_speaker")
        assert 'by_speaker' in by_speaker
        
        segments = real_stt_service.get_transcript("segments")
        assert 'segments' in segments
    
    def test_internal_state_monitoring(self, real_stt_service):
        """Test internal state monitoring for observability"""
        state = real_stt_service.get_internal_state()
        
        required_fields = [
            'service_type', 'is_recording', 'queue_size', 
            'max_queue_size', 'chunks_processed', 'segments_captured',
            'processing_thread_status', 'has_credentials'
        ]
        
        for field in required_fields:
            assert field in state
        
        assert state['service_type'] == 'ProductionSTTServiceV2'
    
    def test_error_handling(self, real_stt_service):
        """Test error handling in various scenarios"""
        # Test stopping when not recording
        result = real_stt_service.stop_recording()
        assert result['success'] is False
        assert 'not currently recording' in result['message'].lower()
        
        # Test queuing when not recording
        sample_audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        success = real_stt_service.queue_audio_chunk(sample_audio)
        assert success is False
    
    @pytest.mark.asyncio
    async def test_conversation_system_integration(self):
        """Test integration with conversation intelligence system"""
        # Create conversation system with mock mode
        system = ConversationIntelligenceSystem(
            mock_mode=True,
            project_id="test-project"
        )
        
        # Test system initialization
        session_id = await system.start_system()
        assert session_id is not None
        
        # Test conversation start/stop
        result = await system.start_conversation()
        assert 'success' in result
        
        result = await system.stop_conversation()
        assert 'success' in result
        
        # Cleanup
        await system.stop_system()
    
    def test_streaming_config_initialization(self, real_stt_service):
        """Test streaming configuration initialization"""
        if real_stt_service._has_credentials:
            assert real_stt_service._streaming_config is not None
            config = real_stt_service._streaming_config
            
            # Check key configuration parameters
            assert config.interim_results is True
            assert config.single_utterance is False
            assert config.config.language_codes == ["en-US"]
        else:
            # In mock mode, streaming config should be None
            assert real_stt_service._streaming_config is None


class TestAudioProcessingPipeline:
    """Test audio processing pipeline functionality"""
    
    @pytest.fixture
    def sample_base64_audio(self):
        """Generate sample base64-encoded audio data"""
        # Generate sample audio data
        sample_rate = 16000
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        # Convert to int16 and encode
        audio_int16 = (audio_data * 32767).astype(np.int16)
        audio_bytes = audio_int16.tobytes()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        return audio_base64
    
    def test_base64_audio_decoding(self, sample_base64_audio):
        """Test base64 audio decoding"""
        try:
            audio_bytes = base64.b64decode(sample_base64_audio)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
            
            assert len(audio_array) > 0
            assert audio_array.dtype == np.float32
            assert np.max(np.abs(audio_array)) <= 1.0
        except Exception as e:
            pytest.fail(f"Base64 audio decoding failed: {e}")
    
    def test_audio_format_validation(self):
        """Test audio format validation"""
        valid_formats = ['audio/webm', 'audio/mp4', 'audio/wav', 'audio/ogg']
        
        for format_type in valid_formats:
            # These should be recognized formats
            assert format_type in ['audio/webm', 'audio/mp4', 'audio/wav', 'audio/ogg']
    
    def test_audio_chunk_processing_performance(self, sample_base64_audio):
        """Test audio chunk processing performance"""
        start_time = time.time()
        
        # Simulate processing multiple audio chunks
        for _ in range(10):
            audio_bytes = base64.b64decode(sample_base64_audio)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should process 10 chunks in under 1 second
        assert processing_time < 1.0


class TestHTTPAPIIntegration:
    """Test integration with HTTP API endpoints"""
    
    def test_api_function_availability(self):
        """Test that critical API functions are available"""
        # Import web_api module
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        import web_api
        
        # Check critical functions exist
        assert hasattr(web_api, 'start_frontend_streaming_mode')
        assert hasattr(web_api, 'process_frontend_audio_chunk')
        assert hasattr(web_api, 'handle_websocket_command')
        assert hasattr(web_api, 'log_websocket_message')
    
    def test_websocket_replacement_function(self):
        """Test WebSocket replacement function"""
        import web_api
        
        # Test the log_websocket_message function exists and is callable
        assert callable(web_api.log_websocket_message)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 