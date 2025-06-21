# 🎤 Conversation Intelligence Web UI

## 🚀 **Quick Start**

### **1. Install Dependencies**
```bash
# Activate your environment
source adk-env/bin/activate

# Install new web dependencies
pip install -r requirements.txt
```

### **2. Test the System**
```bash
# Test all components
python test_web_system.py
```

### **3. Start Web Server**
```bash
# Start the web interface
python web_api.py
```

### **4. Access the UI**
- **Web Interface**: http://localhost:8080
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health

---

## 🏗️ **Architecture Overview**

### **New Components Added**
```
📁 Your Project
├── 🆕 web_api.py              # FastAPI web server
├── 🆕 gcp_session_manager.py  # Ephemeral session storage
├── 🆕 websocket_manager.py    # Real-time communication
├── 🆕 frontend/index.html     # Web interface
├── 🆕 Dockerfile             # Container deployment
├── 🆕 cloudbuild.yaml        # GCP deployment
└── 🔄 meeting_agents.py       # Updated for WebSocket
```

### **Technology Stack**
- **Backend**: FastAPI + WebSockets
- **Frontend**: HTML + JavaScript (Tailwind CSS)
- **Storage**: Firestore with TTL (automatic deletion)
- **Deployment**: Google Cloud Run
- **Real-time**: WebSocket live transcription

---

## 🎯 **Features**

### **✅ What Works Now**
- 🎤 **Real-time recording** with start/stop controls
- 📝 **Live transcription** streaming via WebSocket
- 🧠 **Parallel Gemini processing** (summary + action items)
- 🔗 **Ephemeral URLs** with 24-hour auto-deletion
- 📱 **Responsive web interface**
- 🔒 **Privacy-first** design (no permanent storage)

### **🎨 User Experience**
1. **Click "Start Recording"** → Begin live conversation
2. **See real-time transcription** → Watch your words appear
3. **Click "Stop & Analyze"** → Trigger AI processing
4. **Get organized results** → Summary + categorized action items
5. **Receive secure link** → 24-hour access to results

---

## 🔧 **Configuration**

### **Environment Variables**
```bash
# Required for production
export GOOGLE_CLOUD_PROJECT=econome-hackathon
export GOOGLE_APPLICATION_CREDENTIALS=speech-credentials.json

# Optional
export PORT=8080
export BASE_URL=https://your-domain.com
```

### **Mock Mode (No Credentials)**
```python
# In web_api.py, change:
conversation_system = ConversationIntelligenceSystem(
    mock_mode=True,  # Set to True for testing
    chunk_duration=2.0,
    project_id="econome-hackathon"
)
```

---

## 🚀 **Deployment to Google Cloud**

### **Prerequisites**
1. **Google Cloud Project** with billing enabled
2. **APIs enabled**: Cloud Run, Cloud Build, Firestore, Speech, Vertex AI
3. **gcloud CLI** installed and authenticated

### **Deploy Commands**
```bash
# Set your project
gcloud config set project econome-hackathon

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable firestore.googleapis.com

# Deploy with Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Get the deployed URL
gcloud run services describe conversation-intelligence \
  --region=us-central1 --format="value(status.url)"
```

### **Firestore Setup**
```bash
# Create Firestore database
gcloud firestore databases create --region=us-central1

# TTL will be automatically handled by the application
```

---

## 🧪 **Testing**

### **Local Testing**
```bash
# Test all components
python test_web_system.py

# Test specific components
python gcp_session_manager.py
python websocket_manager.py
```

### **Web Interface Testing**
1. **Start server**: `python web_api.py`
2. **Open browser**: http://localhost:8080
3. **Test recording**: Click start → speak → stop
4. **Check results**: Verify summary and action items
5. **Test ephemeral URL**: Copy and access the secure link

### **API Testing**
```bash
# Health check
curl http://localhost:8080/health

# System status
curl http://localhost:8080/api/status

# Test ephemeral session (use token from test)
curl http://localhost:8080/api/results/YOUR_TOKEN_HERE
```

---

## 🔒 **Privacy Features**

### **Automatic Data Deletion**
- **Firestore TTL**: Documents auto-delete after 24 hours
- **Memory-only processing**: No permanent conversation storage
- **Secure tokens**: Cryptographically secure access URLs
- **Verifiable deletion**: Users can confirm data destruction

### **Privacy Verification**
```bash
# Check if data still exists
curl http://localhost:8080/api/privacy/verify/YOUR_TOKEN

# Response when active:
{"status": "active", "expires_in": "23h 45m remaining"}

# Response when deleted:
{"status": "deleted", "message": "Your data has been permanently deleted"}
```

---

## 🐛 **Troubleshooting**

### **Common Issues**

**1. Import Errors**
```bash
# Install missing dependencies
pip install fastapi uvicorn websockets google-cloud-firestore
```

**2. WebSocket Connection Failed**
- Check if port 8080 is available
- Verify firewall settings
- Try different browser

**3. Firestore Permission Denied**
```bash
# Check credentials
gcloud auth application-default login

# Verify project
gcloud config get-value project
```

**4. Audio Not Working**
- Check microphone permissions in browser
- Verify audio device is working
- Try different browser

### **Debug Mode**
```python
# In web_api.py, enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📊 **Monitoring**

### **Health Endpoints**
- `/health` - Basic health check
- `/api/status` - Detailed system status
- WebSocket connection count in status

### **Logs**
```bash
# Local development
python web_api.py  # Logs to console

# Cloud Run
gcloud logs read conversation-intelligence --limit=50
```

---

## 🎯 **Next Steps**

### **Ready for Hackathon Demo**
1. ✅ **Web interface** - Professional UI
2. ✅ **Real-time features** - Live transcription
3. ✅ **Privacy-first** - Automatic deletion
4. ✅ **GCP integration** - Cloud-native architecture
5. ✅ **Production-ready** - Error handling & monitoring

### **Optional Enhancements**
- 🎨 **React frontend** (current: vanilla JS)
- 📱 **Mobile app** integration
- 🔐 **User authentication** (Firebase Auth)
- 📊 **Analytics dashboard**
- 🌍 **Multi-language support**

---

## 🏆 **Judge Presentation Points**

### **Technical Excellence**
- ✅ **Multi-agent architecture** with real-time coordination
- ✅ **Parallel Gemini processing** for performance
- ✅ **WebSocket real-time** communication
- ✅ **Cloud-native deployment** on Google Cloud Run

### **Privacy Innovation**
- ✅ **Ephemeral storage** with automatic deletion
- ✅ **Firestore TTL** for guaranteed data destruction
- ✅ **Memory-only processing** pipeline
- ✅ **Verifiable deletion** for user trust

### **User Experience**
- ✅ **Intuitive web interface** with real-time feedback
- ✅ **Professional results** display
- ✅ **Secure access links** for practical use
- ✅ **Responsive design** for any device

