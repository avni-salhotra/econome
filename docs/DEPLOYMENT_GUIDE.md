# 🚀 Production Deployment Guide

## 📋 Overview

This guide provides comprehensive instructions for deploying Econome to production environments on Google Cloud Platform. It covers everything from initial setup to monitoring and maintenance, following Google Cloud best practices and enterprise deployment standards.

---

## 🎯 Prerequisites

### Required Accounts & Permissions
- **Google Cloud Project**: With billing enabled and appropriate quotas
- **IAM Permissions**: Project Editor or custom role with specific permissions
- **Service Accounts**: For Speech-to-Text V2 and Vertex AI Gemini
- **GitHub Repository**: For CI/CD pipeline integration

### Required APIs
```bash
# Enable required Google Cloud APIs
gcloud services enable run.googleapis.com
gcloud services enable speech.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### Development Tools
- **Google Cloud CLI**: Latest version (≥400.0.0)
- **Docker**: For local containerization testing
- **Git**: For repository management
- **Python 3.12+**: For local development

---

## 🏗️ Infrastructure Setup

### 1. Project Configuration

```bash
# Set project variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export SERVICE_NAME="econome"

# Configure gcloud CLI
gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
```

### 2. Service Account Creation

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create econome-runner \
    --display-name="Econome Cloud Run Service Account" \
    --description="Service account for Econome production deployment"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/speech.client"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. Firestore Database Setup

```bash
# Create Firestore database in Native mode
gcloud firestore databases create \
    --region=$REGION \
    --type=firestore-native

# Create indexes for performance optimization
gcloud firestore indexes composite create \
    --collection-group=sessions \
    --field-config field-path=expires_at,order=ascending \
    --field-config field-path=__name__,order=ascending
```

---

## 🔐 Secrets Management

### 1. Create Service Account Keys

```bash
# Create keys for service accounts
gcloud iam service-accounts keys create speech-credentials.json \
    --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com

gcloud iam service-accounts keys create gemini-credentials.json \
    --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com
```

### 2. Store Secrets in Secret Manager

```bash
# Store speech credentials
gcloud secrets create speech-credentials \
    --data-file=speech-credentials.json \
    --replication-policy="automatic"

# Store Gemini credentials  
gcloud secrets create gemini-credentials \
    --data-file=gemini-credentials.json \
    --replication-policy="automatic"

# Store environment configuration
echo "production" | gcloud secrets create environment --data-file=-
echo "INFO" | gcloud secrets create log-level --data-file=-
echo "https://your-domain.com" | gcloud secrets create base-url --data-file=-
```

### 3. Grant Secret Access

```bash
# Grant Cloud Run service account access to secrets
gcloud secrets add-iam-policy-binding speech-credentials \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding gemini-credentials \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 🐳 Container Build & Registry

### 1. Build Production Container

```bash
# Navigate to project root
cd /path/to/econome

# Build production-optimized container
docker build -f devops/Dockerfile \
    --target production \
    --build-arg ENVIRONMENT=production \
    --tag gcr.io/$PROJECT_ID/econome:latest \
    --tag gcr.io/$PROJECT_ID/econome:$(git rev-parse --short HEAD) \
    .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/econome:latest
docker push gcr.io/$PROJECT_ID/econome:$(git rev-parse --short HEAD)
```

### 2. Container Optimization

