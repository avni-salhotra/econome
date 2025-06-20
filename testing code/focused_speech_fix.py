#!/usr/bin/env python3
"""
FOCUSED: Get Google Speech-to-Text working ASAP
Systematic debugging approach based on research findings
"""

import os
import time
import wave
import numpy as np
import sounddevice as sd
from google.cloud import speech_v1 as speech
from google.oauth2 import service_account

def test_1_basic_sync_with_real_speech():
    """Test 1: Sync API with real microphone speech"""
    print("🧪 TEST 1: Sync API with Real Speech")
    print("-" * 40)
    
    try:
        # Initialize client
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        client = speech.SpeechClient(credentials=credentials)
        
        # Record real speech
        duration = 5
        sample_rate = 16000
        
        print(f"🎤 Recording {duration} seconds... Say something clearly!")
        print("   Try: 'Hello Google, this is a test of speech recognition'")
        
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()
        
        print("⏹️ Recording complete, processing...")
        
        # Configure for best results
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="latest_short",  # Best for short speech
            enable_automatic_punctuation=True
        )
        
        audio_bytes = audio_data.tobytes()
        
        request = speech.RecognizeRequest(
            config=config,
            audio=speech.RecognitionAudio(content=audio_bytes)
        )
        
        response = client.recognize(request=request)
        
        if response.results:
            print("✅ SYNC API WORKS!")
            for result in response.results:
                transcript = result.alternatives[0].transcript
                confidence = result.alternatives[0].confidence
                print(f"   Transcript: '{transcript}'")
                print(f"   Confidence: {confidence:.3f}")
            return True
        else:
            print("❌ No speech detected in recording")
            return False
            
    except Exception as e:
        print(f"❌ Sync test failed: {e}")
        return False

