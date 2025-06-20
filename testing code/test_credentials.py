#!/usr/bin/env python3
"""
Quick test to verify Google Cloud Speech credentials
"""

import os
import json

def test_credentials():
    cred_file = "speech-credentials.json"
    
    print("🔍 Testing Google Cloud Speech Credentials...")
    print("=" * 50)
    
    # Check if file exists
    if not os.path.exists(cred_file):
        print("❌ Credentials file not found")
        print(f"   Looking for: {cred_file}")
        print("   Download from Google Cloud Console!")
        return False
    
    # Check file format
    try:
        with open(cred_file, 'r') as f:
            creds = json.load(f)
        
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing = [field for field in required_fields if field not in creds]
        
        if missing:
            print(f"❌ Missing required fields: {missing}")
            return False
        
        if creds.get('type') != 'service_account':
            print(f"❌ Wrong credential type: {creds.get('type')}")
            print("   Should be: service_account")
            return False
        
        print("✅ Credentials file format is correct")
        print(f"   Project ID: {creds['project_id']}")
        print(f"   Service Account: {creds['client_email']}")
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON format")
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False
    
    # Test Google Cloud import
    try:
        from google.cloud import speech
        print("✅ Google Cloud Speech library installed")
    except ImportError:
        print("❌ Google Cloud Speech library not installed")
        print("   Run: pip install google-cloud-speech")
        return False
    
    # Test client initialization
    try:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_file
        client = speech.SpeechClient()
        print("✅ Speech client initialized successfully")
        print("\n🎉 Everything looks good! Ready to process audio.")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize Speech client: {e}")
        print("   Check your credentials and API enablement")
        return False

if __name__ == "__main__":
    success = test_credentials()
    
    if success:
        print("\n📋 Next Steps:")
        print("1. Add an audio file (MP3, WAV, FLAC)")
        print("2. Run: python meeting_agents.py")
        print("3. Watch real speech-to-text in action!")
    else:
        print("\n📋 Setup Required:")
        print("1. Follow the detailed setup guide")
        print("2. Download credentials from Google Cloud Console")
        print("3. Save as 'speech-credentials.json'")
        print("4. Run this test again")
