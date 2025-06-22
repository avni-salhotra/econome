# 🏗️ Econome Architecture Documentation

## 📋 Overview

Econome is a privacy-first, real-time conversation intelligence system built with a modern cloud-native architecture. The system provides live audio transcription, AI-powered analysis, and ephemeral session management with automatic data deletion.

## 🎯 Design Principles

### 1. **Privacy-First Architecture**
- Ephemeral data storage with 24-hour TTL
- Automatic session cleanup
- No persistent conversation storage
- Minimal data retention

### 2. **Real-Time Processing**
- WebSocket-based communication
- Live audio streaming and transcription
- Immediate AI analysis and feedback
- Sub-second response times

### 3. **Cloud-Native Design**
- Serverless deployment on Google Cloud Run
- Auto-scaling based on demand
- Stateless application design
- Container-based architecture

### 4. **Security & Compliance**
- Secure secret management with Google Secret Manager
- Service account-based authentication
- Encrypted communication (HTTPS/WSS)
- Input validation and sanitization

## 🏛️ System Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   Web Browser   │◄──►│  Cloud Run      │◄──►│  Google Cloud   │
│                 │    │  (Econome)      │    │  Services       │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                        │                        │
        │                        │                        ├─ Speech-to-Text API
        │                        │                        ├─ Gemini AI API
        │                        │                        ├─ Firestore
        │                        │                        └─ Secret Manager
        │                        │
        ├─ HTML5 Audio API       ├─ FastAPI + WebSockets
        ├─ WebSocket Client      ├─ Multi-Agent System
        └─ Real-time UI          └─ Session Management
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cloud Run Service                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Web API       │  │  WebSocket      │  │  Static Files   │ │
│  │   (FastAPI)     │  │  Handler        │  │  (Frontend)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Conversation    │  │  AI Analysis    │  │  Session        │ │
│  │ Intelligence    │  │  Agent          │  │  Manager        │ │
│  │ System          │  │                 │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Speech Client   │  │  Gemini Client  │  │  Firestore      │ │
│  │ (STT)           │  │  (AI)           │  │  Client         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow

### 1. **Conversation Initiation**
```
User → WebSocket Connection → System Initialization → Agent Setup
```

### 2. **Real-Time Processing**
```
Audio Stream → Speech-to-Text → Live Transcription → WebSocket → User
     ↓
Transcript Buffer → AI Analysis → Insights → WebSocket → User
```

### 3. **Session Completion**
```
Stop Signal → Final Analysis → Summary Generation → Session Storage → Ephemeral URL
```

### 4. **Data Lifecycle**
```
Session Creation → 24-hour TTL → Automatic Cleanup → Data Deletion
```

## 🧩 Core Components

### 1. **Web API Layer (`web_api.py`)**
- **Technology**: FastAPI
- **Responsibilities**:
  - HTTP endpoint management
  - WebSocket connection handling
  - Static file serving
  - Health checks and monitoring
- **Key Features**:
  - Async request handling
  - CORS configuration
  - Error handling and logging

### 2. **Conversation Intelligence System (`meeting_agents.py`)**
- **Technology**: Multi-agent architecture
- **Responsibilities**:
  - Real-time audio processing
  - Transcript management
  - AI analysis coordination
  - System state management
- **Key Features**:
  - Asynchronous processing
  - Agent lifecycle management
  - Error recovery and resilience

### 3. **Session Management (`gcp_session_manager.py`)**
- **Technology**: Google Firestore + In-memory fallback
- **Responsibilities**:
  - Ephemeral session storage
  - TTL-based cleanup
  - Session retrieval and management
- **Key Features**:
  - Automatic expiration
  - Privacy-compliant storage
  - Fallback mechanisms

### 4. **Frontend (`frontend/`)**
- **Technology**: HTML5, JavaScript, Tailwind CSS
- **Responsibilities**:
  - User interface
  - Audio capture and streaming
  - Real-time display updates
  - WebSocket communication
- **Key Features**:
  - Responsive design
  - Real-time audio visualization
  - Progressive enhancement

## 🔧 Technology Stack

### **Backend**
- **Runtime**: Python 3.12
- **Framework**: FastAPI
- **WebSockets**: FastAPI WebSocket support
- **Async**: asyncio, aiohttp

### **AI & ML**
- **Speech-to-Text**: Google Cloud Speech V2
- **AI Analysis**: Google Gemini 1.5 Pro
- **Processing**: Real-time streaming