def test_2_streaming_with_real_speech():
    """Test 2: Streaming API with real microphone speech"""
    print("\n🧪 TEST 2: Streaming API with Real Speech")
    print("-" * 40)
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        client = speech.SpeechClient(credentials=credentials)
        
        # Record speech first
        duration = 6
        sample_rate = 16000
        
        print(f"🎤 Recording {duration} seconds for streaming test...")
        print("   Say: 'This is a streaming test. John will send the report by Friday.'")
        
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()
        
        print("📡 Testing streaming recognition...")
        
        # Optimal streaming config based on Google docs
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="latest_short",
            enable_automatic_punctuation=True
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False
        )
        
        def create_requests():
            """Generate streaming requests with proper timing"""
            audio_bytes = audio_data.tobytes()
            
            # Send in 200ms chunks (3200 bytes at 16kHz)
            chunk_size = 3200
            
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                print(f"   📤 Sending chunk {(i//chunk_size)+1} ({len(chunk)} bytes)")
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                time.sleep(0.2)  # Critical: real-time timing
        
        # Stream the requests
        responses = client.streaming_recognize(streaming_config, create_requests())
        
        response_count = 0
        final_transcripts = []
        
        for response in responses:
            response_count += 1
            print(f"   📨 Response {response_count}")
            
            if response.results:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        confidence = result.alternatives[0].confidence
                        is_final = result.is_final
                        
                        status = "FINAL" if is_final else "interim"
                        print(f"      [{status}] '{transcript}' (conf: {confidence:.3f})")
                        
                        if is_final:
                            final_transcripts.append(transcript)
            else:
                print(f"      No results in response {response_count}")
        
        print(f"\n📊 Streaming Results:")
        print(f"   Total responses: {response_count}")
        print(f"   Final transcripts: {final_transcripts}")
        
        success = len(final_transcripts) > 0
        if success:
            print("✅ STREAMING API WORKS!")
        else:
            print("❌ Streaming API: No final transcripts")
        
        return success
        
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_3_streaming_live_microphone():
    """Test 3: True live streaming from microphone"""
    print("\n🧪 TEST 3: Live Streaming from Microphone")
    print("-" * 40)
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        client = speech.SpeechClient(credentials=credentials)
        
        # Live streaming config
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="latest_short"
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False
        )
        
        print("🎤 Starting live microphone streaming...")
        print("   Speak for 10 seconds, then we'll stop")
        print("   Try: 'Hello Google. This is a live streaming test.'")
        
        def audio_generator():
            """Generate live audio from microphone"""
            chunk_size = 1600  # 100ms chunks
            sample_rate = 16000
            
            with sd.InputStream(samplerate=sample_rate, channels=1, 
                              dtype=np.int16, blocksize=chunk_size) as stream:
                
                for i in range(100):  # 10 seconds worth
                    audio_chunk, _ = stream.read(chunk_size)
                    yield speech.StreamingRecognizeRequest(
                        audio_content=audio_chunk.tobytes()
                    )
                    time.sleep(0.05)  # Slight delay to prevent overwhelming
        
        # Start streaming
        responses = client.streaming_recognize(streaming_config, audio_generator())
        
        response_count = 0
        transcripts = []
        
        start_time = time.time()
        
        for response in responses:
            response_count += 1
            elapsed = time.time() - start_time
            
            print(f"   📨 Response {response_count} at {elapsed:.1f}s")
            
            if response.results:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        is_final = result.is_final
                        
                        if transcript.strip():
                            status = "FINAL" if is_final else "interim"
                            print(f"      [{status}] '{transcript}'")
                            
                            if is_final:
                                transcripts.append(transcript)
            
            # Stop after 10 seconds
            if elapsed > 10:
                break
        
        print(f"\n📊 Live Streaming Results:")
        print(f"   Responses: {response_count}")
        print(f"   Final transcripts: {transcripts}")
        
        success = len(transcripts) > 0
        if success:
            print("✅ LIVE STREAMING WORKS!")
        else:
            print("❌ Live streaming: No transcripts")
        
        return success
        
    except Exception as e:
        print(f"❌ Live streaming failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_4_pseudo_realtime_chunking():
    """Test 4: Pseudo real-time using sync API with chunks"""
    print("\n🧪 TEST 4: Pseudo Real-time (Sync API + Chunks)")
    print("-" * 40)
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        client = speech.SpeechClient(credentials=credentials)
        
        print("🎤 Recording 8 seconds, will process in 2-second chunks...")
        print("   Say: 'First chunk here. Second chunk here. Third chunk here. Fourth chunk done.'")
        
        duration = 8
        sample_rate = 16000
        
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16
        )
        sd.wait()
        
        print("📡 Processing in 2-second chunks...")
        
        # Split into 2-second chunks
        chunk_duration = 2  # seconds
        chunk_samples = chunk_duration * sample_rate
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="latest_short"
        )
        
        transcripts = []
        
        for i in range(0, len(audio_data), chunk_samples):
            chunk_num = (i // chunk_samples) + 1
            chunk = audio_data[i:i+chunk_samples]
            
            if len(chunk) < chunk_samples // 2:  # Skip very short chunks
                continue
            
            print(f"   📤 Processing chunk {chunk_num}...")
            
            request = speech.RecognizeRequest(
                config=config,
                audio=speech.RecognitionAudio(content=chunk.tobytes())
            )
            
            response = client.recognize(request=request)
            
            if response.results:
                for result in response.results:
                    transcript = result.alternatives[0].transcript
                    confidence = result.alternatives[0].confidence
                    print(f"      ✅ Chunk {chunk_num}: '{transcript}' (conf: {confidence:.3f})")
                    transcripts.append(f"Chunk {chunk_num}: {transcript}")
            else:
                print(f"      ⚠️ Chunk {chunk_num}: No speech detected")
        
        print(f"\n📊 Pseudo Real-time Results:")
        print(f"   Chunks processed: {len(transcripts)}")
        for transcript in transcripts:
            print(f"   • {transcript}")
        
        success = len(transcripts) > 0
        if success:
            print("✅ PSEUDO REAL-TIME WORKS!")
        else:
            print("❌ Pseudo real-time: No transcripts")
        
        return success
        
    except Exception as e:
        print(f"❌ Pseudo real-time failed: {e}")
        return False

def run_focused_speech_debugging():
    """Run systematic debugging to get Speech API working"""
    
    print("🎯 FOCUSED: Google Speech-to-Text Debugging")
    print("=" * 60)
    print("Goal: Get speech recognition working for your multi-agent system")
    print("=" * 60)
    
    results = {}
    
    # Test each approach systematically
    results['sync'] = test_1_basic_sync_with_real_speech()
    results['streaming'] = test_2_streaming_with_real_speech()
    results['live'] = test_3_streaming_live_microphone()
    results['pseudo'] = test_4_pseudo_realtime_chunking()
    
    # Analysis and recommendations
    print("\n" + "=" * 60)
    print("📊 DEBUGGING RESULTS:")
    print("=" * 60)
    
    for test, worked in results.items():
        status = "✅ WORKS" if worked else "❌ FAILED"
        print(f"  {test.upper()}: {status}")
    
    print("\n🎯 RECOMMENDATIONS FOR YOUR MULTI-AGENT SYSTEM:")
    
    if results['streaming'] or results['live']:
        print("🏆 STREAMING WORKS! You can build real-time conversation intelligence!")
        print("   • Use streaming API for your TranscriptAgent")
        print("   • Real-time processing for your existing architecture")
        
    elif results['sync']:
        print("✅ SYNC WORKS! Use pseudo-real-time approach:")
        print("   • Process audio in 2-second chunks with sync API")
        print("   • Still feels real-time to users")
        print("   • Perfect for your multi-agent pipeline")
        
    elif results['pseudo']:
        print("✅ PSEUDO REAL-TIME WORKS!")
        print("   • Chunk-based processing confirmed")
        print("   • Integrate with your existing agents")
        
    else:
        print("🔍 ALL TESTS FAILED - Deeper issue exists")
        print("   • Check Google Cloud project settings")
        print("   • Verify Speech API is enabled")
        print("   • Contact Google Cloud support")
    
    print(f"\n⚡ NEXT STEP: Integrate working approach with your multi-agent system!")
    
    return results

if __name__ == "__main__":
    # Check dependencies
    try:
        import sounddevice
        print("✅ sounddevice available")
    except ImportError:
        print("❌ Install sounddevice: pip install sounddevice")
        exit(1)
    
    # Run debugging
    run_focused_speech_debugging()
