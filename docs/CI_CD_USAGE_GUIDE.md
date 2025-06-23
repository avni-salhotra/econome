# 🚀 CI/CD Usage Guide

## 📋 Overview
Your CI/CD pipeline is **working correctly** but requires proper usage. Here's the step-by-step process:

## 🔄 Normal Development Workflow

### 1. **Code Changes** 
```bash
# Make your changes
git add .
git commit -m "Your commit message"
git push origin main
```

### 2. **Automatic CI/CD (No Action Needed)**
- ✅ **Tests Run Automatically** (`01-test-and-validate.yml`)
- ✅ **Build & Push Automatically** (`02-build-and-push.yml`) 
- ✅ **Staging Deploy Automatically** (`03-deploy-staging.yml`)

### 3. **Production Deployment (Manual Trigger)**
```bash
# Deploy latest build to production
gh workflow run "04-deploy-production.yml" \
  --field image-tag="latest" \
  --field confirm-production="DEPLOY"

# Deploy specific build number to production  
gh workflow run "04-deploy-production.yml" \
  --field image-tag="35" \
  --field confirm-production="DEPLOY"
```

## 🏷️ Understanding Image Tags

Your CI/CD creates these tags automatically:
- `build-35` - Build number (use this for production)
- `latest` - Latest successful build
- `sha-abc123` - Git commit SHA

## 🚫 What NOT to Do

**❌ Don't manually build images:**
```bash
# DON'T DO THIS
gcloud builds submit --tag gcr.io/econome-hackathon/econome:manual-fix
```

**✅ Instead, use CI/CD:**
```bash
# DO THIS - just push to main
git push origin main
# Then wait for build-XX tag to appear
```

## 🔍 Monitoring Your Deployments

### Check Build Status
```bash
# List recent builds
gcloud container images list-tags gcr.io/econome-hackathon/econome --limit=5

# Check workflow status
gh run list --workflow="02-build-and-push.yml" --limit=3
```

### Check Deployment Status
```bash
# Production
gcloud run services describe econome --region=us-central1

# Staging  
gcloud run services describe econome-staging --region=us-central1
```

## 🚀 Quick Commands

### Deploy Latest Build to Production
```bash
gh workflow run "04-deploy-production.yml" \
  --field image-tag="latest" \
  --field confirm-production="DEPLOY"
```

### Emergency Rollback
```bash
gh workflow run "99-manual-operations.yml" \
  --field operation="rollback-production" \
  --field confirm-operation="CONFIRM"
```

### Health Check
```bash
gh workflow run "99-manual-operations.yml" \
  --field operation="health-check" \
  --field confirm-operation="CONFIRM"
```

## 📊 Current Status (as of deployment)

- **Latest CI/CD Build**: `build-35` (contains audio encoding fix)
- **Production**: Deploying from `build-18` → `build-35` 
- **Staging**: Already on latest
- **Manual Builds**: Please stop using these

## 🎯 Best Practices

1. **Always push to main** for automatic CI/CD
2. **Use GitHub Actions** for production deployment
3. **Monitor staging** before promoting to production
4. **Use build numbers** for specific deployments
5. **Never manual build** unless emergency

## 🔗 Links

- [GitHub Actions](https://github.com/avnisalhotra/econome/actions)
- [Production](https://econome-964713210810.us-central1.run.app)
- [Staging](https://econome-staging-964713210810.us-central1.run.app) 