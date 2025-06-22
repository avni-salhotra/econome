# 🚀 Deployment Guide

## 📋 Overview

This guide provides comprehensive instructions for deploying Econome using the enhanced CI/CD pipeline with staging and production environments.

## 🔧 Prerequisites

### **Required Tools**
- Google Cloud CLI (`gcloud`)
- Docker
- Git
- GitHub CLI (`gh`) - optional but recommended

### **Google Cloud Setup**
1. **Create or select a GCP project**
2. **Enable required APIs**:
   ```bash
   gcloud services enable \
     speech.googleapis.com \
     aiplatform.googleapis.com \
     firestore.googleapis.com \
     secretmanager.googleapis.com \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     containerregistry.googleapis.com
   ```

3. **Set up service account**:
   ```bash
   # Create service account
   gcloud iam service-accounts create econome-builder \
     --description="Service account for Econome CI/CD" \
     --display-name="Econome Builder"
   
   # Grant necessary permissions for deployment operations
   # Note: Specific roles are configured according to security requirements
   # Contact your platform team for the exact IAM configuration needed

   # Example permission setup (adjust roles based on your security policy):
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:econome-builder@PROJECT_ID.iam.gserviceaccount.com" \
     --role="DEPLOYMENT_ROLE"

   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:econome-builder@PROJECT_ID.iam.gserviceaccount.com" \
     --role="BUILD_ROLE"

   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:econome-builder@PROJECT_ID.iam.gserviceaccount.com" \
     --role="SECRET_ACCESS_ROLE"
   
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:econome-builder@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/storage.admin"
   ```

## 🔐 GitHub Secrets Setup

### **Required Repository Secrets**

Set these secrets in your GitHub repository (`Settings > Secrets and variables > Actions`):

```bash
# Main service account for CI/CD
GCP_CREDENTIALS = <base64-encoded-service-account-key>

# Project configuration  
GCP_PROJECT_ID = econome-hackathon
GCP_REGION = us-central1

# Container registry
GCR_HOSTNAME = gcr.io
```

### **How to Get Service Account Key**
```bash
# Create and download service account key
gcloud iam service-accounts keys create econome-builder-key.json \
  --iam-account=econome-builder@PROJECT_ID.iam.gserviceaccount.com

# Encode to base64 for GitHub secret
base64 -i econome-builder-key.json | pbcopy  # macOS
base64 -w 0 econome-builder-key.json         # Linux

# Add the output as GCP_CREDENTIALS secret in GitHub
```

## 🏗️ CI/CD Pipeline Overview

### **Pipeline Stages**

```
01-Test & Validate → 02-Build & Push → 03-Deploy Staging → 04-Deploy Production
       ↓                    ↓                ↓                     ↓
   • Unit Tests         • Build Image    • Auto Deploy        • Manual Approval
   • Security Scan      • Push to GCR    • Integration Tests   • Production Deploy
   • Code Quality       • Tag Images     • Health Checks       • Validation Tests
   • Docker Build       • Cleanup Old    • E2E Tests          • Monitoring
```

### **Workflow Files**
- `01-test-and-validate.yml` - Runs on PRs and feature branches
- `02-build-and-push.yml` - Runs on main branch pushes
- `03-deploy-staging.yml` - Auto-deploys to staging after build
- `04-deploy-production.yml` - Manual production deployment
- `99-manual-operations.yml` - Rollback, scaling, maintenance

## 🚀 Deployment Process

### **1. Development Workflow**

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/new-feature
gh pr create --title "Add new feature" --body "Description of changes"
```

**What happens**: `01-test-and-validate.yml` runs automatically

### **2. Main Branch Deployment**

```bash
# Merge PR to main
gh pr merge --squash

# Or push directly to main
git checkout main
git push origin main
```

**What happens**:
1. `02-build-and-push.yml` builds and pushes images
2. `03-deploy-staging.yml` deploys to staging automatically
3. Staging tests run and validate deployment

### **3. Production Deployment**

```bash
# Deploy to production (manual approval required)
gh workflow run "04 - Deploy Production" \
  --field image-tag="123" \
  --field confirm-production="DEPLOY"
