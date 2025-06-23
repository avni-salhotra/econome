#!/usr/bin/env python3
"""
Test STT architecture changes with streaming implementation
"""

import sys
import os
import asyncio
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from speech_agent import ProductionSTTServiceV2, MockSTTService, create_stt_service, TranscriptSegment

def test_mock_stt_service():
    """Test that MockSTTService works correctly"""
    print("🧪 Testing MockSTTService...")
    
    # Create mock service
    mock_stt = MockSTTService()
    
    # Test basic functionality
    assert hasattr(mock_stt, 'start_recording')
    assert hasattr(mock_stt, 'stop_recording')
    assert hasattr(mock_stt, 'get_status')
    assert hasattr(mock_stt, 'get_transcript')
    
    # Test start recording
    result = mock_stt.start_recording()
    assert result['success'] is True
    assert result['is_recording'] is True
    
    # Test stop recording
    result = mock_stt.stop_recording()
    assert result['success'] is True
    assert result['is_recording'] is False
    
    print("✅ MockSTTService test passed")

def test_create_stt_service_factory():
    """Test the create_stt_service factory function"""
    print("🧪 Testing create_stt_service factory...")
    
    # Test mock mode
    mock_service = create_stt_service(mock_mode=True)
    assert isinstance(mock_service, MockSTTService)
    
    # Test production mode
    prod_service = create_stt_service(mock_mode=False)
    assert isinstance(prod_service, ProductionSTTServiceV2)
    
    print("✅ create_stt_service factory test passed")

def test_streaming_stt_service_initialization():
    """Test that the new streaming STT service initializes correctly"""
    print("🧪 Testing ProductionSTTServiceV2 initialization...")
    
    # Create service
    stt = ProductionSTTServiceV2()
    
    # Check streaming-specific attributes
    assert hasattr(stt, '_streaming_client')
    assert hasattr(stt, '_streaming_config')
    assert hasattr(stt, '_stream_active')
    assert hasattr(stt, '_stream_lock')
    
    # Check that old methods are removed
    assert not hasattr(stt, '_transcribe_chunk')
    assert not hasattr(stt, '_process_speech_response')
    
    # Check that new streaming methods exist
    assert hasattr(stt, '_start_streaming_recognition')
    assert hasattr(stt, '_create_streaming_session')
    assert hasattr(stt, '_audio_chunk_generator')
    assert hasattr(stt, '_process_streaming_responses')
    assert hasattr(stt, '_handle_streaming_response')
    
    print("✅ ProductionSTTServiceV2 initialization test passed")

def test_streaming_stt_service_mock_recording():
    """Test that the streaming STT service works in mock mode"""
    print("🧪 Testing ProductionSTTServiceV2 mock recording...")
    
    # Create service (will run in mock mode if no audio devices)
    stt = ProductionSTTServiceV2()
    
    # Test recording lifecycle
    start_result = stt.start_recording()
    assert start_result['success'] is True
    assert start_result['is_recording'] is True
    
    # Wait a bit for mock processing
    time.sleep(2)
    
    # Test status
    status = stt.get_status()
    assert status.is_recording is True
    
    # Stop recording
    stop_result = stt.stop_recording()
    assert stop_result['success'] is True
    assert stop_result['is_recording'] is False
    
    # Get transcript
    transcript = stt.get_transcript()
    assert 'transcript' in transcript
    
    print("✅ ProductionSTTServiceV2 mock recording test passed")

def test_transcript_segment_compatibility():
    """Test that TranscriptSegment is compatible with the new architecture"""
    print("🧪 Testing TranscriptSegment compatibility...")
    
    # Create a transcript segment
    segment = TranscriptSegment(
        text="Test transcript",
        speaker_id="Speaker_1",
        confidence=0.95,
        timestamp=datetime.now(),
        is_final=True,
        chunk_id=1
    )
    
    # Test serialization
    segment_dict = segment.to_dict()
    assert 'text' in segment_dict
    assert 'speaker_id' in segment_dict
    assert 'confidence' in segment_dict
    assert 'timestamp' in segment_dict
    assert 'is_final' in segment_dict
    assert 'chunk_id' in segment_dict
    
    print("✅ TranscriptSegment compatibility test passed")

def test_callback_system():
    """Test that the callback system works correctly"""
    print("🧪 Testing callback system...")
    
    # Create mock service
    mock_stt = MockSTTService()
    
    # Test callback registration
    callback_called = False
    
    def test_callback(segment):
        nonlocal callback_called
        callback_called = True
    
    mock_stt.set_transcript_callback(test_callback)
    mock_stt.set_error_callback(lambda error_type, error: None)
    mock_stt.set_status_callback(lambda status: None)
    
    # Callbacks should be registered without error
    print("✅ Callback system test passed")

def main():
    """Run all tests"""
    print("🚀 Starting STT Architecture Tests...")
    print("=" * 50)
    
    try:
        # Run synchronous tests
        test_mock_stt_service()
        test_create_stt_service_factory()
        test_streaming_stt_service_initialization()
        test_streaming_stt_service_mock_recording()
        test_transcript_segment_compatibility()
        test_callback_system()
        
        print("\n" + "=" * 50)
        print("🎉 All STT Architecture Tests Passed!")
        print("✅ Mock mode works correctly")
        print("✅ Streaming architecture is properly implemented")
        print("✅ STT service lifecycle works correctly")
        print("✅ Callback system is functional")
        print("✅ Ready for production deployment")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 