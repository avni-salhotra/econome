from google.adk.agents import Agent
from speech_agent import RealTranscriptAgent
import json

class SimpleAgent(Agent):
    def __init__(self):
        super().__init__(
            name="TestAgent",
            description="A simple test agent to verify ADK setup"
        )
    
    def process(self, input_data):
        return {
            "status": "success",
            "message": "ADK is working perfectly!",
            "input_received": str(input_data),
            "agent_name": self.name
        }

# Test both agents
if __name__ == "__main__":
    print("🚀 Testing ADK Setup...")
    
    # Test 1: Simple ADK agent
    agent = SimpleAgent()
    result = agent.process("Hello from hackathon setup!")
    print("=== ADK AGENT TEST ===")
    print(json.dumps(result, indent=2))
    print("✅ ADK setup working!\n")
    
    # Test 2: Real Speech Agent
    print("=== SPEECH AGENT TEST ===")
    speech_agent = RealTranscriptAgent()
    
    # Test with sample audio (or fallback to mock)
    test_audio = {
        "file_path": "sample_meeting.wav",  # Change this to your actual audio file
        "format": "wav"
    }
    
    speech_result = speech_agent.process(test_audio)
    print(f"Status: {speech_result['status']}")
    if speech_result['status'] == 'error':
        print(f"❌ ERROR DETAILS: {speech_result.get('error', 'No error message')}")
    print(f"API Used: {speech_result.get('api_used', 'mock')}")
    print(f"Speakers: {speech_result['speakers_detected']}")
    print(f"Confidence: {speech_result['confidence_score']}")
    
    if speech_result['status'] == 'success':
        print("\n" + "="*50)
        print("FULL TRANSCRIPT DEBUG:")
        print("="*50)
        print(speech_result['transcript'])
        print("="*50)
        print(f"Total characters: {len(speech_result['transcript'])}")
        print(f"Word Count: {speech_result.get('word_count', 'unknown')}")
        print(f"Segments Processed: {speech_result.get('segments_processed', 'unknown')}")
    else:
        print(f"Error: {speech_result.get('error', 'Unknown error')}")
    
    print(f"\n{'✅' if speech_result['status'] == 'success' else '⚠️'} Speech agent test complete!")
