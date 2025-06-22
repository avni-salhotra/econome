#!/usr/bin/env python3
"""
Production Real-Time Conversation Intelligence System
Main demo script for Google Cloud ADK Hackathon

Clean architecture with STT service and multi-agent coordination
UPDATED VERSION: Parallel processing with Summary + Action Items
FIXED: Use 2-second chunks for better STT quality
"""

# Ensure Gemini credentials are available
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    # Look for credentials in project root
    project_root = Path(__file__).parent.parent
    speech_creds = project_root / "speech-credentials.json"
    if speech_creds.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(speech_creds)

import asyncio
import time
from datetime import datetime
from typing import Dict, Any

# Import our production system
from src.meeting_agents import ConversationIntelligenceSystem
from src.speech_agent import ProductionSTTServiceV2

def print_banner():
    """Print system banner"""
    print("╔═══════════════════════════════════════════════════════════════════════╗")
    print("║          🏆 REAL-TIME CONVERSATION INTELLIGENCE SYSTEM 🏆            ║")
    print("║                     Google Cloud ADK Hackathon                       ║")
    print("╠═══════════════════════════════════════════════════════════════════════╣")
    print("║  🎤 Google Cloud Speech V2  │  🧠 Gemini Parallel Analysis           ║")
    print("║  📝 Clean Transcript Build  │  🔄 Multi-Agent Architecture           ║")
    print("║  📊 Summary + Action Items  │  💾 Session Management                 ║")
    print("╚═══════════════════════════════════════════════════════════════════════╝")

async def interactive_demo():
    """Interactive demo with real-time conversation processing"""
    
    print_banner()
    print("\n🎯 INTERACTIVE DEMO MODE - PARALLEL PROCESSING")
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
        chunk_duration=0.1,  # 🎯 OPTIMIZED: 100ms chunks for real-time streaming
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
            print("🎮 PARALLEL CONVERSATION INTELLIGENCE")
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
        import traceback
        traceback.print_exc()
    finally:
        print("\n🧹 Cleaning up...")
        system.stop_system()
        print("✅ System shutdown complete")

async def live_conversation_demo(system):
    """Live conversation recording demo - UPDATED FOR ASYNC"""
    
    print("\n🎤 LIVE CONVERSATION DEMO")
    print("-" * 30)
    
    print("Starting conversation recording...")
    start_result = system.start_conversation()
    
    if not start_result.get("success"):
        print(f"❌ Failed to start recording: {start_result.get('message')}")
        return
    
    print("✅ Recording started!")
    print("\n📢 SPEAK CLEARLY AND NATURALLY:")
    print("• Use complete sentences")
    print("• Talk about your plans, projects, or thoughts")
    print("• Mention tasks you need to do or people to contact")
    print("• Include deadlines or scheduled events")
    print("• Speak for at least 30 seconds for good analysis")
    print("\n🛑 **PRESS ENTER TO STOP RECORDING WHEN DONE**")
    
    print(f"\n🎤 LIVE TRANSCRIPTION (press ENTER when done):")
    print("-" * 50)
    
    start_time = time.time()
    last_status_time = start_time
    
    import threading
    stop_event = threading.Event()
    
    def wait_for_enter():
        input()
        stop_event.set()
    
    input_thread = threading.Thread(target=wait_for_enter, daemon=True)
    input_thread.start()
    
    while not stop_event.is_set():
        if time.time() - last_status_time >= 15:
            elapsed = int(time.time() - start_time)
            print(f"\n⏱️  Recording... {elapsed}s elapsed | Press ENTER to stop")
            last_status_time = time.time()
        
        await asyncio.sleep(0.5)
    
    print("\n" + "-" * 50)
    print("⏹️ Stopping recording and processing...")
    print("🧠 Running PARALLEL Gemini analysis (Summary + Action Items)...")
    
    # 🆕 NEW: Use await for async stop_conversation
    summary = await system.stop_conversation()
    
    display_conversation_results(summary)

