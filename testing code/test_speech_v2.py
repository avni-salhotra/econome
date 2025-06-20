#!/usr/bin/env python3
"""
Fixed Speech-to-Text API V2 test with proper model specification
"""
import os
import time
import numpy as np

def test_v2_with_service_account():
    """Test v2 with explicit service account authentication and proper model"""
    try:
        print("🧪 Testing Speech-to-Text V2 with service account...")
        
        # Import v2 with explicit service account
        from google.cloud import speech_v2
        from google.oauth2 import service_account
        
        # Load service account credentials explicitly
        credentials = service_account.Credentials.from_service_account_file(
            "speech-credentials.json"
        )
        
        # Initialize v2 client with explicit credentials
        client = speech_v2.SpeechClient(credentials=credentials)
        print("✅ V2 client created with service account")
        
        # Test simple recognition first
        print("🔧 Testing V2 simple recognition...")
        
        # Create some test audio (sine wave)
        duration = 1.0
        sample_rate = 16000
        frequency = 440
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = (np.sin(frequency * 2 * np.pi * t) * 0.1 * 32767).astype(np.int16)
        audio_content = tone.tobytes()
        
        request = speech_v2.RecognizeRequest(
            recognizer="projects/econome-hackathon/locations/global/recognizers/_",
            config=speech_v2.RecognitionConfig(
                explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                    encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                ),
                language_codes=["en-US"],
                model="latest_long",  # Specify the model explicitly
                features=speech_v2.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                )
            ),
            content=audio_content
        )
        
        response = client.recognize(request=request)
        print(f"✅ V2 recognition successful: {response}")
        
        # Now test streaming
        print("🔧 Testing V2 streaming...")
        
        def request_generator():
            # First request: config only
            yield speech_v2.StreamingRecognizeRequest(
                recognizer="projects/econome-hackathon/locations/global/recognizers/_",
                streaming_config=speech_v2.StreamingRecognitionConfig(
                    config=speech_v2.RecognitionConfig(
                        explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                            encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                            sample_rate_hertz=16000,
                            audio_channel_count=1,
                        ),
                        language_codes=["en-US"],
                        model="latest_short",  # Use short model for streaming
                        features=speech_v2.RecognitionFeatures(
                            enable_automatic_punctuation=True,
                        )
                    ),
                    streaming_features=speech_v2.StreamingRecognitionFeatures(
                        interim_results=True,
                    )
                )
            )
            
            # Generate longer test audio with some variation
            duration = 3.0
            sample_rate = 16000
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            # Mix multiple frequencies to create more interesting audio
            tone1 = np.sin(440 * 2 * np.pi * t) * 0.05
            tone2 = np.sin(880 * 2 * np.pi * t) * 0.03
            tone3 = np.sin(220 * 2 * np.pi * t) * 0.02
            mixed_tone = (tone1 + tone2 + tone3) * 32767
            audio_data = mixed_tone.astype(np.int16)
            
            # Send audio in chunks
            chunk_size = 1600  # 0.1 seconds at 16kHz
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                print(f"🔧 V2 sending chunk {i//chunk_size + 1}, size: {len(chunk)}")
                yield speech_v2.StreamingRecognizeRequest(audio=chunk.tobytes())
                time.sleep(0.1)  # Simulate real-time
        
        print("📡 Starting V2 streaming recognition...")
        responses = client.streaming_recognize(requests=request_generator())
        
        response_count = 0
        start_time = time.time()
        
        for response in responses:
            response_count += 1
            elapsed = time.time() - start_time
            print(f"📡 V2 streaming response #{response_count} (t={elapsed:.1f}s): {response}")
            
            # Break after reasonable time
            if elapsed > 10:
                print("Breaking after 10 seconds")
                break
        
        print(f"🏁 V2 streaming completed: {response_count} responses")
        return response_count > 0
        
    except Exception as e:
        print(f"❌ V2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Speech-to-Text API V2 with Fixed Configuration")
    print("=" * 60)
    
    works = test_v2_with_service_account()
    if works:
        print("\n🎉 V2 STREAMING WORKS!")
    else:
        print("\n❌ V2 still doesn't work")
