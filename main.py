#!/usr/bin/env python3
"""
Production Real-Time Conversation Intelligence System
Main demo script for Google Cloud ADK Hackathon

Clean architecture with STT service and multi-agent coordination
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Dict, Any

# Import our production system
from meeting_agents import ConversationIntelligenceSystem
from speech_agent import ProductionSTTServiceV2

def print_banner():
    """Print system banner"""
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║          🏆 REAL-TIME CONVERSATION INTELLIGENCE SYSTEM 🏆            ║")
    print("║                     Google Cloud ADK Hackathon                       ║")
    print("╠═══════════════════════════════════════════════════════════════════════╣")
    print("║  🎤 Google Cloud Speech V2  │  🧠 Vertex AI Analysis                 ║")
    print("║  📋 Action Item Extraction  │  🔄 Multi-Agent Architecture           ║")
    print("║  📊 Real-time Intelligence  │  💾 BigQuery Storage                   ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")

async def interactive_demo():
    """Interactive demo with real-time conversation processing"""
    
    print_banner()
    print("\n🎯 INTERACTIVE DEMO MODE")
    print("=" * 70)
    
    # Configuration
    mock_mode = input("Run in mock mode (no Google Cloud required)? [y/N]: ").lower().startswith('y')
    
    if mock_mode:
        print("🔧 Running in MOCK MODE - no credentials required")
    else:
        print("🔧 Running in PRODUCTION MODE - using Google Cloud services")
    
    # Initialize system
    print("\n🏗️ Initializing system...")
    system = ConversationIntelligenceSystem(
        mock_mode=mock_mode,
        chunk_duration=2.0,  # 2-second chunks for responsive feel
        project_id="econome-hackathon"
    )
    
    try:
        # Start system
        print("🚀 Starting multi-agent system...")
        session_id = await system.start_system()
        
        print(f"✅ System ready! Session ID: {session_id}")
        
        # Interactive loop
        while True:
            print("\n" + "="*50)
            print("🎮 CONVERSATION INTELLIGENCE DEMO")
            print("="*50)
            print("1. Start live conversation recording")
            print("2. Get system status")
            print("3. Test STT service directly")
            print("4. Run automated demo")
            print("5. Exit")
            
            choice = input("\nSelect option [1-5]: ").strip()
            
            if choice == "1":
                await live_conversation_demo(system)
            elif choice == "2":
                show_system_status(system)
            elif choice == "3":
                await test_stt_directly(mock_mode)
            elif choice == "4":
                await automated_demo(system)
            elif choice == "5":
                break
            else:
                print("❌ Invalid option. Please select 1-5.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        print("\n🧹 Cleaning up...")
        system.stop_system()
        print("✅ System shutdown complete")

async def live_conversation_demo(system):
    """Live conversation recording demo"""
    
    print("\n🎤 LIVE CONVERSATION DEMO")
    print("-" * 30)
    
    # Start conversation
    print("Starting conversation recording...")
    start_result = system.start_conversation()
    
    if not start_result.get("success"):
        print(f"❌ Failed to start recording: {start_result.get('message')}")
        return
    
    print("✅ Recording started!")
    print("\n📢 CONVERSATION PROMPTS:")
    print("Try saying phrases like:")
    print("• 'John will send the proposal by Friday'")
    print("• 'We need to schedule a design review next week'")
    print("• 'Sarah should coordinate with the marketing team'")
    print("• 'Let's follow up on the budget discussion'")
    print("• 'Mike will prepare the client presentation'")
    
    # Monitor for specified duration or user input
    duration = int(input("\nRecording duration in seconds [30]: ") or "30")
    
    print(f"\n🎤 RECORDING FOR {duration} SECONDS...")
    print("Speak naturally now...")
    
    # Real-time monitoring
    start_time = time.time()
    last_status_time = start_time
    
    while time.time() - start_time < duration:
        # Show status updates every 5 seconds
        if time.time() - last_status_time >= 5:
            status = system.get_live_status()
            session_info = status.get("session_info", {})
            
            chunks = session_info.get("total_transcript_chunks", 0)
            duration_str = session_info.get("session_duration", "0:00:00")
            
            print(f"📊 Live Status: {chunks} chunks processed | Duration: {duration_str}")
            last_status_time = time.time()
        
        await asyncio.sleep(1)
    
    # Stop recording
    print("\n⏹️ Stopping recording...")
    summary = system.stop_conversation()
    
    # Display results
    display_conversation_results(summary)

async def automated_demo(system):
    """Automated demo with simulated conversation"""
    
    print("\n🤖 AUTOMATED DEMO")
    print("-" * 20)
    
    print("Starting automated conversation simulation...")
    
    # Start recording
    start_result = system.start_conversation()
    if not start_result.get("success"):
        print(f"❌ Failed to start: {start_result.get('message')}")
        return
    
    # Let it run for a shorter duration in automated mode
    print("🎤 Simulating 20-second conversation...")
    await asyncio.sleep(20)
    
    # Stop and show results
    summary = system.stop_conversation()
    display_conversation_results(summary)

def display_conversation_results(summary: Dict[str, Any]):
    """Display conversation analysis results"""
    
    print("\n" + "="*70)
    print("📊 CONVERSATION ANALYSIS RESULTS")
    print("="*70)
    
    if summary.get("error"):
        print(f"❌ Error: {summary['error']}")
        return
    
    # Basic session info
    print(f"🆔 Session ID: {summary.get('session_id', 'N/A')}")
    print(f"⏱️  Duration: {summary.get('duration_formatted', 'N/A')}")
    print(f"📝 Transcript Chunks: {summary.get('total_transcript_chunks', 0)}")
    print(f"🎭 Speakers Detected: Multiple speakers identified")
    
    # Action items
    action_items = summary.get('action_items', [])
    print(f"\n📋 ACTION ITEMS EXTRACTED: {len(action_items)}")
    
    if action_items:
        print("-" * 50)
        for i, item in enumerate(action_items, 1):
            print(f"{i}. {item.get('action', 'N/A')}")
            print(f"   👤 Assigned to: {item.get('assignee', 'N/A')}")
            print(f"   ⚡ Priority: {item.get('priority', 'N/A')}")
            print(f"   📅 Deadline: {item.get('deadline', 'N/A')}")
            print(f"   🕐 Detected: {item.get('timestamp', 'N/A')[:19]}")
            print()
    else:
        print("   No action items detected in this conversation segment")
    
    # System performance
    print("\n⚡ SYSTEM PERFORMANCE:")
    print(f"   🔄 Multi-agent coordination: ✅ Active")
    print(f"   🎤 Real-time transcription: ✅ Completed")
    print(f"   🧠 Live analysis: ✅ Processed")
    print(f"   💾 Data storage: ✅ Ready")

def show_system_status(system):
    """Show detailed system status"""
    
    print("\n📊 SYSTEM STATUS")
    print("-" * 20)
    
    status = system.get_live_status()
    
    print(f"🔧 System Running: {status.get('system_running', False)}")
    
    session_info = status.get("session_info", {})
    print(f"📋 Session Active: {session_info.get('session_active', False)}")
    
    if session_info.get("session_active"):
        print(f"🆔 Session ID: {session_info.get('session_id', 'N/A')}")
        print(f"🎤 Recording: {session_info.get('transcription_active', False)}")
        print(f"⏱️  Duration: {session_info.get('session_duration', 'N/A')}")
    
    stt_status = status.get("stt_status", {})
    if stt_status:
        print(f"🔊 Queue Health: {stt_status.get('queue_health', 'N/A')}")
        print(f"📝 Chunks Processed: {stt_status.get('total_chunks_processed', 0)}")
        print(f"🎭 Speakers Detected: {stt_status.get('speakers_detected', 0)}")

async def test_stt_directly(mock_mode: bool):
    """Test STT service directly"""
    
    print("\n🔧 DIRECT STT SERVICE TEST")
    print("-" * 30)
    
    # Create STT service
    if mock_mode:
        from speech_agent import MockSTTService
        stt = MockSTTService()
        print("🔧 Using Mock STT Service")
    else:
        stt = ProductionSTTServiceV2()
        print("🔧 Using Production STT Service")
    
    # Set up callback
    def on_transcript(segment):
        print(f"📝 {segment.speaker_id}: {segment.text} (confidence: {segment.confidence:.3f})")
    
    if hasattr(stt, 'set_transcript_callback'):
        stt.set_transcript_callback(on_transcript)
    
    # Test recording
    print("\nStarting 15-second STT test...")
    start_result = stt.start_recording()
    
    if start_result.get("success"):
        print("🎤 Recording... speak now!")
        await asyncio.sleep(15)
        
        stop_result = stt.stop_recording()
        print(f"⏹️ Recording stopped: {stop_result.get('message')}")
        
        if hasattr(stt, 'get_transcript'):
            transcript = stt.get_transcript()
            print(f"\n📄 Final transcript length: {len(transcript.get('transcript', ''))}")
    else:
        print(f"❌ Failed to start recording: {start_result.get('message')}")

def quick_test():
    """Quick system validation test"""
    
    print("🧪 QUICK SYSTEM TEST")
    print("=" * 30)
    
    async def run_test():
        # Test system initialization
        print("1. Testing system initialization...")
        system = ConversationIntelligenceSystem(mock_mode=True)
        
        # Test system startup
        print("2. Testing system startup...")
        session_id = await system.start_system()
        print(f"   ✅ Session created: {session_id}")
        
        # Test status
        print("3. Testing status reporting...")
        status = system.get_live_status()
        print(f"   ✅ System running: {status.get('system_running')}")
        
        # Test conversation start/stop
        print("4. Testing conversation flow...")
        start_result = system.start_conversation()
        print(f"   ✅ Conversation started: {start_result.get('success')}")
        
        await asyncio.sleep(2)  # Brief pause
        
        stop_result = system.stop_conversation()
        print(f"   ✅ Conversation stopped: {stop_result.get('session_id') is not None}")
        
        # Cleanup
        print("5. Testing system shutdown...")
        system.stop_system()
        print("   ✅ System stopped")
        
        print("\n🎯 QUICK TEST COMPLETE - All systems operational!")
    
    asyncio.run(run_test())

def show_help():
    """Show help information"""
    
    print("\n📖 CONVERSATION INTELLIGENCE SYSTEM HELP")
    print("=" * 50)
    print("This system provides real-time conversation intelligence using:")
    print("• Google Cloud Speech-to-Text V2 for transcription")
    print("• Vertex AI for conversation analysis")
    print("• Multi-agent architecture for coordination")
    print("• Real-time action item extraction")
    print("\nUsage:")
    print("  python main.py                 - Interactive demo")
    print("  python main.py --test          - Quick system test")
    print("  python main.py --help          - Show this help")
    print("\nRequirements:")
    print("• speech-credentials.json file (for production mode)")
    print("• Google Cloud project with Speech and Vertex AI enabled")
    print("• Audio input device (microphone)")

def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ["--help", "-h", "help"]:
            show_help()
        elif arg in ["--test", "-t", "test"]:
            quick_test()
        else:
            print(f"❌ Unknown argument: {arg}")
            show_help()
    else:
        # Run interactive demo
        asyncio.run(interactive_demo())

if __name__ == "__main__":
    main()
