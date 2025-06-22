#!/usr/bin/env python3
"""
Test script to verify cloud mode detection and audio processing
"""

import os
import sys
import asyncio
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from speech_agent import AUDIO_AVAILABLE, CLOUD_RUN_MODE
from web_api import websocket_manager, session_manager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cloud_mode_detection():
    """Test cloud mode detection"""
    print("🔍 Testing Cloud Mode Detection...")
    print(f"  AUDIO_AVAILABLE: {AUDIO_AVAILABLE}")
    print(f"  CLOUD_RUN_MODE: {CLOUD_RUN_MODE}")
    
    # Check environment variables
    cloud_env_vars = ['K_SERVICE', 'K_REVISION', 'K_CONFIGURATION']
    for var in cloud_env_vars:
        value = os.getenv(var)
        print(f"  {var}: {value}")
    
    # Check hostname
    import socket
    hostname = socket.gethostname()
    print(f"  Hostname: {hostname}")
    
    # Check if we're in a container
    container_indicators = ['/proc/1/cgroup', '/.dockerenv']
    for indicator in container_indicators:
        exists = os.path.exists(indicator)
        print(f"  {indicator}: {exists}")
    
    print("✅ Cloud mode detection test complete\n")

def test_audio_processing():
    """Test audio processing capabilities"""
    print("🎵 Testing Audio Processing...")
    
    try:
        import numpy as np
        print("  ✅ NumPy available")
    except ImportError:
        print("  ❌ NumPy not available")
        return
    
    try:
        from pydub import AudioSegment
        print("  ✅ pydub available")
    except ImportError:
        print("  ❌ pydub not available")
    
    try:
        import sounddevice as sd
        print("  ✅ sounddevice available")
        
        # Try to query devices
        try:
            devices = sd.query_devices()
            print(f"  📱 Audio devices found: {len(devices)}")
            for i, device in enumerate(devices[:3]):  # Show first 3 devices
                print(f"    {i}: {device['name']} (in: {device['max_input_channels']}, out: {device['max_output_channels']})")
        except Exception as e:
            print(f"  ⚠️ Could not query audio devices: {e}")
            
    except ImportError:
        print("  ❌ sounddevice not available")
    
    print("✅ Audio processing test complete\n")

def test_websocket_manager():
    """Test WebSocket manager initialization"""
    print("🔗 Testing WebSocket Manager...")
    
    try:
        # Test WebSocket manager
        stats = websocket_manager.get_connection_stats()
        print(f"  ✅ WebSocket manager initialized: {stats}")
    except Exception as e:
        print(f"  ❌ WebSocket manager error: {e}")
    
    print("✅ WebSocket manager test complete\n")

async def test_session_manager():
    """Test session manager"""
    print("💾 Testing Session Manager...")
    
    try:
        stats = await session_manager.get_session_stats()
        print(f"  ✅ Session manager stats: {stats}")
    except Exception as e:
        print(f"  ❌ Session manager error: {e}")
    
    print("✅ Session manager test complete\n")

def main():
    """Run all tests"""
    print("🧪 Running Cloud Audio Tests...\n")
    
    # Run synchronous tests
    test_cloud_mode_detection()
    test_audio_processing()
    test_websocket_manager()
    
    # Run async tests
    asyncio.run(test_session_manager())
    
    print("🎉 All tests completed!")

if __name__ == "__main__":
    main() 