# 🔐 Secrets Management Guide

This guide explains how to properly manage secrets and credentials for the Econome project using Google Secret Manager and secure deployment practices.

## 🎯 Overview

**Local Development**: Uses credential files  
**Production**: Uses Google Secret Manager  
**CI/CD**: Uses GitHub Secrets + Google Secret Manager  

## 🏠 Local Development Setup

### 1. Create Service Account
```bash
# Create service account
gcloud iam service-accounts create econome-service \
    --description="Service account for Econome application" \
    --display-name="Econome Service Account"

# Get your project ID
PROJECT_ID=$(gcloud config get-value project)

# Grant necessary permissions for application runtime
# Note: Specific roles are configured according to security requirements
# Contact your platform team for the exact IAM configuration needed

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="SPEECH_SERVICE_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="AI_PLATFORM_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="SECRET_ACCESS_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-service@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/firestore.user"
```

### 2. Download Credentials
```bash
# Create and download service account key
gcloud iam service-accounts keys create speech-credentials.json \
    --iam-account=econome-service@$PROJECT_ID.iam.gserviceaccount.com

# Copy for Gemini (same service account, different name for clarity)
cp speech-credentials.json gemini-credentials.json
```

### 3. Setup Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your project ID
sed -i "s/your-project-id-here/$PROJECT_ID/g" .env
```

## ☁️ Production Setup (Google Secret Manager)

### 1. Enable Secret Manager API
```bash
gcloud services enable secretmanager.googleapis.com
```

### 2. Create Secrets
```bash
# Create speech credentials secret
gcloud secrets create speech-credentials --data-file=speech-credentials.json

# Create gemini credentials secret
gcloud secrets create gemini-credentials --data-file=gemini-credentials.json

# Verify secrets were created
gcloud secrets list
```

### 3. Grant Cloud Run Access
```bash
# Get Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_RUN_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant secret access
gcloud secrets add-iam-policy-binding speech-credentials \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gemini-credentials \
    --member="serviceAccount:$CLOUD_RUN_SA" \
    --role="roles/secretmanager.secretAccessor"
```

## 🚀 GitHub Actions Setup

### 1. Create GitHub Secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions

Create these secrets:

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `GCP_PROJECT_ID` | Your Google Cloud Project ID | `gcloud config get-value project` |
| `GCP_SA_KEY` | Service account key for deployment | Create deployment service account |
| `SPEECH_CREDENTIALS` | Speech service account JSON | Content of `speech-credentials.json` |
| `GEMINI_CREDENTIALS` | Gemini service account JSON | Content of `gemini-credentials.json` |

### 2. Create Deployment Service Account
```bash
# Create deployment service account
gcloud iam service-accounts create github-deploy \
    --description="Service account for GitHub Actions deployment" \
    --display-name="GitHub Deploy"

# Grant deployment permissions for CI/CD operations
# Note: Specific roles are configured according to security requirements
# Contact your platform team for the exact IAM configuration needed

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="DEPLOYMENT_ADMIN_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="BUILD_SERVICE_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="SECRET_MANAGEMENT_ROLE"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:github-deploy@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-deploy-key.json \
    --iam-account=github-deploy@$PROJECT_ID.iam.gserviceaccount.com

# Copy content to GitHub secret GCP_SA_KEY
cat github-deploy-key.json
```

### 3. Setup GitHub Secrets
```bash
# Get project ID
echo "GCP_PROJECT_ID: $(gcloud config get-value project)"

# Get service account key (copy this to GCP_SA_KEY)
echo "GCP_SA_KEY:"
cat github-deploy-key.json

# Get credentials (copy these to respective secrets)
echo "SPEECH_CREDENTIALS:"
cat speech-credentials.json

echo "GEMINI_CREDENTIALS:"
cat gemini-credentials.json
```

## 🔒 Security Best Practices

### ✅ DO
- Use Google Secret Manager for production secrets
- Use different service accounts for different purposes
- Rotate service account keys regularly
- Use least-privilege IAM roles
- Monitor secret access logs
- Use GitHub Secrets for CI/CD credentials
- Keep credential files out of version control

### ❌ DON'T
- Commit credential files to Git
- Use the same service account key everywhere
- Share service account keys via email/chat
- Use overly broad IAM permissions
- Store secrets in environment variables in production
- Use default service accounts for applications

## 🔍 Verification

### Check Local Setup
```bash
# Verify credentials work
python test_gemini.py
python test_stt_simple.py

# Check environment
python -c "import os; print('Project:', os.getenv('GOOGLE_CLOUD_PROJECT'))"
```

### Check Production Setup
```bash
# List secrets
gcloud secrets list

# Check secret access
gcloud secrets versions access latest --secret="speech-credentials" --format="get(payload.data)" | base64 -d | jq .project_id

# Test Cloud Run deployment
curl https://your-service-url/health
```

### Check GitHub Actions
```bash
# Verify GitHub secrets are set
gh secret list

# Check workflow runs
gh run list
```

## 🚨 Troubleshooting

### Common Issues

**1. Permission Denied**
```bash
# Check IAM permissions
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:serviceAccount:your-service-account"
```

**2. Secret Not Found**
```bash
# List all secrets
gcloud secrets list

# Check secret versions
gcloud secrets versions list speech-credentials
```

**3. GitHub Actions Failing**
- Check that all GitHub secrets are set correctly
- Verify service account has necessary permissions
- Check Cloud Build logs in Google Cloud Console

**4. Local Development Issues**
```bash
# Check credential file exists and is valid
ls -la *-credentials.json
python -c "import json; print(json.load(open('speech-credentials.json'))['project_id'])"

# Test authentication
gcloud auth application-default login
```

## 📊 Monitoring

### Secret Access Logs
```bash
# View secret access logs
gcloud logging read "resource.type=gce_instance AND protoPayload.serviceName=secretmanager.googleapis.com" --limit=50
```

### Service Account Usage
```bash
# Check service account activity
gcloud logging read "protoPayload.authenticationInfo.principalEmail:econome-service@$PROJECT_ID.iam.gserviceaccount.com" --limit=20
```

## 🔄 Rotation Schedule

**Recommended rotation schedule:**
- **Service Account Keys**: Every 90 days
- **GitHub Secrets**: When service account keys are rotated
- **Secret Manager Secrets**: When underlying credentials change

**Rotation Process:**
1. Create new service account key
2. Update Secret Manager
3. Update GitHub Secrets
4. Test deployment
5. Delete old key

---

## 📞 Support

If you encounter issues with secrets management:

1. Check the [troubleshooting section](#-troubleshooting)
2. Verify IAM permissions
3. Check Google Cloud Console logs
4. Review GitHub Actions workflow logs

**Security Incident Response:**
If credentials are accidentally exposed:
1. Immediately disable the service account
2. Create new credentials
3. Update all secrets
4. Review access logs
5. Rotate all related secrets
