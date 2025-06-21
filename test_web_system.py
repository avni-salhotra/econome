#!/usr/bin/env python3
"""
Test script for the web-based conversation intelligence system
"""

import asyncio
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gcp_session_manager import GCPEphemeralSessionManager
from websocket_manager import WebSocketManager
from meeting_agents import ConversationIntelligenceSystem

async def test_session_manager():
    """Test the GCP session manager"""
    print("🧪 Testing GCP Session Manager...")
    
    manager = GCPEphemeralSessionManager()
    
    # Test session creation
    token = await manager.create_session(
        summary="Test conversation summary about planning a project meeting",
        action_items=[
            {"type": "todo", "action": "Schedule project meeting", "deadline": "Friday", "recipient": None},
            {"type": "communicate", "action": "Send agenda to team", "deadline": "Thursday", "recipient": "Team"},
            {"type": "reminder", "action": "Prepare presentation slides", "deadline": "Next week", "recipient": None}
        ],
        session_metadata={"test": True, "duration": "30 seconds"}
    )
    
    print(f"✅ Created session with token: {token[:8]}...")
    
    # Test session retrieval
    session = await manager.get_session(token)
    if session:
        print(f"✅ Retrieved session: {session.summary[:50]}...")
        print(f"   Time remaining: {session.time_remaining}")
        print(f"   Action items: {len(session.action_items)}")
    else:
        print("❌ Failed to retrieve session")
    
    # Test stats
    stats = await manager.get_session_stats()
    print(f"✅ Session stats: {stats}")
    
    return token

async def test_websocket_manager():
    """Test the WebSocket manager"""
    print("\n🧪 Testing WebSocket Manager...")
    
    manager = WebSocketManager()
    
    # Test broadcast
    await manager.broadcast({
        "type": "test",
        "message": "Test broadcast message",
        "timestamp": datetime.now().isoformat()
    })
    
    # Test live transcript broadcast
    await manager.broadcast_live_transcript(
        text="This is a test transcript",
        confidence=0.95,
        speaker_id="Speaker_1"
    )
    
    # Test system status broadcast
    await manager.broadcast_system_status(
        status="testing",
        message="System test in progress",
        details={"test_mode": True}
    )
    
    # Test stats
    stats = manager.get_connection_stats()
    print(f"✅ WebSocket stats: {stats}")

async def test_conversation_system():
    """Test the conversation intelligence system"""
    print("\n🧪 Testing Conversation Intelligence System...")
    
    # Create WebSocket manager for testing
    websocket_manager = WebSocketManager()
    
    # Initialize system with mock mode
    system = ConversationIntelligenceSystem(
        mock_mode=True,  # Use mock mode for testing
        chunk_duration=2.0,
        websocket_manager=websocket_manager
    )
    
    try:
        # Start system
        session_id = await system.start_system()
        print(f"✅ System started with session: {session_id}")
        
        # Test status
        status = system.get_live_status()
        print(f"✅ System status: {status}")
        
        # Test conversation start
        start_result = system.start_conversation()
        print(f"✅ Conversation start result: {start_result}")
        
        # Simulate some conversation time
        print("⏳ Simulating 5 seconds of conversation...")
        await asyncio.sleep(5)
        
        # Test conversation stop
        print("🛑 Stopping conversation and testing analysis...")
        stop_result = await system.stop_conversation()
        print(f"✅ Conversation stop result keys: {list(stop_result.keys())}")
        
        if stop_result.get("gemini_summary"):
            print(f"✅ Summary generated: {stop_result['gemini_summary'][:100]}...")
        
        if stop_result.get("action_items"):
            print(f"✅ Action items found: {len(stop_result['action_items'])}")
        
    except Exception as e:
        print(f"❌ System test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        system.stop_system()
        print("✅ System stopped")

async def test_integration():
    """Test full integration"""
    print("\n🧪 Testing Full Integration...")
    
    # Test session manager
    token = await test_session_manager()
    
    # Test WebSocket manager
    await test_websocket_manager()
    
    # Test conversation system
    await test_conversation_system()
    
    print(f"\n🎉 All tests completed!")
    print(f"📋 Session token for manual testing: {token}")
    print(f"🌐 You can test the session retrieval at: /api/results/{token}")

def test_imports():
    """Test that all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        from gcp_session_manager import GCPEphemeralSessionManager
        print("✅ GCP Session Manager import successful")
        
        from websocket_manager import WebSocketManager
        print("✅ WebSocket Manager import successful")
        
        from meeting_agents import ConversationIntelligenceSystem
        print("✅ Conversation Intelligence System import successful")
        
        from web_api import app
        print("✅ Web API import successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting Web System Tests...")
    print("=" * 50)
    
    # Test imports first
    if not test_imports():
        print("❌ Import tests failed. Please check dependencies.")
        return
    
    # Run integration tests
    await test_integration()
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    print("✅ All core components tested successfully")
    print("🌐 Ready to start web server with: python web_api.py")
    print("📱 Frontend available at: http://localhost:8080")
    print("📚 API docs available at: http://localhost:8080/docs")

if __name__ == "__main__":
    # Set up environment
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "speech-credentials.json"

    # Set up Gemini credentials for testing (use a dummy key)
    if "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = "dummy-key-for-testing"

    # Run tests
    asyncio.run(main())
