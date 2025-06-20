#!/usr/bin/env python3
"""
Fixed minimal V1 streaming test with proper service account authentication
"""
import os
import time
import numpy as np
from google.cloud import speech_v1 as speech
from google.oauth2 import service_account

def minimal_v1_streaming_test():
    """Test the minimal streaming case with proper authentication"""
    try:
        print("🧪 Minimal V1 Streaming Test with Service Account")
        
        # Load service account credentials explicitly
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        
        # Initialize client with explicit credentials
        client = speech.SpeechClient(credentials=credentials)
        print("✅ V1 client created with service account")
        
        # Create minimal config
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            model="default",  # Explicitly specify model
            use_enhanced=True  # Try enhanced model
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,   # Enable interim results for more feedback
            single_utterance=False  # Don't stop after one utterance
        )
        
        print(f"📋 Config: {streaming_config}")
        
        # Create audio request generator with real audio data
        def audio_requests():
            print("🎵 Generating test audio...")
            
            # Generate a more complex audio signal
            duration = 2.0
            sample_rate = 16000
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            # Create a sweep from 200Hz to 800Hz (more speech-like)
            frequency_start = 200
            frequency_end = 800
            frequency = np.linspace(frequency_start, frequency_end, len(t))
            tone = np.sin(2 * np.pi * np.cumsum(frequency) / sample_rate) * 0.3
            
            # Add some noise to make it more realistic
            noise = np.random.normal(0, 0.05, len(tone))
            signal = (tone + noise) * 32767
            audio_data = signal.astype(np.int16).tobytes()
            
            # Send in realistic chunks (100ms each)
            chunk_size = 3200  # 100ms at 16kHz, 16-bit
            total_chunks = len(audio_data) // chunk_size
            
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                chunk_num = i // chunk_size + 1
                print(f"📡 Sending chunk {chunk_num}/{total_chunks}, size: {len(chunk)} bytes")
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
                time.sleep(0.1)  # Simulate real-time streaming
        
        print("🚀 Starting streaming recognition...")
        
        # Time the call
        start_time = time.time()
        
        # Use the streaming recognize method
        responses = client.streaming_recognize(streaming_config, audio_requests())
        
        print("📻 Got response iterator, processing responses...")
        
        response_count = 0
        final_results = []
        
        try:
            for response in responses:
                response_count += 1
                elapsed = time.time() - start_time
                
                print(f"📨 Response #{response_count} (t={elapsed:.2f}s):")
                
                if response.results:
                    for i, result in enumerate(response.results):
                        if result.alternatives:
                            transcript = result.alternatives[0].transcript
                            confidence = result.alternatives[0].confidence
                            is_final = result.is_final
                            
                            status = "FINAL" if is_final else "interim"
                            print(f"  Result {i+1} [{status}]: '{transcript}' (confidence: {confidence:.3f})")
                            
                            if is_final:
                                final_results.append(transcript)
                else:
                    print(f"  No results in response")
                    print(f"  Raw response: {response}")
                
                # Break if it takes too long
                if elapsed > 15:
                    print("⏰ Breaking after 15 seconds")
                    break
                    
        except Exception as iter_error:
            print(f"❌ Error during iteration: {iter_error}")
            import traceback
            traceback.print_exc()
            
        elapsed = time.time() - start_time
        print(f"⏱️ Total time: {elapsed:.2f}s")
        print(f"📊 Response count: {response_count}")
        print(f"🎯 Final results: {final_results}")
        
        success = response_count > 0
        if success:
            print("✅ Streaming API responded!")
        else:
            print("❌ No responses received")
            
        return success
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    works = minimal_v1_streaming_test()
    if works:
        print("\n🎉 V1 MINIMAL STREAMING WORKS!")
    else:
        print("\n❌ V1 streaming still fails")
