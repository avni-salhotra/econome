#!/usr/bin/env python3
"""
Final STT Test - Using Official Google Pattern
"""

import time
from speech_agent import FinalWorkingAgent

def test_basic_recording():
    """Test basic recording functionality"""
    print("🧪 Testing FINAL Working STT Agent")
    print("=" * 50)
    
    # Create agent
    agent = FinalWorkingAgent()
    
    # Test Google connection first
    print("🔧 Testing Google Cloud connection...")
    connection_test = agent.test_google_connection()
    print(f"Connection test: {connection_test}")
    
    # Test minimal streaming
    print("\n🔧 Testing minimal streaming...")
    minimal_test = agent.test_minimal_streaming()
    print(f"Minimal test: {minimal_test}")
    
    # Test with known audio
    print("\n🔧 Testing with generated audio...")
    audio_test = agent.test_with_known_audio()
    print(f"Audio test: {audio_test}")
    
    # Check status
    status = agent.get_status()
    print(f"\n📊 Initial Status:")
    print(f"   Has credentials: {status['has_credentials']}")
    print(f"   Is recording: {status['is_recording']}")
    
    # Only continue with full test if minimal test works
    if minimal_test.get("responses", 0) > 0:
        print("\n✅ Minimal streaming works! Continuing with full test...")
    else:
        print("\n❌ Minimal streaming failed. Skipping full test.")
        print("🔍 This suggests a service account permissions issue.")
        return
    
    # Start recording
    print("\n🎤 Starting 10-second recording test...")
    print("🔊 SPEAK LOUDLY AND CLEARLY!")
    result = agent.start_recording()
    print(f"Start result: {result}")
    
    if result["status"] == "success":
        if result["has_credentials"]:
            print("\n🎯 Speak now for 10 seconds...")
            print("   Say something like: 'Hello, this is a test of the speech recognition system'")
            print("   📢 SPEAK LOUDLY - watch for audio level indicators!")
        else:
            print("\n⚠️ No credentials - audio will be captured but not transcribed")
        
        # Wait for 10 seconds
        for i in range(10, 0, -1):
            print(f"   ⏰ {i}s remaining...", end='\r')
            time.sleep(1)
        print("\n")
        
        # Stop recording
        result = agent.stop_recording()
        print(f"📄 Stop result: {result}")
        
        # Show transcript
        if result.get("transcript"):
            print(f"\n✅ TRANSCRIPT CAPTURED:")
            print("=" * 30)
            print(result["transcript"])
            print("=" * 30)
        else:
            print("\n⚠️ No transcript captured")
            if not status['has_credentials']:
                print("   This is expected without Google Cloud credentials")
            else:
                print("   🔍 Check if you spoke loudly enough (watch for audio level indicators)")
    
    else:
        print(f"❌ Failed to start recording: {result['message']}")

def interactive_test():
    """Interactive test mode"""
    print("\n🎮 Interactive Mode")
    print("Commands: start, stop, status, quit")
    
    agent = FinalWorkingAgent()
    
    while True:
        try:
            cmd = input("\nSpeech> ").strip().lower()
            
            if cmd == "quit" or cmd == "q":
                break
            elif cmd == "start":
                result = agent.start_recording()
                print(f"Start: {result}")
            elif cmd == "stop":
                result = agent.stop_recording()
                print(f"Stop: {result}")
                if result.get("transcript"):
                    print(f"Transcript: {result['transcript']}")
            elif cmd == "status":
                status = agent.get_status()
                print(f"Status: {status}")
            else:
                print("Unknown command. Use: start, stop, status, quit")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Basic 10-second test")
    print("2. Interactive mode")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        test_basic_recording()
    elif choice == "2":
        interactive_test()
    else:
        print("Invalid choice, running basic test...")
        test_basic_recording()
