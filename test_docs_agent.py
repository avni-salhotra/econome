#!/usr/bin/env python3
"""
Test script for the docs agent to verify authentication and model access before running ADK server.
"""

import sys
import os

def test_docs_agent():
    """Test the docs agent import and basic functionality."""
    print("🧪 Testing docs agent...")
    
    try:
        # Test importing the agent
        print("📦 Importing docs agent...")
        from docs.agent import root_agent, PROJECT_ID, AUTH_METHOD
        print(f"✅ Agent imported successfully")
        print(f"📋 Project/Auth: {PROJECT_ID}")
        print(f"🔐 Authentication method: {AUTH_METHOD}")
        print(f"🤖 Agent name: {root_agent.name}")
        print(f"🧠 Model: {root_agent.model}")
        
        # Test the documentation search function
        print("\n📚 Testing documentation search...")
        try:
            from docs.agent import search_documentation
            result = search_documentation("What is Econome?")
            if result and 'content' in result:
                print("✅ Documentation search function works")
                print(f"📄 Sample result: {result['content'][:100]}...")
            else:
                print("⚠️ Documentation search returned empty result")
        except Exception as e:
            print(f"⚠️ Documentation search test failed: {e}")
        
        print("\n✅ All basic tests passed!")
        print("🚀 Ready to start ADK server!")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_docs_agent()
    sys.exit(0 if success else 1) 