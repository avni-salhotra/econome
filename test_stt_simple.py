#!/usr/bin/env python3
"""
Simple STT Testing Script
Test the accuracy of your speech-to-text transcription
"""

from speech_agent import ProductionSTTServiceV2
import time

def test_stt_accuracy():
    """Simple test to verify STT transcript accuracy"""
    
    print("🎤 STT Accuracy Test")
    print("=" * 40)
    
    # Initialize STT service
    stt = ProductionSTTServiceV2(chunk_duration=2.0)
    
    # Store transcripts for review
    transcripts = []
    
    def on_transcript(segment):
        transcript_line = f"[{segment.speaker_id}] {segment.text}"
        transcripts.append(transcript_line)
        print(f"📝 {transcript_line} (confidence: {segment.confidence:.3f})")
    
    # Set up callback
    stt.set_transcript_callback(on_transcript)
    
    print("\n🎯 Test Instructions:")
    print("1. Press ENTER to start recording")
    print("2. Speak clearly for 15 seconds")
    print("3. Try saying something like:")
    print("   'Hello, my name is [your name]. Today is a great day for testing speech recognition.'")
    print("   'The quick brown fox jumps over the lazy dog.'")
    print("   'John will send the proposal by Friday afternoon.'")
    
    input("\nPress ENTER to start 15-second recording...")
    
    # Start recording
    print("\n🔴 RECORDING STARTED - Speak clearly now!")
    result = stt.start_recording()
    
    if not result.get("success"):
        print(f"❌ Failed to start recording: {result.get('message')}")
        return
    
    # Record for 15 seconds
    for i in range(15, 0, -1):
        print(f"⏰ {i} seconds remaining...", end="\r")
        time.sleep(1)
    
    print("\n🔴 STOPPING RECORDING...")
    
    # Stop recording
    stop_result = stt.stop_recording()
    
    # Get final results
    final_transcript = stt.get_transcript("full")
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    
    print(f"✅ Recording Status: {stop_result.get('message', 'Unknown')}")
    print(f"📊 Duration: {stop_result.get('session_duration', 'Unknown')}")
    print(f"🎭 Speakers Detected: {stop_result.get('speakers_detected', 0)}")
    print(f"📝 Total Segments: {stop_result.get('segments_captured', 0)}")
    
    print(f"\n📄 FULL TRANSCRIPT:")
    print("-" * 40)
    if final_transcript.get("transcript"):
        print(final_transcript["transcript"])
    else:
        print("No transcript generated")
    
    print(f"\n📋 SEGMENT-BY-SEGMENT BREAKDOWN:")
    print("-" * 40)
    if transcripts:
        for i, transcript in enumerate(transcripts, 1):
            print(f"{i:2d}. {transcript}")
    else:
        print("No segments captured")
    
    print(f"\n🎯 ACCURACY EVALUATION:")
    print("Please manually review the transcript above and check:")
    print("✓ Are the words correct?")
    print("✓ Is punctuation appropriate?") 
    print("✓ Did it correctly identify multiple speakers?")
    print("✓ How's the overall quality?")
    
    # Save transcript for review
    if final_transcript.get("transcript"):
        filename = f"test_transcript_{int(time.time())}.txt"
        try:
            with open(filename, 'w') as f:
                f.write("STT Accuracy Test Results\n")
                f.write("=" * 40 + "\n\n")
                f.write("Full Transcript:\n")
                f.write(final_transcript["transcript"])
                f.write("\n\nSegment Breakdown:\n")
                for transcript in transcripts:
                    f.write(f"{transcript}\n")
            print(f"\n💾 Transcript saved to: {filename}")
        except Exception as e:
            print(f"⚠️ Could not save transcript: {e}")

if __name__ == "__main__":
    test_stt_accuracy()