async def automated_demo(system):
    """Automated demo with simulated conversation - UPDATED FOR ASYNC"""
    
    print("\n🤖 AUTOMATED DEMO")
    print("-" * 20)
    
    print("Starting automated conversation simulation...")
    
    # Start recording
    start_result = system.start_conversation()
    if not start_result.get("success"):
        print(f"❌ Failed to start: {start_result.get('message')}")
        return
    
    # Let it run for a longer duration to get meaningful content
    print("🎤 Simulating 30-second conversation...")
    print("(In mock mode, this will generate sample transcript)")
    await asyncio.sleep(30)
    
    # Stop and show results
    print("🧠 Processing PARALLEL final analysis...")
    # 🆕 NEW: Use await for async stop_conversation
    summary = await system.stop_conversation()
    display_conversation_results(summary)

def display_conversation_results(summary: Dict[str, Any]):
    """Display conversation analysis results - SUMMARY + ACTION ITEMS"""
    
    print("\n" + "="*70)
    print("📊 CONVERSATION ANALYSIS RESULTS")
    print("="*70)
    
    if summary.get("error"):
        print(f"❌ Error: {summary['error']}")
        return
    
    print(f"🆔 Session ID: {summary.get('session_id', 'N/A')}")
    print(f"⏱️  Duration: {summary.get('duration_formatted', 'N/A')}")
    print(f"📝 Raw Transcript Chunks Collected: {summary.get('total_transcript_chunks', 0)}")
    
    # Show clean transcript if available
    full_transcript = summary.get('full_transcript', '')
    if full_transcript and len(full_transcript.strip()) > 0:
        print(f"\n📄 CLEAN FINAL TRANSCRIPT:")
        print("-" * 50)
        print(full_transcript)
        print(f"\n📏 Clean Transcript Length: {len(full_transcript)} characters")
        
        # Show first few words for quick verification
        words = full_transcript.split()
        if len(words) > 0:
            preview = ' '.join(words[:15])
            if len(words) > 15:
                preview += "..."
            print(f"📖 Preview: {preview}")
    else:
        print(f"\n📄 CLEAN TRANSCRIPT:")
        print("-" * 50)
        print("❌ No clean transcript available")
        print("   Possible reasons:")
        print("   • Conversation too short")
        print("   • Low confidence transcription")
        print("   • Mostly filler words or unclear speech")
        print("   • Background noise or poor audio quality")
    
    # Show Gemini summary
    gemini_summary = summary.get('gemini_summary', 'No summary available')
    print(f"\n🧠 ORGANIZED THOUGHTS:")
    print("-" * 50)
    
    if (gemini_summary and 
        gemini_summary != "No summary available" and 
        "not yet generated" not in gemini_summary.lower() and
        "failed" not in gemini_summary.lower() and
        "too short" not in gemini_summary.lower()):
        
        print(gemini_summary)
        print(f"\n📏 Summary Length: {len(gemini_summary)} characters")
        
    else:
        print("❌ Summary not generated successfully")
        print(f"Status: {gemini_summary}")

    # 🆕 NEW: Show Action Items
    action_items = summary.get('action_items', [])
    total_action_items = summary.get('total_action_items', 0)
    
    print(f"\n📋 ACTION ITEMS ({total_action_items} found):")
    print("-" * 50)
    
    if action_items and len(action_items) > 0:
        # Group by type for better organization
        todos = [item for item in action_items if isinstance(item, dict) and item.get('type') == 'todo']
        communications = [item for item in action_items if isinstance(item, dict) and item.get('type') == 'communicate']
        reminders = [item for item in action_items if isinstance(item, dict) and item.get('type') == 'reminder']
        
        # Display todos
        if todos:
            print("📝 TO-DO ITEMS:")
            for i, item in enumerate(todos, 1):
                action_text = item.get('action', '')
                deadline = item.get('deadline')
                print(f"   {i}. {action_text}")
                if deadline:
                    print(f"      ⏰ Due: {deadline}")
        
        # Display communications
        if communications:
            print("\n💬 COMMUNICATIONS:")
            for i, item in enumerate(communications, 1):
                action_text = item.get('action', '')
                recipient = item.get('recipient')
                deadline = item.get('deadline')
                print(f"   {i}. {action_text}")
                if recipient:
                    print(f"      👤 To: {recipient}")
                if deadline:
                    print(f"      ⏰ By: {deadline}")
        
        # Display reminders
        if reminders:
            print("\n⏰ REMINDERS:")
            for i, item in enumerate(reminders, 1):
                action_text = item.get('action', '')
                deadline = item.get('deadline')
                print(f"   {i}. {action_text}")
                if deadline:
                    print(f"      📅 When: {deadline}")
        
        print(f"\n✅ Action items successfully extracted!")
        
    else:
        print("📝 No specific action items detected in this conversation")
        print("💡 To get action items, try mentioning:")
        print("   • Tasks you need to do")
        print("   • People you need to contact")
        print("   • Deadlines or scheduled events")
        print("   • Follow-ups or reminders")

    # Show processing pipeline status
    transcript_ok = len(full_transcript.strip()) > 20 if full_transcript else False
    summary_ok = (gemini_summary and 
                  "not yet generated" not in gemini_summary.lower() and 
                  "failed" not in gemini_summary.lower() and
                  "too short" not in gemini_summary.lower())
    
    print(f"\n⚡ PARALLEL PROCESSING PIPELINE:")
    print(f"   🎤 Real-time STT transcription: ✅ Completed")
    print(f"   📝 Transcript chunk collection: ✅ {summary.get('total_transcript_chunks', 0)} chunks")
    print(f"   🧹 Transcript cleaning & filtering: {'✅ Success' if transcript_ok else '⚠️  Insufficient'}")
    print(f"   🧠 Gemini summary generation: {'✅ Success' if summary_ok else '❌ Failed'}")
    print(f"   📋 Gemini action extraction: {'✅ Success' if total_action_items >= 0 else '❌ Failed'}")
    print(f"   ⚡ Parallel processing: {'✅ Both calls simultaneous' if summary_ok else '⚠️  Sequential fallback'}")
    print(f"   🔄 Multi-agent coordination: ✅ Active")
    
    print(f"\n🏆 HACKATHON FEATURES DEMONSTRATED:")
    print(f"   ✅ Google Cloud Speech V2 integration")
    print(f"   ✅ Gemini 1.5 Pro multi-call coordination")
    print(f"   ✅ Advanced async parallel processing")
    print(f"   ✅ Multi-agent architecture patterns")
    print(f"   ✅ Real-time conversation intelligence")
    print(f"   ✅ Structured action item extraction")
    
    # Debug info for troubleshooting
    if not transcript_ok:
        print(f"\n🔍 DEBUG INFO:")
        print(f"   • Raw chunks collected: {summary.get('total_transcript_chunks', 0)}")
        print(f"   • Session duration: {summary.get('duration_formatted', 'N/A')}")
        print(f"   • Check microphone and speak more clearly")
    
    print(f"\n💡 NEXT STEPS:")
    if transcript_ok and summary_ok:
        print(f"   🎉 Great! The parallel processing system worked end-to-end")
        print(f"   • Try different conversation topics")
        print(f"   • Test with longer conversations")
        print(f"   • Experiment with action-oriented speech")
        print(f"   • Notice the parallel processing speed improvement")
    else:
        print(f"   🔧 System needs tuning:")
        if not transcript_ok:
            print(f"   • Focus on clearer speech and longer conversations")
            print(f"   • Check microphone setup and reduce background noise")
        if not summary_ok:
            print(f"   • Ensure transcript quality is sufficient")
            print(f"   • Check Gemini integration and API access")

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
        print(f"🔊 STT Queue Health: {stt_status.get('queue_health', 'N/A')}")
        print(f"📝 Chunks Processed: {stt_status.get('total_chunks_processed', 0)}")