```dockerfile
# Production Dockerfile optimization
FROM python:3.12-slim as production

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libportaudio2 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash econome
USER econome
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy application code
COPY --chown=econome:econome src/ src/
COPY --chown=econome:econome frontend/ frontend/

# Security: Remove unnecessary files
RUN find . -name "*.pyc" -delete && \
    find . -name "__pycache__" -type d -exec rm -rf {} +

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Production command
CMD ["python", "-m", "uvicorn", "src.web_api:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

---

## ☁️ Cloud Run Deployment

### 1. Production Service Configuration

```yaml
# cloud-run-service.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: econome
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/binary-authorization: require-attestations
spec:
  template:
    metadata:
      annotations:
        # Auto-scaling configuration
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/targetConcurrencyUtilization: "70"
        autoscaling.knative.dev/scaleDownDelay: "300s"
        
        # Performance optimization
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "4Gi"
        run.googleapis.com/cpu: "2"
        
        # Security
        run.googleapis.com/vpc-access-connector: projects/$PROJECT_ID/locations/$REGION/connectors/default
        
    spec:
      containerConcurrency: 1000
      timeoutSeconds: 3600
      serviceAccountName: econome-runner@$PROJECT_ID.iam.gserviceaccount.com
      
      containers:
      - image: gcr.io/$PROJECT_ID/econome:latest
        
        resources:
          limits:
            cpu: "2"
            memory: "4Gi"
          requests:
            cpu: "1"
            memory: "2Gi"
            
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: PROJECT_ID
          value: "$PROJECT_ID"
        - name: LOG_LEVEL
          value: "INFO"
        - name: PORT
          value: "8080"
          
        # Secret mounting
        volumeMounts:
        - name: speech-credentials
          mountPath: /app/secrets/speech
          readOnly: true
        - name: gemini-credentials
          mountPath: /app/secrets/gemini
          readOnly: true
          
        # Health monitoring
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          timeoutSeconds: 10
          periodSeconds: 30
          
        startupProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          
      volumes:
      - name: speech-credentials
        secret:
          secretName: speech-credentials
      - name: gemini-credentials
        secret:
          secretName: gemini-credentials
```

### 2. Deploy to Cloud Run

```bash
# Deploy using gcloud CLI with production configuration
gcloud run deploy econome \
    --image=gcr.io/$PROJECT_ID/econome:latest \
    --region=$REGION \
    --platform=managed \
    --service-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com \
    --memory=4Gi \
    --cpu=2 \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=1000 \
    --timeout=3600 \
    --set-env-vars="ENVIRONMENT=production,PROJECT_ID=$PROJECT_ID,LOG_LEVEL=INFO" \
    --set-secrets="/app/secrets/speech/credentials.json=speech-credentials:latest" \
    --set-secrets="/app/secrets/gemini/credentials.json=gemini-credentials:latest" \
    --allow-unauthenticated \
    --port=8080

# Get service URL
export SERVICE_URL=$(gcloud run services describe econome --region=$REGION --format="value(status.url)")
echo "Service deployed at: $SERVICE_URL"
```

---

## 🔄 CI/CD Pipeline Setup

### 1. GitHub Actions Configuration

```yaml
# .github/workflows/05-auto-production-deploy.yml
name: "05 - Auto Production Deploy"

on:
  push:
    branches: [ main ]

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  SERVICE_NAME: econome

jobs:
  deploy-production:
    name: "🌍 Deploy to Production"
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - name: "📥 Checkout code"
      uses: actions/checkout@v4

    - name: "🔑 Authenticate to Google Cloud"
      uses: google-github-actions/auth@v2
      with:
        credentials_json: ${{ secrets.GCP_SA_KEY }}

    - name: "⚙️ Set up Cloud SDK"
      uses: google-github-actions/setup-gcloud@v2

    - name: "🏗️ Trigger Cloud Build"
      run: |
        gcloud builds submit \
          --config=devops/cloudbuild/deploy-production.yaml \
          --substitutions=_DEPLOY_ENV=production,_SERVICE_URL=${{ secrets.PRODUCTION_URL }} \
          --region=$REGION

    - name: "🔍 Verify deployment"
      run: |
        # Wait for deployment to complete
        sleep 60
        
        # Health check
        response=$(curl -s -o /dev/null -w "%{http_code}" ${{ secrets.PRODUCTION_URL }}/health)
        if [ $response -eq 200 ]; then
          echo "✅ Production deployment successful"
        else
          echo "❌ Production deployment failed - HTTP $response"
          exit 1
        fi

    - name: "📊 Performance validation"
      run: |
        # Basic performance test
        time curl -s ${{ secrets.PRODUCTION_URL }}/health
        
        # Load test with ab (if available)
        if command -v ab &> /dev/null; then
          ab -n 100 -c 10 ${{ secrets.PRODUCTION_URL }}/health
        fi
