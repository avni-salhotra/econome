#!/usr/bin/env python3
"""
Gemini API Service for Conversation Analysis

This module provides functions to interact with the Gemini API for:
- Summarizing conversations
- Extracting action items

It includes mock functionality for development without credentials.
"""

import os
import json
from typing import List, Dict

# Google AI imports
try:
    import google.generativeai as genai
    from google.oauth2 import service_account
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    genai = None
    service_account = None

# --- Constants ---
GENERATION_MODEL = "models/gemini-1.5-pro"
GENERATION_PARAMS = {
    "candidate_count": 1,
    "temperature": 0.7,
}

# --- Initialization ---

def _initialize_gemini():
    """Initialize the Gemini client with service account credentials."""
    if not GOOGLE_API_AVAILABLE:
        print("⚠️ Google AI libraries not installed, running in mock mode.")
        return None

    try:
        # Look for credentials in the standard path for this project
        creds_path = "gemini-credentials.json"
        if os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(creds_path)
            genai.configure(credentials=credentials)
            print("✅ Gemini initialized with service account credentials from gemini-credentials.json")
            return genai.GenerativeModel(GENERATION_MODEL)
        else:
            print("⚠️ gemini-credentials.json not found, running in mock mode.")
            return None
    except Exception as e:
        print(f"❌ Failed to initialize Gemini: {e}")
        return None

# Initialize model (may be None if no credentials)
model = _initialize_gemini()

# --- Functions ---

async def summarize_conversation(text: str) -> str:
    """
    Use Gemini to organize and structure stream-of-consciousness thoughts
    into a coherent, readable format while preserving all important information.
    """
    if model is None:
        return f"Mock organized thoughts: Cleaned up rambling from conversation about {text[:50]}... (Gemini not available)"

    try:
        prompt = (
            "You are an expert at organizing rambling, stream-of-consciousness thoughts. "
            "The user just spoke their thoughts out loud, possibly jumping between topics or repeating themselves. "
            "Your job is to take their raw, unfiltered thoughts and organize them into a clean, structured format.\n\n"
            "Guidelines:\n"
            "- Combine related thoughts together\n"
            "- Remove repetition and filler words\n"
            "- Create logical flow and structure\n"
            "- Keep ALL important information and context\n"
            "- Do NOT create action items - just organize their thoughts\n"
            "- Use simple, clear language\n"
            "- Format with short paragraphs for readability\n\n"
            
            "Raw thoughts from the user:\n"
            f"{text}\n\n"
            
            "Organized thoughts:"
        )
        
        response = await model.generate_content_async(prompt, generation_config=GENERATION_PARAMS)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini organization error: {e}")
        return f"Organization unavailable due to error: {str(e)}"


async def extract_action_items(text: str) -> List[Dict]:
    """
    Use Gemini to extract action items relevant to a single user context.
    Returns a list of dicts with 'action', 'type', 'deadline', 'recipient'.
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
            "Return the output as a JSON list of objects, where each object has the keys "
            "'action', 'type', 'deadline', and 'recipient'. If a field is not present, use null. "
            "Do not include any preamble or explanation, only the JSON list.\n\n"
            "Conversation Text:\n"
            f"{text}\n\n"
            "JSON Output:"
        )
        
        response = await model.generate_content_async(prompt, generation_config=GENERATION_PARAMS)
        
        # Clean up response before parsing
        cleaned_response = response.text.strip()

        # Try to extract JSON from the response
        try:
            # Look for JSON content between brackets
            start_idx = cleaned_response.find('[')
            end_idx = cleaned_response.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = cleaned_response[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [{"error": "Response was not a list", "raw_output": cleaned_response}]
            else:
                # No JSON brackets found, try parsing the whole response
                parsed = json.loads(cleaned_response)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [{"error": "Response was not a JSON list", "raw_output": cleaned_response}]
                    
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print(f"Raw response: {cleaned_response}")
            
            # Return a fallback action item if parsing fails
            return [{
                "error": "Failed to parse Gemini JSON output",
                "raw_output": cleaned_response,
                "type": "todo",
                "action": "Review AI-extracted action items manually",
                "deadline": "Soon",
                "recipient": None
            }]
            
    except Exception as e:
        print(f"❌ Gemini action item extraction error: {e}")
        return [{"action": f"Error extracting action items: {e}", "type": "error", "deadline": None, "recipient": None}]


async def test_gemini_integration():
    """Test function to verify Gemini integration works"""
    
    print("🧪 Testing Gemini Integration...")
    
    test_transcript = """
    I need to send the quarterly report to Sarah by Friday.
    Also, I should schedule a meeting with the design team next week.
    Don't forget to follow up with Mike about the contract details.
    """
    
    print("Testing summarization...")
    summary = await summarize_conversation(test_transcript)
    print(f"Summary: {summary}")
    
    print("\nTesting action item extraction...")
    action_items = await extract_action_items(test_transcript)
    print(f"Action items: {json.dumps(action_items, indent=2)}")
    
    print("✅ Gemini integration test complete")


# --- Self-Test ---

async def _test_gemini_functions():
    """Test both functions with a sample text if run as a script."""
    sample_text = (
        "Hey team, so for the project update, I think we need to finalize the "
        "prepare the slides for the Friday presentation."
    )
    
    print("--- Testing Conversation Summary ---")
    summary = await summarize_conversation(sample_text)
    print("Summary:", summary)
    
    print("\n--- Testing Action Item Extraction ---")
    action_items = await extract_action_items(sample_text)
    print("Action Items:", json.dumps(action_items, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test_gemini_functions())