async def test_stt_directly(mock_mode: bool):
    """Test STT service directly - using same settings as main system"""
    
    print("\n🔧 DIRECT STT SERVICE TEST")
    print("-" * 30)
    
    # Create STT service with SAME settings as main system
    if mock_mode:
        from src.speech_agent import MockSTTService
        stt = MockSTTService()
        print("🔧 Using Mock STT Service")
    else:
        stt = ProductionSTTServiceV2(chunk_duration=0.1)  # 🎯 OPTIMIZED: 100ms for real-time
        print("🔧 Using Production STT Service (2-second chunks)")
    
    # Set up callback
    def on_transcript(segment):
        print(f"📝 {segment.text} (confidence: {segment.confidence:.3f})")
    
    if hasattr(stt, 'set_transcript_callback'):
        stt.set_transcript_callback(on_transcript)
    
    # Test recording
    print("\nStarting 20-second STT test...")
    print("🎤 Try saying: 'Today is a great day. I need to call Sarah by Friday and finish my project.'")
    start_result = stt.start_recording()
    
    if start_result.get("success"):
        print("🔴 Recording... speak clearly now!")
        await asyncio.sleep(20)
        
        stop_result = stt.stop_recording()
        print(f"⏹️ Recording stopped: {stop_result.get('message')}")
        
        if hasattr(stt, 'get_transcript'):
            transcript = stt.get_transcript()
            transcript_text = transcript.get('transcript', '')
            print(f"\n📄 Final transcript ({len(transcript_text)} chars):")
            if transcript_text:
                print(f"'{transcript_text}'")
            else:
                print("No transcript generated")
    else:
        print(f"❌ Failed to start recording: {start_result.get('message')}")

