# 🚀 Econome Cloud Deployment Guide

This guide will walk you through deploying Econome to Google Cloud Run, even if you have zero cloud experience.

## 📋 Prerequisites

Before starting, you'll need:
- A Google account
- A computer with internet access
- Basic command line knowledge (we'll guide you through each step)

## 🏗️ Step 1: Create Google Cloud Project

### 1.1 Create Google Cloud Account
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Sign in with your Google account
3. Accept the terms of service
4. You'll get $300 in free credits for new accounts

### 1.2 Create a New Project
1. Click the project dropdown at the top of the page
2. Click "New Project"
3. Enter project name: `econome-production` (or your preferred name)
4. Click "Create"
5. **Important**: Note your Project ID (it will be something like `econome-production-123456`)

## 🔑 Step 2: Setup Service Account & Credentials

### 2.1 Create Service Account
1. In Google Cloud Console, go to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Name: `econome-service`
4. Description: `Service account for Econome application`
5. Click "Create and Continue"

### 2.2 Grant Permissions
Add these roles to your service account:
- `Cloud Run Admin`
- `Cloud Build Service Account`
- `Speech-to-Text Admin`
- `AI Platform Admin`
- `Secret Manager Admin`
- `Storage Admin`

### 2.3 Create and Download Credentials
1. Click on your service account
2. Go to "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON" format
5. Click "Create"
6. **Important**: You'll need to download this key twice and save as:
   - `speech-credentials.json` (for Google Cloud Speech-to-Text)
   - `gemini-credentials.json` (for Gemini AI)

   **Note**: You can use the same service account key for both services, just save it with both names.

## 💻 Step 3: Install Required Tools

### 3.1 Install Google Cloud CLI

**For macOS:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**For Windows:**
1. Download from [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. Run the installer
3. Follow the setup wizard

**For Linux:**
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

### 3.2 Install Docker

**For macOS:**
1. Download [Docker Desktop for Mac](https://docs.docker.com/desktop/mac/install/)
2. Install and start Docker Desktop

**For Windows:**
1. Download [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/)
2. Install and start Docker Desktop

**For Linux:**
```bash
sudo apt-get update
sudo apt-get install docker.io
sudo systemctl start docker
sudo systemctl enable docker
```

### 3.3 Authenticate Google Cloud CLI
```bash
gcloud auth login
gcloud auth application-default login
```

## 🛠️ Step 4: Prepare Your Econome Project

### 4.1 Download/Clone Econome
If you haven't already, get the Econome code on your computer.

### 4.2 Setup Credentials (IMPORTANT!)
You need to set up credential files for Google Cloud services:

**Option A: Quick Setup (Recommended)**
```bash
cd econome
./setup-credentials.sh
```

**Option B: Manual Setup**
1. Save your downloaded service account key as `service-account-key.json`
2. Copy it to both required names:
   ```bash
   cp service-account-key.json speech-credentials.json
   cp service-account-key.json gemini-credentials.json
   ```

**Why two files?** Econome uses separate credential files for:
- `speech-credentials.json` - Google Cloud Speech-to-Text API
- `gemini-credentials.json` - Gemini AI API

You can use the same service account key for both (it has all required permissions).

### 4.3 Setup Local Environment (Optional but Recommended)
```bash
./setup-local.sh
```

This script will:
- Create a Python virtual environment
- Install dependencies
- Setup environment configuration
- Test the setup

### 4.4 Verify Setup
Ensure you have these files in your project folder:
- ✅ `speech-credentials.json`
- ✅ `gemini-credentials.json`
- ✅ `.env` (created by setup script)

## 🚀 Step 5: Deploy to Cloud

### 5.1 Run Deployment Script
```bash
./deploy.sh
```

The script will:
1. Check prerequisites
2. Setup Google Cloud project
3. Enable required APIs
4. Create secrets in Google Cloud
5. Build and deploy your application

### 5.2 Follow the Prompts
The script will ask for:
- Your Google Cloud Project ID
- Confirmation for various steps

## 🔒 Step 6: Secure Your Deployment

### 6.1 Environment Variables
The deployment automatically sets up:
- Secure credential storage using Google Secret Manager
- Environment-based configuration
- Non-root container execution

### 6.2 Access Control
By default, your service allows public access. To restrict:

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

## 📊 Step 7: Monitor Your Deployment

### 7.1 Check Service Status
```bash
gcloud run services describe econome --region=us-central1
```

### 7.2 View Logs
```bash
gcloud logs read --service=econome --limit=50
```

### 7.3 Monitor Costs
1. Go to Google Cloud Console
2. Navigate to "Billing"
3. Set up budget alerts

## 🔧 Step 8: Custom Domain (Optional)

### 8.1 Map Custom Domain
```bash
gcloud run domain-mappings create \
    --service=econome \
    --domain=your-domain.com \
    --region=us-central1
```

### 8.2 Setup SSL Certificate
Google Cloud Run automatically provides SSL certificates for custom domains.

## 🚨 Troubleshooting

### Common Issues:

**1. Permission Denied Errors**
- Ensure your service account has all required roles
- Check that APIs are enabled

**2. Build Failures**
- Verify `gcp-credentials.json` is in the project root
- Check that Docker is running

**3. Service Won't Start**
- Check logs: `gcloud logs read --service=econome`
- Verify environment variables are set correctly

**4. Can't Access Service**
- Check if service allows public access
- Verify the service URL is correct

### Getting Help:
1. Check the logs first: `gcloud logs read --service=econome`
2. Verify your configuration: `gcloud run services describe econome --region=us-central1`
3. Test locally first: `python web_api.py`

## 💰 Cost Management

### Expected Costs:
- **Cloud Run**: Pay per request (very low for personal use)
- **Speech-to-Text**: $0.006 per 15 seconds
- **Gemini AI**: Varies by usage
- **Storage**: Minimal (data deleted after 24 hours)

### Cost Optimization:
1. Set up billing alerts
2. Use the free tier limits
3. Monitor usage in Cloud Console

## 🔄 Updates and Maintenance

### To Update Your Deployment:
```bash
# Make your code changes, then:
./deploy.sh
```

### To Delete Everything:
```bash
# Delete the service
gcloud run services delete econome --region=us-central1

# Delete the project (if you want to start over)
gcloud projects delete YOUR-PROJECT-ID
```

## ✅ Success!

Once deployed, your Econome service will be available at:
`https://econome-XXXXXXXXX-uc.a.run.app`

The deployment script will show you the exact URL.

## 🛡️ Security Best Practices

1. **Never commit credentials to version control**
2. **Use Google Secret Manager for sensitive data**
3. **Regularly rotate service account keys**
4. **Monitor access logs**
5. **Set up billing alerts**
6. **Use least-privilege IAM roles**

---

## 📝 Quick Reference

### Essential Commands:
```bash
# Deploy/Update
./deploy.sh

# Check status
gcloud run services describe econome --region=us-central1

# View logs
gcloud logs read --service=econome --limit=50

# Test locally
python web_api.py
```

### Important Files:
- `speech-credentials.json` - Your Google Cloud Speech-to-Text service account key (keep secure!)
- `gemini-credentials.json` - Your Gemini AI service account key (keep secure!)
- `.env` - Local environment configuration
- `cloudbuild.yaml` - Cloud Build configuration
- `Dockerfile` - Container configuration

### Service URLs:
- **Main App**: `https://your-service-url/`
- **Health Check**: `https://your-service-url/health`
- **API Docs**: `https://your-service-url/docs`

---

**Need Help?** Check the troubleshooting section above or review the logs for specific error messages.
