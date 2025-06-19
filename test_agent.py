from google.adk.agents import Agent
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

# Test the agent
if __name__ == "__main__":
    agent = SimpleAgent()
    result = agent.process("Hello from hackathon setup!")
    print("🚀 Agent Test Result:")
    print(json.dumps(result, indent=2))
    print("\n✅ ADK setup is perfect! Ready to build!")