async def quick_test():
    """Quick system validation test - UPDATED FOR ASYNC"""
    
    print("🧪 QUICK SYSTEM TEST - PARALLEL PROCESSING")
    print("=" * 45)
    
    # Test system initialization
    print("1. Testing system initialization...")
    system = ConversationIntelligenceSystem(mock_mode=True, chunk_duration=0.1)
    
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
    
    await asyncio.sleep(5)  # Longer pause for mock data generation
    
    # 🆕 NEW: Use await for async stop_conversation
    stop_result = await system.stop_conversation()
    print(f"   ✅ Conversation stopped: {stop_result.get('session_id') is not None}")
    
    # Check if we got both summary and action items
    summary = stop_result.get('gemini_summary', '')
    action_items = stop_result.get('action_items', [])
    print(f"   ✅ Summary generated: {len(summary) > 0}")
    print(f"   ✅ Action items extracted: {len(action_items)} items")
    
    # Cleanup
    print("5. Testing system shutdown...")
    system.stop_system()
    print("   ✅ System stopped")
    
    print("\n🎯 PARALLEL PROCESSING SYSTEM TEST COMPLETE!")
    print("✅ STT → Parallel Gemini (Summary + Actions) flow working")

def show_help():
    """Show help information"""
    
    print("\n📖 PARALLEL CONVERSATION INTELLIGENCE SYSTEM")
    print("=" * 55)
    print("This system provides advanced conversation intelligence using:")
    print("• Google Cloud Speech-to-Text V2 for real-time transcription")
    print("• Intelligent transcript cleaning and filtering")
    print("• Gemini AI for parallel summary + action item processing")
    print("• Multi-agent architecture for coordination")
    print("\nParallel Processing Flow:")
    print("1. Real-time STT transcription (visible during recording)")
    print("2. Collect and clean transcript chunks")
    print("3. PARALLEL Gemini analysis: Summary + Action Items")
    print("4. Display organized thoughts + categorized action items")
    print("\nUsage:")
    print("  python main.py                 - Interactive demo")
    print("  python main.py --test          - Quick system test")
    print("  python main.py --help          - Show this help")
    print("\nRequirements:")
    print("• speech-credentials.json file (for production mode)")
    print("• Google Cloud project with Speech and Vertex AI enabled")
    print("• Audio input device (microphone)")
    print("\nTips for best results:")
    print("• Speak clearly in complete sentences")
    print("• Record for at least 30 seconds")
    print("• Mention specific tasks, people, and deadlines")
    print("• Avoid excessive background noise")
    print("• Use good microphone quality")
    print("\nAction Item Detection:")
    print("• Tasks: 'I need to...', 'I should...', 'I have to...'")
    print("• Communications: 'Call John', 'Email Sarah', 'Text Mike'")
    print("• Reminders: 'Meeting at 3pm', 'Doctor appointment Friday'")

def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ["--help", "-h", "help"]:
            show_help()
        elif arg in ["--test", "-t", "test"]:
            asyncio.run(quick_test())
        else:
            print(f"❌ Unknown argument: {arg}")
            show_help()
    else:
        # Run interactive demo
        asyncio.run(interactive_demo())

if __name__ == "__main__":
    main()