```

### 2. Cloud Build Configuration

```yaml
# devops/cloudbuild/deploy-production.yaml
steps:
- id: 'deploy-to-cloud-run'
  name: 'gcr.io/cloud-builders/gcloud'
  args:
  - 'run'
  - 'deploy'
  - 'econome'
  - '--image=gcr.io/$PROJECT_ID/econome:$COMMIT_SHA'
  - '--region=us-central1'
  - '--platform=managed'
  - '--memory=4Gi'
  - '--cpu=2'
  - '--min-instances=1'
  - '--max-instances=10'
  - '--concurrency=1000'
  - '--timeout=3600'
  - '--service-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com'
  - '--set-env-vars=ENVIRONMENT=production,PROJECT_ID=$PROJECT_ID'
  - '--allow-unauthenticated'

- id: 'verify-deployment'
  name: 'gcr.io/cloud-builders/curl'
  args: ['https://econome-service-url.run.app/health']

substitutions:
  _DEPLOY_ENV: 'production'
  _SERVICE_URL: 'https://econome-service-url.run.app'

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: 'E2_HIGHCPU_8'
```

---

## 📊 Monitoring & Observability

### 1. Cloud Monitoring Setup

```bash
# Enable Cloud Monitoring API
gcloud services enable monitoring.googleapis.com

# Create custom dashboard
gcloud alpha monitoring dashboards create \
    --config-from-file=devops/monitoring/dashboard.json
```

### 2. Custom Metrics Configuration

```python
# Production monitoring implementation
from google.cloud import monitoring_v3

class ProductionMetrics:
    """Production metrics collection for Cloud Monitoring"""
    
    def __init__(self, project_id: str):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{project_id}"
        
    async def record_conversation_metrics(self, session: ConversationSession):
        """Record comprehensive conversation metrics"""
        
        # Speech recognition latency
        await self.record_metric(
            "custom.googleapis.com/econome/speech_latency",
            session.get_speech_latency_ms(),
            {"session_id": session.session_id}
        )
        
        # AI processing time
        await self.record_metric(
            "custom.googleapis.com/econome/ai_processing_time",
            session.get_ai_processing_ms(),
            {"session_id": session.session_id}
        )
        
        # User satisfaction score
        await self.record_metric(
            "custom.googleapis.com/econome/user_satisfaction",
            session.get_satisfaction_score(),
            {"session_id": session.session_id}
        )
        
        # Cost metrics
        await self.record_metric(
            "custom.googleapis.com/econome/api_cost",
            session.get_total_cost_usd(),
            {"session_id": session.session_id, "cost_type": "total"}
        )
```

### 3. Alerting Configuration

```yaml
# monitoring/alerts.yaml
displayName: "Econome Production Alerts"
combiner: OR
conditions:
- displayName: "High Error Rate"
  conditionThreshold:
    filter: 'resource.type="cloud_run_revision" resource.label.service_name="econome"'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 0.05  # 5% error rate
    duration: 300s

- displayName: "High Latency"
  conditionThreshold:
    filter: 'resource.type="cloud_run_revision" resource.label.service_name="econome"'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 5000  # 5 second latency
    duration: 180s

- displayName: "Memory Usage High"
  conditionThreshold:
    filter: 'resource.type="cloud_run_revision" resource.label.service_name="econome"'
    comparison: COMPARISON_GREATER_THAN
    thresholdValue: 0.85  # 85% memory usage
    duration: 300s

notificationChannels:
- projects/$PROJECT_ID/notificationChannels/email-alerts
- projects/$PROJECT_ID/notificationChannels/slack-alerts
```

---

## 🔄 Blue-Green Deployment

### 1. Blue-Green Strategy

```bash
# Deploy new version to staging URL
gcloud run deploy econome-staging \
    --image=gcr.io/$PROJECT_ID/econome:$NEW_VERSION \
    --region=$REGION \
    --no-traffic

# Validate staging deployment
curl -f https://econome-staging-url.run.app/health

# If validation passes, update traffic
gcloud run services update-traffic econome \
    --to-revisions=econome-staging=100 \
    --region=$REGION

# Monitor for 10 minutes, rollback if issues
sleep 600

# Check error rates
ERROR_RATE=$(gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit=100 --format="value(timestamp)" | wc -l)

if [ $ERROR_RATE -gt 5 ]; then
    echo "High error rate detected, rolling back"
    gcloud run services update-traffic econome \
        --to-revisions=PREVIOUS_REVISION=100 \
        --region=$REGION
fi
```

### 2. Canary Deployment

```bash
# Deploy new version with 10% traffic
gcloud run deploy econome \
    --image=gcr.io/$PROJECT_ID/econome:$NEW_VERSION \
    --region=$REGION \
    --tag=canary

