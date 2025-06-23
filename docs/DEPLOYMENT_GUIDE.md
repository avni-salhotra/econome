# 🚀 Econome Production Deployment Guide

This guide provides step-by-step instructions for deploying the production-ready Econome real-time conversation intelligence system to Google Cloud Run.

## 📋 Prerequisites

Before starting, you'll need:
- A Google account with billing enabled
- Basic command line knowledge
- **No Docker required** - We use Cloud Build for container builds

## 🏗️ Step 1: Create Google Cloud Project

### 1.1 Create Google Cloud Account
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Sign in with your Google account
3. Accept the terms of service
4. New accounts receive $300 in free credits

### 1.2 Create a New Project
1. Click the project dropdown at the top of the page
2. Click "New Project"
3. Enter project name: `econome-production` (or your preferred name)
4. Click "Create"
5. **Important**: Note your Project ID (e.g., `econome-production-123456`)

## 🔑 Step 2: Setup Service Account & Credentials

### 2.1 Create Service Account
```bash
# Create service account for the application
gcloud iam service-accounts create econome-service \
    --description="Service account for Econome application runtime" \
    --display-name="Econome Service Account"

# Get your project ID
PROJECT_ID=$(gcloud config get-value project)
```

### 2.2 Grant Required Permissions
```bash
# Application runtime permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/speech.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/firestore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 2.3 Create and Download Credentials
```bash
# Create and download service account key
gcloud iam service-accounts keys create speech-credentials.json \
    --iam-account=econome-service@$PROJECT_ID.iam.gserviceaccount.com

# Copy for Gemini AI (same service account, different name for clarity)
cp speech-credentials.json gemini-credentials.json

# Verify files exist
ls -la *-credentials.json
```

## 💻 Step 3: Install Required Tools

### 3.1 Install Google Cloud CLI

**For macOS:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**For Windows:**
1. Download from [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Run the installer and follow the setup wizard

**For Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

### 3.2 Authenticate Google Cloud CLI
```bash
# Authenticate with your user account
gcloud auth login

# Set up application default credentials
gcloud auth application-default login

# Set the project
gcloud config set project $PROJECT_ID
```

## 🛠️ Step 4: Enable Required APIs

```bash
# Enable all required Google Cloud APIs
gcloud services enable \
    speech.googleapis.com \
    aiplatform.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com

# Verify APIs are enabled
gcloud services list --enabled
```

## 🔐 Step 5: Setup Production Secrets

### 5.1 Create Secret Manager Secrets
```bash
# Create speech credentials secret
gcloud secrets create speech-credentials --data-file=speech-credentials.json

# Create gemini credentials secret
gcloud secrets create gemini-credentials --data-file=gemini-credentials.json

# Verify secrets were created
gcloud secrets list
```

### 5.2 Grant Cloud Run Access to Secrets
```bash
# Get Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_RUN_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant secret access to Cloud Run
gcloud secrets add-iam-policy-binding speech-credentials \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gemini-credentials \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor"
```

## 🏗️ Step 6: Setup Firestore Database

```bash
# Create Firestore database in Native mode
gcloud firestore databases create --region=us-central1

# Note: TTL (Time-To-Live) for automatic data deletion is handled by the application
```

## 🚀 Step 7: Deploy the Application

### 7.1 Quick Deployment (Recommended)
```bash
# Clone the repository (if you haven't already)
git clone https://github.com/YOUR_USERNAME/econome.git
cd econome

# Deploy using Cloud Run source deployment
gcloud run deploy econome \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 1 \
    --max-instances 10 \
    --timeout 3600 \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

### 7.2 Advanced Deployment with GitHub Actions

If you want to set up the full CI/CD pipeline:

#### Create Deployment Service Account
```bash
# Create service account for GitHub Actions
gcloud iam service-accounts create github-deploy \
    --description="Service account for GitHub Actions deployment" \
    --display-name="GitHub Deploy"

# Grant deployment permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.builder"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-deploy-key.json \
    --iam-account=github-deploy@$PROJECT_ID.iam.gserviceaccount.com
```

#### Setup GitHub Secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions

Create these secrets:
- `GCP_PROJECT_ID`: Your Google Cloud Project ID
- `GCP_SA_KEY`: Content of `github-deploy-key.json`
- `SPEECH_CREDENTIALS`: Content of `speech-credentials.json`
- `GEMINI_CREDENTIALS`: Content of `gemini-credentials.json`

## ✅ Step 8: Verify Deployment