### **Data Storage**
- **Primary**: Google Firestore (ephemeral)
- **Fallback**: In-memory storage
- **Secrets**: Google Secret Manager

### **Infrastructure**
- **Compute**: Google Cloud Run
- **Container**: Docker
- **Registry**: Google Container Registry
- **CI/CD**: GitHub Actions + Cloud Build

### **Frontend**
- **Core**: HTML5, JavaScript ES6+
- **Styling**: Tailwind CSS
- **Audio**: Web Audio API
- **Communication**: WebSocket API

## 🔒 Security Architecture

### **Authentication & Authorization**
```
GitHub Actions → Service Account → GCP APIs
     ↓
Cloud Run → Service Account → Google Services
     ↓
Application → Secret Manager → Credentials
```

### **Data Protection**
- **In Transit**: HTTPS/WSS encryption
- **At Rest**: Google Cloud encryption
- **Processing**: Memory-only for audio
- **Storage**: Ephemeral with TTL

### **Secret Management**
```
Google Secret Manager
├─ speech-credentials (STT API)
├─ gemini-credentials (AI API)
└─ Environment-specific secrets
```

## 📊 Deployment Architecture

### **Environments**

#### **Staging**
- **Service**: `econome-staging`
- **Resources**: 1 CPU, 1GB RAM
- **Scaling**: 0-3 instances
- **Purpose**: Testing and validation

#### **Production**
- **Service**: `econome`
- **Resources**: 2 CPU, 2GB RAM
- **Scaling**: 1-10 instances
- **Purpose**: Live user traffic

### **CI/CD Pipeline**
```
Code Push → Tests → Build → Push → Staging → Manual Approval → Production
     ↓         ↓      ↓      ↓        ↓            ↓              ↓
   GitHub   GitHub  Cloud  GCR   Cloud Run   Human Review   Cloud Run
  Actions   Actions  Build        (Staging)                (Production)
```

## 🚀 Performance Characteristics

### **Latency Targets**
- **WebSocket Connection**: < 100ms
- **Speech Recognition**: < 500ms
- **AI Analysis**: < 2s
- **Session Retrieval**: < 200ms

### **Throughput Targets**
- **Concurrent Users**: 100+ per instance
- **Audio Processing**: Real-time (1:1 ratio)
- **WebSocket Messages**: 1000+ per second

### **Scalability**
- **Horizontal**: Auto-scaling Cloud Run instances
- **Vertical**: Configurable CPU/memory per instance
- **Geographic**: Single region (us-central1)

## 🔍 Monitoring & Observability

### **Health Checks**
- **Endpoint**: `/health`
- **Checks**: Service status, dependencies, resources
- **Frequency**: Every 30 seconds

### **Logging**
- **Platform**: Google Cloud Logging
- **Format**: Structured JSON
- **Levels**: INFO, WARNING, ERROR

### **Metrics**
- **Platform**: Google Cloud Monitoring
- **Custom Metrics**: Session count, processing time
- **Alerts**: Error rate, latency, availability

## 🔄 Data Lifecycle Management

### **Session Lifecycle**
```
Creation → Active Use → Completion → Storage → TTL Expiry → Deletion
   ↓          ↓           ↓          ↓         ↓           ↓
  0min     0-60min     60min    60min-24h   24h        24h+
```

### **Privacy Compliance**
- **Data Minimization**: Only necessary data stored
- **Purpose Limitation**: Data used only for intended purpose
- **Storage Limitation**: 24-hour maximum retention
- **Transparency**: Clear data handling policies

## 🔧 Configuration Management

### **Environment Variables**
- **Common**: Shared across environments
- **Environment-specific**: Staging vs Production
- **Secrets**: Managed via Secret Manager

### **Feature Flags**
- **API Documentation**: Configurable
- **Debug Endpoints**: Environment-specific
- **Mock Mode**: Testing support

## 📈 Future Considerations

### **Scalability Enhancements**
- Multi-region deployment
- CDN for static assets
- Database sharding (if needed)

### **Feature Additions**
- User authentication
- Conversation history (opt-in)
- Advanced AI features
- Mobile application

### **Performance Optimizations**
- Edge computing for audio processing
- Caching layers
- Connection pooling
- Resource optimization

---

*This architecture documentation is maintained alongside the codebase and updated with each major release.*