# Split traffic: 90% to stable, 10% to canary
gcloud run services update-traffic econome \
    --to-revisions=econome-stable=90,econome-canary=10 \
    --region=$REGION

# Monitor canary performance
# If successful, gradually increase traffic
gcloud run services update-traffic econome \
    --to-revisions=econome-stable=50,econome-canary=50 \
    --region=$REGION

# Final cutover
gcloud run services update-traffic econome \
    --to-revisions=econome-canary=100 \
    --region=$REGION
```

---

## 🛡️ Security Hardening

### 1. Network Security

```bash
# Create VPC connector for private networking
gcloud compute networks vpc-access connectors create econome-connector \
    --region=$REGION \
    --subnet=default \
    --subnet-project=$PROJECT_ID \
    --min-instances=2 \
    --max-instances=10

# Configure firewall rules
gcloud compute firewall-rules create allow-econome-internal \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:8080 \
    --source-ranges=10.0.0.0/8 \
    --target-tags=econome
```

### 2. Container Security

```bash
# Enable Binary Authorization
gcloud container binauthz policy import policy.yaml

# Create attestor for container verification
gcloud container binauthz attestors create prod-attestor \
    --attestation-authority-note-project=$PROJECT_ID \
    --attestation-authority-note=prod-note \
    --description="Production attestor for Econome"
```

### 3. Secrets Rotation

```bash
#!/bin/bash
# scripts/rotate-secrets.sh

echo "🔄 Starting secrets rotation..."

# Create new service account key
gcloud iam service-accounts keys create new-speech-credentials.json \
    --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com

# Update secret with new key
gcloud secrets versions add speech-credentials \
    --data-file=new-speech-credentials.json

# Update Cloud Run service to use new secret version
gcloud run services update econome \
    --region=$REGION \
    --update-secrets="/app/secrets/speech/credentials.json=speech-credentials:latest"

# Verify deployment
curl -f https://your-service-url.run.app/health

# Delete old key after verification
OLD_KEY_ID=$(gcloud iam service-accounts keys list \
    --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com \
    --format="value(name)" \
    --filter="validAfterTime<-P7D" \
    --limit=1)

if [ ! -z "$OLD_KEY_ID" ]; then
    gcloud iam service-accounts keys delete $OLD_KEY_ID \
        --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com \
        --quiet
    echo "✅ Old key deleted: $OLD_KEY_ID"
fi

echo "✅ Secrets rotation complete"
```

---

## 🧪 Production Validation

### 1. Health Checks

```bash
#!/bin/bash
# scripts/production-healthcheck.sh

SERVICE_URL="https://your-service-url.run.app"

echo "🔍 Starting production validation..."

# Basic health check
echo "Testing health endpoint..."
if curl -f $SERVICE_URL/health > /dev/null 2>&1; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi

# API functionality test
echo "Testing conversation API..."
RESPONSE=$(curl -s -X POST $SERVICE_URL/api/conversation/start \
    -H "Content-Type: application/json" \
    -d '{"mode": "frontend_streaming"}')

if echo $RESPONSE | grep -q "connection_id"; then
    echo "✅ API test passed"
else
    echo "❌ API test failed"
    exit 1
fi

# Performance test
echo "Testing response time..."
RESPONSE_TIME=$(curl -o /dev/null -s -w "%{time_total}" $SERVICE_URL/health)
if (( $(echo "$RESPONSE_TIME < 2.0" | bc -l) )); then
    echo "✅ Performance test passed ($RESPONSE_TIME seconds)"
else
    echo "⚠️ Performance test warning: ${RESPONSE_TIME}s response time"
fi

echo "✅ Production validation complete"
```

### 2. Load Testing

```bash
# Install Apache Bench for load testing
sudo apt-get install apache2-utils

# Basic load test
ab -n 1000 -c 10 https://your-service-url.run.app/health

# Conversation API load test
echo '{"mode": "frontend_streaming"}' > test-payload.json
ab -n 100 -c 5 -p test-payload.json -T application/json \
   https://your-service-url.run.app/api/conversation/start
```

---

## 🔧 Maintenance & Operations

### 1. Backup Procedures

```bash
#!/bin/bash
# scripts/backup-configuration.sh