### 8.1 Check Service Status
```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe econome \
    --region=us-central1 \
    --format="value(status.url)")

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl "$SERVICE_URL/health"
```

### 8.2 Test the Application
1. Open the service URL in your browser
2. Click "Start Recording"
3. Speak for a few seconds
4. Click "Stop & Analyze"
5. Verify you see organized thoughts and action items

### 8.3 Check Logs
```bash
# View recent logs
gcloud logs read "resource.type=cloud_run_revision" \
    --limit=50 \
    --format="table(timestamp,severity,textPayload)"
```

## 🔒 Step 9: Security Configuration

### 9.1 Remove Public Access (Optional)
If you want to restrict access:
```bash
# Remove public access
gcloud run services remove-iam-policy-binding econome \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker"

# Add specific users
gcloud run services add-iam-policy-binding econome \
    --region=us-central1 \
    --member="user:your-email@gmail.com" \
    --role="roles/run.invoker"
```

### 9.2 Enable HTTPS Only
```bash
# Cloud Run automatically enforces HTTPS
# Verify the service is accessible only via HTTPS
curl -I "$SERVICE_URL"
```

## 📊 Step 10: Monitor Your Deployment

### 10.1 View Service Metrics
```bash
# Check service description
gcloud run services describe econome --region=us-central1

# Monitor resource usage
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
```

### 10.2 Set Up Monitoring Dashboard
1. Go to [Google Cloud Monitoring](https://console.cloud.google.com/monitoring)
2. Create a dashboard for your Cloud Run service
3. Add charts for:
   - Request count
   - Request latency
   - Error rate
   - Container CPU utilization
   - Container memory utilization

## 🛠️ Step 11: Maintenance & Updates

### 11.1 Update the Application
```bash
# Deploy a new version
gcloud run deploy econome \
    --source . \
    --platform managed \
    --region us-central1
```

### 11.2 Scale the Service
```bash
# Adjust scaling parameters
gcloud run services update econome \
    --region=us-central1 \
    --min-instances=1 \
    --max-instances=20
```

### 11.3 View and Rotate Secrets
```bash
# List secret versions
gcloud secrets versions list speech-credentials

# Add new secret version
gcloud secrets versions add speech-credentials --data-file=new-credentials.json
```

## 🆘 Troubleshooting

### Common Issues

**1. Service won't start**
```bash
# Check logs for errors
gcloud logs read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit=20
```

**2. API calls failing**
```bash
# Verify APIs are enabled
gcloud services list --enabled | grep -E "(speech|aiplatform|firestore)"

# Check service account permissions
gcloud projects get-iam-policy $PROJECT_ID
```

**3. Audio upload issues**
- Verify the frontend is using HTTPS (required for MediaRecorder API)
- Check browser console for errors
- Ensure microphone permissions are granted

**4. AI processing slow**
- Check Gemini API quotas and limits
- Monitor Cloud Run instance performance
- Consider increasing memory allocation

### Getting Help

**Documentation**: Check the [main README.md](../README.md) for architecture details

**Logs**: Always check logs first
```bash
gcloud logs read "resource.type=cloud_run_revision" --limit=100
```

**Support**: For production issues, review the [RUNBOOK.md](RUNBOOK.md) for operational procedures

## 💰 Cost Optimization

### Estimated Costs (Monthly)
- **Cloud Run**: $5-20 (based on usage)
- **Speech-to-Text**: $10-50 (60 minutes free/month)
- **Gemini AI**: $15-75 (varies by usage)
- **Firestore**: $0-5 (ephemeral data, minimal storage)
- **Total**: ~$30-150/month for moderate usage

### Cost-Saving Tips
1. **Use minimum instances sparingly** - Only set min-instances > 0 if cold starts are an issue
2. **Monitor usage** - Set up billing alerts
3. **Right-size resources** - Start with 1 CPU, 1GB RAM and scale up if needed
4. **Use ephemeral storage** - Automatic cleanup reduces Firestore costs

---

## 🎉 Success!

Your Econome system is now deployed and ready for production use! Users can:

1. **Record conversations** using any modern web browser
2. **Get real-time transcription** powered by Google Speech V2
3. **Receive AI analysis** with organized thoughts and action items
4. **Access results securely** via 24-hour ephemeral URLs
5. **Trust privacy** with automatic data deletion

**🌐 Share your service URL**: `https://econome-*.a.run.app`

---

*For operational procedures and monitoring, see [RUNBOOK.md](RUNBOOK.md)*