```

**What happens**:
1. Pre-deployment validation
2. Production deployment with health checks
3. Post-deployment validation
4. Monitoring and alerting

## 🌍 Environment Configuration

### **Staging Environment**
- **Service**: `econome-staging`
- **Resources**: 1 CPU, 1GB RAM
- **Scaling**: 0-3 instances
- **URL**: `https://econome-staging-*.a.run.app`

### **Production Environment**
- **Service**: `econome`
- **Resources**: 2 CPU, 2GB RAM  
- **Scaling**: 1-10 instances
- **URL**: `https://econome-*.a.run.app`

## 🔧 Manual Operations

### **Rollback Production**
```bash
gh workflow run "99 - Manual Operations" \
  --field operation="rollback-production" \
  --field confirm-operation="CONFIRM"
```

### **Scale Production**
```bash
gh workflow run "99 - Manual Operations" \
  --field operation="scale-up-production" \
  --field scale-instances="15" \
  --field confirm-operation="CONFIRM"
```

### **Health Check**
```bash
gh workflow run "99 - Manual Operations" \
  --field operation="health-check" \
  --field confirm-operation="CONFIRM"
```

### **View Logs**
```bash
gh workflow run "99 - Manual Operations" \
  --field operation="logs-production" \
  --field confirm-operation="CONFIRM"
```

## 🔍 Monitoring & Troubleshooting

### **Health Check Endpoints**
- **Staging**: `https://econome-staging-*.a.run.app/health`
- **Production**: `https://econome-*.a.run.app/health`

### **Common Issues**

#### **Build Failures**
```bash
# Check build logs
gh run list --workflow="02 - Build & Push"
gh run view RUN_ID --log

# Common fixes
- Check requirements.txt syntax
- Verify Dockerfile syntax
- Ensure all tests pass locally
```

#### **Deployment Failures**
```bash
# Check deployment logs
gh run list --workflow="03 - Deploy Staging"
gh run view RUN_ID --log

# Common fixes
- Verify service account permissions
- Check Cloud Run quotas
- Validate environment variables
```

#### **Service Not Responding**
```bash
# Check service status
gcloud run services describe econome --region=us-central1

# Check logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Manual health check
curl -f https://econome-*.a.run.app/health
```

## 📊 Performance Monitoring

### **Key Metrics**
- **Response Time**: < 2s for health checks
- **Error Rate**: < 1% for production
- **Availability**: > 99.9% uptime
- **Scaling**: Auto-scale based on traffic

### **Monitoring Tools**
- **Google Cloud Monitoring**: Built-in metrics
- **Cloud Logging**: Structured logs
- **GitHub Actions**: CI/CD pipeline status

## 🔒 Security Best Practices

### **Secret Management**
- All secrets stored in Google Secret Manager
- Service account keys rotated regularly
- No secrets in code or environment variables

### **Access Control**
- Principle of least privilege
- Service account-based authentication
- Audit logging enabled

### **Network Security**
- HTTPS/WSS only
- Cloud Run ingress controls
- VPC connector (if needed)

## 🔄 Backup & Recovery

### **Automated Backups**
- Container images stored in GCR
- Build artifacts stored in Cloud Storage
- Configuration stored in Git

### **Recovery Procedures**
1. **Rollback**: Use manual operations workflow
2. **Rebuild**: Re-run CI/CD pipeline
3. **Emergency**: Deploy from specific image tag

## 📈 Scaling Considerations

### **Horizontal Scaling**
- Cloud Run auto-scaling (0-10 instances)
- Concurrent request handling (100 per instance)
- Cold start optimization

### **Vertical Scaling**
- CPU: 1-4 vCPUs per instance
- Memory: 1-8GB per instance
- Timeout: Up to 3600 seconds

## 🎯 Next Steps

1. **Set up monitoring alerts**
2. **Configure custom domain** (optional)
3. **Implement blue-green deployment** (advanced)
4. **Add performance testing** (load testing)

---

*This deployment guide is maintained alongside the codebase and updated with each release.*