echo "📦 Starting configuration backup..."

# Export Cloud Run service configuration
gcloud run services describe econome \
    --region=$REGION \
    --format="export" > backup/cloud-run-config-$(date +%Y%m%d).yaml

# Export Firestore indexes
gcloud firestore indexes list \
    --format="value(name)" > backup/firestore-indexes-$(date +%Y%m%d).txt

# Export IAM policies
gcloud projects get-iam-policy $PROJECT_ID \
    --format=json > backup/iam-policy-$(date +%Y%m%d).json

# Export secrets list (not the actual secret values)
gcloud secrets list \
    --format="value(name)" > backup/secrets-list-$(date +%Y%m%d).txt

echo "✅ Configuration backup complete"
```

### 2. Scaling Management

```bash
# Scale up for high traffic
gcloud run services update econome \
    --region=$REGION \
    --min-instances=3 \
    --max-instances=20

# Scale down for cost optimization
gcloud run services update econome \
    --region=$REGION \
    --min-instances=1 \
    --max-instances=10
```

### 3. Log Analysis

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=econome" \
    --limit=100 \
    --format="table(timestamp,severity,textPayload)"

# Monitor error rates
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" \
    --limit=50 \
    --format="table(timestamp,severity,textPayload)"

# Export logs for analysis
gcloud logging read "resource.type=cloud_run_revision" \
    --format=json > logs/econome-logs-$(date +%Y%m%d).json
```

---

## 🆘 Troubleshooting

### Common Issues & Solutions

#### 1. Cold Start Latency
**Problem**: High latency on first request after idle period
**Solution**:
```bash
# Increase minimum instances
gcloud run services update econome \
    --region=$REGION \
    --min-instances=2
```

#### 2. Memory Issues
**Problem**: Out of memory errors during high load
**Solution**:
```bash
# Increase memory allocation
gcloud run services update econome \
    --region=$REGION \
    --memory=6Gi
```

#### 3. API Rate Limits
**Problem**: Google Cloud API quota exceeded
**Solution**:
```bash
# Check current quotas
gcloud compute project-info describe --format="table(quotas.metric,quotas.limit,quotas.usage)"

# Request quota increase through Cloud Console
```

#### 4. Secret Access Issues
**Problem**: Service cannot access secrets
**Solution**:
```bash
# Verify service account permissions
gcloud secrets get-iam-policy speech-credentials

# Re-grant access if needed
gcloud secrets add-iam-policy-binding speech-credentials \
    --member="serviceAccount:econome-runner@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 📋 Production Checklist

### Pre-Deployment
- [ ] All APIs enabled
- [ ] Service accounts created with minimal permissions
- [ ] Secrets stored in Secret Manager
- [ ] Firestore database configured
- [ ] Container built and tested
- [ ] Security scanning passed
- [ ] Load testing completed

### Deployment
- [ ] Cloud Run service deployed
- [ ] Health checks passing
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] DNS configured (if using custom domain)
- [ ] SSL certificates validated

### Post-Deployment
- [ ] Performance validation completed
- [ ] Security audit passed
- [ ] Backup procedures tested
- [ ] Documentation updated
- [ ] Team trained on operations
- [ ] Incident response plan activated

---

## 📚 Additional Resources

### Google Cloud Documentation
- [Cloud Run Production Guide](https://cloud.google.com/run/docs/deploying)
- [Speech-to-Text Best Practices](https://cloud.google.com/speech-to-text/docs/best-practices)
- [Secret Manager Security](https://cloud.google.com/secret-manager/docs/best-practices)

### Monitoring & Alerting
- [Cloud Monitoring Setup](https://cloud.google.com/monitoring/quickstart)
- [Alerting Policies](https://cloud.google.com/monitoring/alerts)
- [Log Analysis](https://cloud.google.com/logging/docs/view/logs-viewer)

### Security & Compliance
- [Security Best Practices](https://cloud.google.com/security/best-practices)
- [Compliance Resources](https://cloud.google.com/security/compliance)
- [Privacy Engineering](https://cloud.google.com/privacy)

---

<div align="center">
  <p><strong>🚀 Production Deployment Guide</strong></p>
  <p><em>Comprehensive deployment instructions for enterprise-grade systems</em></p>
</div>
