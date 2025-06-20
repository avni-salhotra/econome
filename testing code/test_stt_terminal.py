#!/usr/bin/env python3
"""
Terminal-based STT Testing Interface
Clean, fault-tolerant testing for ProductionStreamingSTTAgent
"""

import time
import threading
import sys
import os
from typing import Dict, Any
from speech_agent import ProductionStreamingSTTAgent

class STTTerminalTester:
    """Clean terminal interface for testing real-time STT"""
    
    def __init__(self):
        self.agent = ProductionStreamingSTTAgent()
        self.monitoring = False
        self.monitor_thread = None
    
    def print_header(self):
        """Print clean header"""
        print("\n" + "="*60)
        print("🎤 REAL-TIME STT TESTING TERMINAL")
        print("="*60)
        print("Agent:", self.agent.name)
        print("Ready for live audio testing...")
        print("="*60 + "\n")
    
    def print_commands(self):
        """Show available commands"""
        print("COMMANDS:")
        print("  start    - Start live recording")
        print("  stop     - Stop recording")
        print("  status   - Show current status")
        print("  save     - Save transcript to file")
        print("  monitor  - Toggle live status monitoring")
        print("  clear    - Clear screen")
        print("  help     - Show this help")
        print("  quit     - Exit tester")
        print()
    
    def execute_command(self, command: str) -> bool:
        """Execute user command, return False to quit"""
        cmd_parts = command.strip().lower().split()
        if not cmd_parts:
            return True
            
        cmd = cmd_parts[0]
        
        if cmd in ['quit', 'exit', 'q']:
            return False
            
        elif cmd == 'start':
            self.start_recording()
            
        elif cmd == 'stop':
            self.stop_recording()
            
        elif cmd == 'status':
            self.show_status()
            
        elif cmd == 'save':
            filename = cmd_parts[1] if len(cmd_parts) > 1 else None
            self.save_transcript(filename)
            
        elif cmd == 'monitor':
            self.toggle_monitoring()
            
        elif cmd == 'clear':
            os.system('clear' if os.name == 'posix' else 'cls')
            self.print_header()
            
        elif cmd in ['help', 'h']:
            self.print_commands()
            
        else:
            print(f"❌ Unknown command: {cmd}")
            print("Type 'help' for available commands")
        
        return True
    
    def start_recording(self):
        """Start recording with user feedback"""
        print("🎤 Starting live recording...")
        result = self.agent.process({"action": "start"})
        
        if result["status"] == "success":
            print("✅ RECORDING STARTED")
            print(f"   • Sample rate: {result['sample_rate']} Hz")
            print(f"   • Channels: {result['channels']}")
            print(f"   • Session limit: {result['session_limit']}")
            print("\n🎯 Speak now - your audio will be transcribed in real-time!")
            print("   Type 'stop' when finished, or 'monitor' to see live updates")
            
            # Auto-start monitoring for immediate feedback
            if not self.monitoring:
                self.toggle_monitoring()
                
        else:
            print(f"❌ Failed to start: {result['message']}")
    
    def stop_recording(self):
        """Stop recording with summary"""
        print("\n⏹️ Stopping recording...")
        result = self.agent.process({"action": "stop"})
        
        # Stop monitoring
        if self.monitoring:
            self.toggle_monitoring()
        
        if result["status"] == "success":
            print("✅ RECORDING STOPPED")
            print(f"   • Duration: {result['session_duration']}")
            print(f"   • Sessions: {result['total_sessions']}")
            print(f"   • Speakers: {result['speakers_detected']}")
            print(f"   • Segments: {result['total_segments']}")
            
            # Show final transcript
            if result.get("final_transcript"):
                print("\n📝 FINAL TRANSCRIPT:")
                print("-" * 40)
                print(result["final_transcript"])
                print("-" * 40)
                print("💡 Type 'save' to save transcript to file")
            else:
                print("\n⚠️ No transcript captured")
                
        else:
            print(f"❌ Error stopping: {result['message']}")
    
    def show_status(self):
        """Show detailed status"""
        result = self.agent.process({"action": "status"})
        
        print("\n📊 CURRENT STATUS:")
        print("-" * 30)
        print(f"Recording: {'🔴 ACTIVE' if result['is_recording'] else '⚫ STOPPED'}")
        
        if result['is_recording']:
            print(f"Duration: {result['session_duration']} / {result['session_limit']}")
            print(f"Session: #{result['current_session']}")
            print(f"Queue size: {result['queue_size']}")
            print(f"Speakers: {result['speakers_detected']}")
            print(f"Segments: {result['total_segments']}")
            
            # Health status
            health = result.get('session_health', {})
            if health:
                print(f"Queue health: {health.get('queue_health', 'unknown')}")
                print(f"Session health: {health.get('session_health', 'unknown')}")
            
            # Recent transcript chunks
            recent = result.get('recent_segments', [])
            if recent:
                print("\n💬 RECENT SEGMENTS:")
                for seg in recent[-3:]:  # Last 3
                    speaker = seg.get('speaker', 'Unknown')
                    text = seg.get('text', '')[:60] + "..." if len(seg.get('text', '')) > 60 else seg.get('text', '')
                    print(f"   Speaker {speaker}: {text}")
        
        print("-" * 30)
    
    def save_transcript(self, filename: str = None):
        """Save transcript to file"""
        result = self.agent.process({"action": "save", "filename": filename})
        
        if result["status"] == "success":
            print(f"✅ Transcript saved: {result['filename']}")
            print(f"   Length: {result['transcript_length']} characters")
        else:
            print(f"❌ Save failed: {result['message']}")
    
    def toggle_monitoring(self):
        """Toggle live status monitoring"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1.0)
            print("🔕 Live monitoring OFF")
        else:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("🔔 Live monitoring ON - showing real-time updates...")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        last_segment_count = 0
        
        while self.monitoring:
            try:
                status = self.agent.process({"action": "status"})
                
                if status['is_recording']:
                    # Show new segments
                    current_count = status.get('total_segments', 0)
                    if current_count > last_segment_count:
                        recent = status.get('recent_segments', [])
                        if recent:
                            # Show the newest segment
                            newest = recent[-1]
                            speaker = newest.get('speaker', 'Unknown')
                            text = newest.get('text', '')
                            confidence = newest.get('confidence', 0)
                            print(f"🎭 Speaker {speaker}: {text} ({confidence:.2f})")
                        last_segment_count = current_count
                    
                    # Show session restart warnings
                    health = status.get('session_health', {})
                    if health.get('session_health') == 'restarting_soon':
                        print("⏰ Session will restart soon...")
                
                time.sleep(2.0)  # Update every 2 seconds
                
            except Exception as e:
                print(f"⚠️ Monitor error: {e}")
                time.sleep(1.0)
    
    def cleanup(self):
        """Clean shutdown"""
        print("\n🧹 Cleaning up...")
        
        # Stop monitoring
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1.0)
        
        # Stop recording if active
        status = self.agent.process({"action": "status"})
        if status.get('is_recording'):
            print("Stopping active recording...")
            self.agent.process({"action": "stop"})
        
        print("✅ Cleanup complete")
    
    def run(self):
        """Main testing loop"""
        self.print_header()
        self.print_commands()
        
        try:
            while True:
                try:
                    # Get user input
                    command = input("STT> ").strip()
                    
                    if not command:
                        continue
                    
                    # Execute command
                    if not self.execute_command(command):
                        break
                        
                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    break
                except EOFError:
                    print("\n\n⚠️ End of input")
                    break
                    
        finally:
            self.cleanup()
            print("\n👋 STT Tester finished. Goodbye!")

def main():
    """Entry point"""
    print("Initializing STT Terminal Tester...")
    
    try:
        tester = STTTerminalTester()
        tester.run()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
