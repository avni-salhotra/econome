# Econome ADK Documentation Server

## Quick Start for Judges

This is a **Google Agent Development Kit (ADK)** integration that provides an intelligent documentation assistant for the Econome conversation intelligence platform.

### 🚀 One-Command Setup

```bash
./setup-adk.sh
```

This script will:
1. ✅ Check virtual environment 
2. 🔐 Set up Google Cloud authentication automatically
3. 🌐 Start the ADK documentation server on http://localhost:8002

### 🎯 What This Demonstrates

- **ADK Integration**: Real production system enhanced with Google's ADK
- **Intelligent Documentation**: AI-powered search through 100KB+ of technical docs
- **Function Tools**: 5 specialized tools for documentation discovery
- **Enterprise Ready**: Proper authentication and deployment patterns

### 📋 Authentication Options

The server automatically detects and uses authentication in this order:

1. **gcloud CLI** (recommended for local testing)
   ```bash
   gcloud auth application-default login
   ```

2. **Service Account Key** (for production deployment)
   - Place `service-account-key.json` in project root
   - Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

3. **Google Cloud Metadata** (when running on Google Cloud)

### 🧪 Testing the Agent

1. Open http://localhost:8002 in your browser
2. Select the `docs` agent
3. Ask questions like:
   - "What documentation is available for Econome?"
   - "How do I deploy the Econome system?"
   - "What is the architecture of Econome?"
   - "Show me the runbook procedures"

### 🔧 Function Tools Available

- `search_documentation()` - Intelligent search across all docs
- `get_architecture_overview()` - System architecture details  
- `get_deployment_instructions()` - Deployment procedures
- `get_project_runbook()` - Operational procedures
- `list_available_documentation()` - Available documentation index

### 📚 Documentation Coverage

- **ARCHITECTURE.md** - System design and technical overview
- **DEPLOYMENT_GUIDE.md** - Step-by-step deployment instructions  
- **DESIGN_DECISIONS.md** - Technical decisions and rationale
- **RUNBOOK.md** - Operational procedures and troubleshooting

### 🌟 Business Value

- **Solves Documentation Discovery**: Enterprise teams can't find information in large codebases
- **Natural Language Interface**: Ask questions instead of browsing files
- **Production Integration**: Shows how ADK enhances existing systems vs. building from scratch
- **Scalable Pattern**: Can be deployed to Google Cloud (Vertex AI Agent Engine, Cloud Run, GKE)

### 🔍 Troubleshooting

**Authentication Issues:**
```bash
# Check current authentication
gcloud auth list

# Login if needed
gcloud auth application-default login

# Check project
gcloud config get-value project
```

**Missing Dependencies:**
```bash
# Recreate virtual environment
python -m venv adk-env
source adk-env/bin/activate
pip install google-adk
```

### 📊 Technical Achievement

✅ **Working ADK Integration** - Not just a demo, fully functional  
✅ **Production Documentation** - Real 100KB+ technical documentation  
✅ **Intelligent Search** - Semantic search and retrieval  
✅ **Enterprise Authentication** - Google Cloud ADC integration  
✅ **Cloud Deployable** - Ready for production deployment  

---

**Time Investment**: ~2 hours to integrate ADK with existing production system  
**Lines of Code**: ~200 lines for full documentation agent  
**Business Impact**: Immediate value for technical knowledge discovery 