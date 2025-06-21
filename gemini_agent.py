import os
import json
import google.generativeai as genai
from google.oauth2 import service_account
from typing import List, Dict

# --- Configuration ---

GENERATION_MODEL = "models/gemini-1.5-pro"
GENERATION_PARAMS = {
    "temperature": 0.7,
    "top_p": 1.0,
    "top_k": 40,
    "max_output_tokens": 1024
}

# --- Initialization ---

def _initialize_gemini(credentials_path: str = "gemini-credentials.json"):
    """Initialize Gemini with proper error handling and service account credentials"""
    try:
        # First try service account credentials
        if os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            genai.configure(credentials=credentials)
            print("✅ Gemini initialized with service account credentials")
            return genai.GenerativeModel(GENERATION_MODEL)

        # Fallback to API key if available
        elif os.getenv("GOOGLE_API_KEY"):
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            print("✅ Gemini initialized with API key")
            return genai.GenerativeModel(GENERATION_MODEL)

        # Fallback to default credentials
        elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            genai.configure()
            print("✅ Gemini initialized with application default credentials")
            return genai.GenerativeModel(GENERATION_MODEL)

        else:
            print("⚠️ No Gemini credentials found - running in mock mode")
            return None

    except Exception as e:
        print(f"⚠️ Gemini initialization failed: {e}")
        return None

# Initialize model (may be None if no credentials)
model = _initialize_gemini()

# --- Functions ---

def summarize_conversation(text: str) -> str:
    """
    Use Gemini to organize and structure stream-of-consciousness thoughts
    into a coherent, readable format while preserving all important information.
    """
    if model is None:
        return f"Mock summary: Organized thoughts from conversation about {text[:50]}... (Gemini not available)"

    try:
        prompt = (
            "You are helping someone organize their stream-of-consciousness thoughts into a clear, structured format. "
            "Your goal is NOT to summarize or compress information, but to organize and improve readability while preserving all important details.\n\n"
            
            "Please reorganize the following spoken thoughts by:\n"
            "1. **Preserving ALL important information** - don't remove or compress anything meaningful\n"
            "2. **Organizing related ideas together** - group thoughts that belong together even if they were mentioned separately\n"
            "3. **Creating logical flow** - arrange ideas in a sensible order with smooth transitions\n"
            "4. **Cleaning up speech patterns** - remove filler words (um, uh, you know), false starts, and repetitions\n"
            "5. **Adding structure** - use clear paragraphs and natural transitions between different topics\n"
            "6. **Maintaining the speaker's voice** - keep their personal style and tone, just make it more organized\n\n"
            
            "Think of this as taking messy handwritten notes and typing them up neatly - same content, better organization.\n\n"
            
            "Original thoughts:\n"
            f"{text}\n\n"
            
            "Organized version:"
        )
        
        response = model.generate_content(prompt, generation_config=GENERATION_PARAMS)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini organization error: {e}")
        return f"Organization unavailable due to error: {str(e)}"


def extract_action_items(text: str) -> List[Dict]:
    """
    Use Gemini to extract action items relevant to a single user context.
    Returns a list of dicts with keys: type, action, deadline, and optionally recipient.
    FIXED VERSION with safe JSON parsing.
    """
    if model is None:
        return [
            {"type": "todo", "action": "Mock action item from conversation", "deadline": "Soon", "recipient": None},
            {"type": "reminder", "action": "Follow up on conversation topics", "deadline": "Tomorrow", "recipient": None}
        ]

    try:
        prompt = (
            "From the following transcript, extract action items relevant to a single speaker (the user). Classify each item as one of:\n"
            '- "todo": things the user must do\n'
            '- "communicate": messages the user intends to send to someone else\n'
            '- "reminder": events or tasks the user should be reminded about\n\n'
            "For each action item, return a JSON object with:\n"
            '- "type": one of "todo", "communicate", or "reminder"\n'
            '- "action": the description of the task or message\n'
            '- "deadline": if any (e.g., "Tuesday", "next week"), otherwise null\n'
            '- "recipient": if the user plans to communicate with someone (e.g., "Amber"), otherwise null\n\n'
            "Respond with a JSON list of these items. Example format:\n"
            '[\n'
            '  {"type": "todo", "action": "Send proposal", "deadline": "Friday", "recipient": null},\n'
            '  {"type": "communicate", "action": "Follow up on contract", "deadline": null, "recipient": "Amber"}\n'
            ']\n\n'
            "Transcript:\n"
            f"{text}"
        )

        response = model.generate_content(prompt, generation_config=GENERATION_PARAMS)
        response_text = response.text.strip()

        # Try to extract JSON from the response
        try:
            # Look for JSON content between brackets
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response_text[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [{"error": "Response was not a list", "raw_output": response_text}]
            else:
                # No JSON brackets found, try parsing the whole response
                parsed = json.loads(response_text)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [{"error": "Response was not a JSON list", "raw_output": response_text}]
                    
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Raw response: {response_text}")
            
            # Return a fallback action item if parsing fails
            return [{
                "error": "Failed to parse Gemini JSON output",
                "raw_output": response_text,
                "type": "todo",
                "action": "Review AI-extracted action items manually",
                "deadline": "Soon",
                "recipient": None
            }]
            
    except Exception as e:
        print(f"❌ Gemini action item extraction error: {e}")
        return [{
            "error": f"Gemini API error: {str(e)}",
            "type": "todo", 
            "action": "Check system logs for AI processing errors",
            "deadline": "Now",
            "recipient": None
        }]


def test_gemini_integration():
    """Test function to verify Gemini integration works"""
    
    print("🧪 Testing Gemini Integration...")
    
    test_transcript = """
    I need to send the quarterly report to Sarah by Friday.
    Also, I should schedule a meeting with the design team next week.
    Don't forget to follow up with Mike about the contract details.
    """
    
    print("Testing summarization...")
    summary = summarize_conversation(test_transcript)
    print(f"Summary: {summary}")
    
    print("\nTesting action item extraction...")
    action_items = extract_action_items(test_transcript)
    print(f"Action items: {json.dumps(action_items, indent=2)}")
    
    print("✅ Gemini integration test complete")


if __name__ == "__main__":
    test_gemini_integration()