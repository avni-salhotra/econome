#!/usr/bin/env python3
"""
Test with actual audio file to eliminate audio generation issues
"""
import os
import wave
import time
from google.cloud import speech_v1 as speech
from google.oauth2 import service_account

def create_test_wav_file():
    """Create a simple WAV file with the correct format"""
    import numpy as np
    
    # Audio parameters
    sample_rate = 16000
    duration = 2.0  # seconds
    frequency = 440  # A4 note
    
    # Generate audio data
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.3
    
    # Convert to 16-bit PCM
    audio_16bit = (audio_data * 32767).astype(np.int16)
    
    # Write WAV file
    filename = "test_audio.wav"
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_16bit.tobytes())
    
    print(f"✅ Created {filename}: {duration}s, {sample_rate}Hz, 16-bit mono")
    return filename

def test_with_real_audio():
    """Test both sync and streaming with a real WAV file"""
    try:
        # Create test audio file
        audio_file = create_test_wav_file()
        
        # Load service account credentials
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        
        # Initialize client
        client = speech.SpeechClient(credentials=credentials)
        print("✅ Speech client initialized")
        
        # Read the audio file
        with open(audio_file, 'rb') as f:
            audio_content = f.read()
        
        print(f"📁 Loaded audio file: {len(audio_content)} bytes")
        
        # Test 1: Synchronous recognition
        print("\n🔧 Testing synchronous recognition...")
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="default"
        )
        
        sync_request = speech.RecognizeRequest(
            config=config,
            audio=speech.RecognitionAudio(content=audio_content)
        )
        
        sync_response = client.recognize(request=sync_request)
        print(f"📋 Sync response: {sync_response}")
        
        if sync_response.results:
            print("✅ Sync recognition found results!")
            for result in sync_response.results:
                print(f"  Transcript: '{result.alternatives[0].transcript}'")
                print(f"  Confidence: {result.alternatives[0].confidence}")
        else:
            print("ℹ️ Sync recognition: no speech detected (expected for tone)")
        
        # Test 2: Streaming recognition
        print("\n🔧 Testing streaming recognition...")
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False
        )
        
        def audio_chunks():
            """Stream the audio file in chunks"""
            chunk_size = 3200  # 0.2 seconds
            audio_data = audio_content[44:]  # Skip WAV header
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                print(f"📡 Streaming chunk {i//chunk_size + 1}, size: {len(chunk)}")
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                time.sleep(0.2)  # Real-time simulation
        
        responses = client.streaming_recognize(streaming_config, audio_chunks())
        
        response_count = 0
        for response in responses:
            response_count += 1
            print(f"📨 Streaming response #{response_count}: {response}")
            
            if response.results:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        is_final = result.is_final
                        status = "FINAL" if is_final else "interim"
                        print(f"  [{status}] '{transcript}'")
        
        print(f"\n📊 Streaming test completed: {response_count} responses")
        
        # Cleanup
        os.remove(audio_file)
        print(f"🗑️ Cleaned up {audio_file}")
        
        return response_count > 0
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_speech_from_microphone():
    """Test with very short recorded speech if available"""
    try:
        print("\n🎤 Testing with short speech recording...")
        
        # Try to record a short snippet
        import sounddevice as sd
        import numpy as np
        
        duration = 3  # seconds
        sample_rate = 16000
        
        print(f"🔴 Recording for {duration} seconds... Say something!")
        audio_data = sd.rec(int(duration * sample_rate), 
                           samplerate=sample_rate, 
                           channels=1, 
                           dtype=np.int16)
        sd.wait()  # Wait until recording is finished
        print("⏹️ Recording complete")
        
        # Convert to bytes
        audio_bytes = audio_data.tobytes()
        
        # Load credentials and client
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        client = speech.SpeechClient(credentials=credentials)
        
        # Test streaming with real speech
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="default"
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
            single_utterance=False
        )
        
        def speech_chunks():
            chunk_size = 3200
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                print(f"🗣️ Sending speech chunk {i//chunk_size + 1}")
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                time.sleep(0.2)
        
        print("🎯 Testing streaming with real speech...")
        responses = client.streaming_recognize(streaming_config, speech_chunks())
        
        response_count = 0
        transcripts = []
        
        for response in responses:
            response_count += 1
            print(f"🎤 Speech response #{response_count}: {response}")
            
            if response.results:
                for result in response.results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        confidence = result.alternatives[0].confidence
                        is_final = result.is_final
                        
                        if is_final:
                            transcripts.append(transcript)
                            print(f"✅ FINAL: '{transcript}' (confidence: {confidence:.3f})")
                        else:
                            print(f"⏳ interim: '{transcript}'")
        
        print(f"\n🎯 Speech test results:")
        print(f"  Responses: {response_count}")
        print(f"  Final transcripts: {transcripts}")
        
        return len(transcripts) > 0
        
    except ImportError:
        print("ℹ️ sounddevice not available, skipping microphone test")
        return False
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing with Real Audio Files")
    print("=" * 50)
    
    # Test with generated WAV file
    wav_works = test_with_real_audio()
    
    # Test with microphone if available
    mic_works = test_speech_from_microphone()
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    print(f"  WAV file test: {'✅ WORKS' if wav_works else '❌ FAILED'}")
    print(f"  Microphone test: {'✅ WORKS' if mic_works else '❌ FAILED'}")
    
    if wav_works or mic_works:
        print("\n🎉 STREAMING API IS WORKING!")
    else:
        print("\n💡 CONCLUSION: Streaming API accepts audio but doesn't return transcriptions")
        print("   This confirms your original findings about free trial limitations.")
