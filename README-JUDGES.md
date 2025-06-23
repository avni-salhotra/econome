# 🚀 Econome ADK Documentation Agent - Judge Setup Guide

**Security-First Authentication for Hackathon Evaluation**

Welcome, judges! This guide will help you set up and run the Econome ADK documentation agent with your own Google AI Studio API key. This approach ensures secure, individual authentication and provides better access control for the evaluation process.

## 🔐 Why Individual API Keys?

This system requires each judge to authenticate with their own Google AI Studio API key for several important security reasons:

- **Individual Access Control**: Each judge has their own authentication credentials
- **Audit Trail**: Usage can be tracked per judge for accountability
- **Security Isolation**: No shared credentials that could be compromised
- **Rate Limiting**: Personal quotas prevent abuse and ensure fair usage
- **Compliance**: Meets enterprise security standards for hackathon evaluation

## 📋 Quick Setup (5 Minutes)

### Step 1: Get Your Google AI Studio API Key

1. **Visit Google AI Studio**: Go to [https://aistudio.google.com/](https://aistudio.google.com/)
2. **Sign in** with your Google account
3. **Create API Key**: 
   - Click on "Get API key" in the left sidebar
   - Click "Create API key in new project" (or use existing project)
   - Copy the generated API key (starts with `AIza...`)
   - **Important**: Keep this key secure and don't share it

### Step 2: Set Up the Environment

1. **Clone and navigate to the project**:
   ```bash
   git clone [repository-url]
   cd econome
   ```

2. **Set your API key** (choose one method):

   **Option A: Environment Variable (Recommended)**
   ```bash
   export GOOGLE_API_KEY="your_api_key_here"
   ```

   **Option B: Create a .env file**
   ```bash
   echo "GOOGLE_API_KEY=your_api_key_here" > .env
   ```

3. **Run the setup script**:
   ```bash
   chmod +x setup-adk.sh
   ./setup-adk.sh
   ```

### Step 3: Access the Documentation Agent

1. **Open your browser** to: `http://localhost:8002`
2. **Click on the "docs" agent**
3. **Create a new session**
4. **Start asking questions** about the Econome project!

## 💡 Sample Questions to Try

- "What is the Econome project and what does it do?"
- "How does the speech-to-text functionality work?"
- "What are the main components of the system architecture?"
- "How is the system deployed to production?"
- "What security measures are implemented?"

## 🔧 Troubleshooting

### API Key Issues
- **Invalid API key**: Double-check you copied the full key from Google AI Studio
- **Quota exceeded**: You may need to enable billing in your Google Cloud project
- **API not enabled**: The Generative Language API should be automatically enabled

### Setup Issues
- **Port already in use**: Try a different port with `adk web --port 8003`
- **Permission denied**: Make sure the setup script is executable: `chmod +x setup-adk.sh`
- **Python environment**: Ensure you're using Python 3.12+ and have the ADK environment activated

### Getting Help
If you encounter issues:
1. Check the terminal output for specific error messages
2. Ensure your API key is correctly set
3. Try restarting the server: `Ctrl+C` then run `./setup-adk.sh` again

## 🏆 What You're Evaluating

### **Business Value**
- **AI-Powered Documentation Search**: Intelligent search through technical documentation
- **Production Integration**: ADK agent integrated with existing enterprise system
- **Scalable Architecture**: Cloud-native deployment ready for enterprise use

### **Technical Achievement**
- **Google ADK Integration**: Successful integration of Google's Agent Development Kit
- **Multi-Agent System**: Documentation agent working alongside existing conversation intelligence agents
- **Security-First Design**: Enterprise-grade authentication and access control
- **Cloud Deployment**: Full CI/CD pipeline with staging and production environments

### **Innovation**
- **Hybrid Intelligence**: Combines existing production AI system with new ADK capabilities
- **Developer Experience**: Easy-to-use documentation search for technical teams
- **Extensible Framework**: Foundation for additional ADK agents and capabilities

## 📊 Success Metrics

- **Accuracy**: How well does the agent answer questions about the documentation?
- **Performance**: Response time and system reliability
- **Usability**: Ease of setup and interaction quality
- **Integration**: How seamlessly does it work with the existing Econome system?

## 🛡️ Security Notes

- Your API key provides access to Google's Generative AI services
- Keep your API key confidential and don't share it
- The key is only used for AI model access, not for any data storage
- All conversations are processed securely through Google's infrastructure

## 🎯 Evaluation Criteria

Consider these aspects during your evaluation:

1. **Functionality**: Does the documentation agent work as intended?
2. **User Experience**: Is it easy to set up and use?
3. **Integration Quality**: How well does it integrate with the existing system?
4. **Technical Implementation**: Code quality and architecture decisions
5. **Business Impact**: Potential value for enterprise customers
6. **Innovation**: Creative use of Google ADK capabilities

---

**Thank you for evaluating the Econome ADK Documentation Agent!** 

This project demonstrates the power of integrating Google's Agent Development Kit with existing production AI systems to create new capabilities for enterprise customers.

For questions about the project, please refer to the documentation or contact the development team. 