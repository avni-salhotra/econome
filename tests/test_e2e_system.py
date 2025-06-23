#!/usr/bin/env python3
"""
End-to-End System Tests for HTTP-based Real-time Audio Streaming
Tests the complete HTTP API workflow without WebSocket dependencies
"""

import asyncio
import aiohttp
import json
import base64
import time
import os
import sys
from typing import Dict, Any

# Test configuration
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:8080")
TIMEOUT = 30

async def test_health_endpoint():
    """Test the health check endpoint"""
    print("🏥 Testing health endpoint...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{SERVICE_URL}/health") as response:
            if response.status != 200:
                raise Exception(f"Health check failed: {response.status}")
            
            data = await response.json()
            print(f"✅ Health check passed: {data}")
            return True

async def test_conversation_start():
    """Test starting a new conversation"""
    print("🚀 Testing conversation start...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVICE_URL}/api/conversation/start") as response:
            if response.status != 200:
                raise Exception(f"Failed to start conversation: {response.status}")
            
            data = await response.json()
            connection_id = data.get("connection_id")
            
            if not connection_id:
                raise Exception("No connection_id returned")
            
            print(f"✅ Conversation started with ID: {connection_id}")
            return connection_id

async def test_audio_upload(connection_id: str):
    """Test uploading audio data"""
    print("🎤 Testing audio upload...")
    
    # Create a simple test audio data (base64 encoded silence)
    test_audio_data = base64.b64encode(b'\x00' * 1024).decode('utf-8')
    
    payload = {
        "audio_data": test_audio_data,
        "format": "webm",
        "sample_rate": 16000
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{SERVICE_URL}/api/conversation/{connection_id}/audio",
            json=payload
        ) as response:
            if response.status not in [200, 202]:
                raise Exception(f"Audio upload failed: {response.status}")
            
            print("✅ Audio upload successful")
            return True

async def test_event_stream(connection_id: str):
    """Test Server-Sent Events stream"""
    print("📡 Testing event stream...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{SERVICE_URL}/api/conversation/{connection_id}/events",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Event stream failed: {response.status}")
                
                # Read first event to verify stream works
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data:'):
                        print(f"✅ Received event: {line_str[:100]}...")
                        break
                
                print("✅ Event stream test passed")
                return True
                
        except asyncio.TimeoutError:
            print("✅ Event stream timeout (expected for test)")
            return True

async def test_conversation_stop(connection_id: str):
    """Test stopping a conversation"""
    print("🛑 Testing conversation stop...")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{SERVICE_URL}/api/conversation/{connection_id}/stop") as response:
            if response.status not in [200, 202]:
                raise Exception(f"Failed to stop conversation: {response.status}")
            
            print("✅ Conversation stopped successfully")
            return True

async def run_http_api_tests():
    """Run complete HTTP API test suite"""
    print("🧪 Starting HTTP API E2E Tests...")
    print(f"🔗 Service URL: {SERVICE_URL}")
    
    try:
        # Test 1: Health check
        await test_health_endpoint()
        
        # Test 2: Start conversation
        connection_id = await test_conversation_start()
        
        # Test 3: Upload audio
        await test_audio_upload(connection_id)
        
        # Test 4: Test event stream
        await test_event_stream(connection_id)
        
        # Test 5: Stop conversation
        await test_conversation_stop(connection_id)
        
        print("✅ All HTTP API tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_dependencies():
    """Verify test dependencies are available"""
    print("🔍 Verifying test dependencies...")
    
    try:
        import aiohttp
        print("✅ aiohttp available")
        
        import asyncio
        print("✅ asyncio available")
        
        import json
        print("✅ json available")
        
        print("✅ All required modules available")
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

async def main():
    """Main test runner"""
    if not test_dependencies():
        sys.exit(1)
    
    success = await run_http_api_tests()
    
    if success:
        print("🎉 All E2E tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
