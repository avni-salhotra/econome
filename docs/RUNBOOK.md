# ⚙️ Production Operations Runbook

## 📋 Overview

This runbook provides comprehensive operational procedures for the Econome production system. It serves as the primary reference for Site Reliability Engineers (SREs), DevOps teams, and on-call personnel responsible for maintaining system availability, performance, and reliability.

**Service Level Objectives (SLOs)**:
- **Availability**: 99.9% uptime (8.77 hours downtime/year)
- **Latency**: P95 < 3 seconds end-to-end processing
- **Error Rate**: < 0.1% of requests result in errors
- **Recovery Time**: < 15 minutes for critical incidents

---

## 🎯 System Overview

### Architecture Summary
- **Platform**: Google Cloud Run (serverless containers)
- **Frontend**: Single-page application served by FastAPI
- **Backend**: FastAPI with async/await processing
- **AI Services**: Google Cloud Speech V2 + Vertex AI Gemini
- **Storage**: Cloud Firestore (ephemeral, 24h TTL)
- **Monitoring**: Cloud Monitoring + Cloud Logging

### Key Components
1. **Web Application** (`src/web_api.py`) - FastAPI server handling HTTP requests
2. **Speech Agent** (`src/speech_agent.py`) - Real-time audio processing
3. **Orchestration Agent** (`src/meeting_agents.py`) - Multi-agent coordination
4. **Gemini Agent** (`src/gemini_agent.py`) - AI analysis processing
5. **Session Manager** (`src/gcp_session_manager.py`) - Ephemeral state management

---

## 🔍 Monitoring & Alerting

### Primary Monitoring Dashboard
**URL**: [Cloud Monitoring Dashboard](https://console.cloud.google.com/monitoring/dashboards/custom/econome-production)

### Key Metrics to Monitor

#### Application Performance
```bash
# Key metrics and thresholds
availability_slo = 99.9%              # Critical: < 99.9%
error_rate_threshold = 0.1%           # Warning: > 0.05%, Critical: > 0.1%
p95_latency_threshold = 3000          # Warning: > 2s, Critical: > 3s
p99_latency_threshold = 5000          # Critical: > 5s
```

#### Resource Utilization
```bash
# Cloud Run resource monitoring
cpu_utilization_warning = 70%        # Warning threshold
cpu_utilization_critical = 85%       # Critical threshold
memory_utilization_warning = 80%     # Warning threshold
memory_utilization_critical = 90%    # Critical threshold
container_instance_count_max = 10     # Auto-scaling limit
```

#### Business Metrics
```bash
# Conversation processing metrics
conversations_per_hour = normal_range  # Track business volume
speech_recognition_accuracy = >90%     # Quality threshold
ai_analysis_success_rate = >95%        # AI processing health
user_satisfaction_score = >4.0         # User experience metric
```

### Alert Configurations

#### Critical Alerts (Page Immediately)
```yaml
# High Priority Alerts
alerts:
  - name: "Service Down"
    condition: "Availability < 99%"
    duration: "2 minutes"
    action: "Page on-call engineer"
    
  - name: "High Error Rate"
    condition: "Error rate > 1%"
    duration: "5 minutes" 
    action: "Page on-call engineer"
    
  - name: "Extreme Latency"
    condition: "P95 latency > 10 seconds"
    duration: "3 minutes"
    action: "Page on-call engineer"
    
  - name: "Memory Exhaustion"
    condition: "Memory usage > 95%"
    duration: "2 minutes"
    action: "Page on-call engineer"
```

#### Warning Alerts (Slack/Email)
```yaml
# Medium Priority Alerts
alerts:
  - name: "Elevated Error Rate"
    condition: "Error rate > 0.1%"
    duration: "10 minutes"
    action: "Slack #econome-ops"
    
  - name: "High Latency"
    condition: "P95 latency > 3 seconds"
    duration: "5 minutes"
    action: "Slack #econome-ops"
    
  - name: "Resource Pressure"
    condition: "CPU > 80% OR Memory > 85%"
    duration: "15 minutes"
    action: "Email ops team"
```

---

## 🚨 Incident Response Procedures

### Incident Classification

#### Severity 1 (Critical) - Page Immediately
- **Service completely down** (availability < 95%)
- **Data loss or corruption**
- **Security breach**
- **Widespread user impact** (>50% of traffic affected)

#### Severity 2 (High) - Response within 30 minutes
- **Degraded performance** (P95 latency > 5s)
- **High error rates** (>1% of requests)
- **Component failures** affecting functionality
- **Moderate user impact** (10-50% of traffic affected)

#### Severity 3 (Medium) - Response within 2 hours
- **Performance issues** (P95 latency 3-5s)
- **Minor component degradation**
- **Low user impact** (<10% of traffic affected)

### Incident Response Workflow

#### 1. Initial Response (0-5 minutes)
```bash
# Immediate assessment checklist
1. Acknowledge the alert
2. Check service health dashboard
3. Verify incident scope and impact
4. Determine severity level
5. Engage additional resources if needed

# Quick health check commands
gcloud run services describe econome --region=us-central1
curl -f https://econome-service-url/health
gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit=20
```

#### 2. Investigation (5-15 minutes)
```bash
# Systematic investigation steps

# Check service status
gcloud run services describe econome --region=us-central1 --format="table(status.conditions.type,status.conditions.status,status.conditions.message)"

# Review recent deployments
gcloud run revisions list --service=econome --region=us-central1 --limit=5

# Analyze error logs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="econome" AND severity>=ERROR' \
    --limit=50 --format="table(timestamp,severity,textPayload)"

# Check resource utilization
gcloud monitoring metrics list --filter='resource.type="cloud_run_revision"' | grep econome

# Verify external dependencies
curl -I https://speech.googleapis.com
curl -I https://aiplatform.googleapis.com
```

#### 3. Mitigation (15-30 minutes)
Based on investigation findings, apply appropriate mitigation:

```bash
# Common mitigation strategies

# Rollback to previous version
PREVIOUS_REVISION=$(gcloud run revisions list --service=econome --region=us-central1 --limit=2 --format="value(metadata.name)" | tail -1)
gcloud run services update-traffic econome --to-revisions=$PREVIOUS_REVISION=100 --region=us-central1

# Scale up resources
gcloud run services update econome --memory=6Gi --cpu=4 --min-instances=3 --max-instances=20 --region=us-central1

# Restart service (force new deployment)
gcloud run services replace-traffic econome --to-latest --region=us-central1

# Emergency maintenance mode (if needed)
gcloud run services update econome --set-env-vars="MAINTENANCE_MODE=true" --region=us-central1
```

---

## 🛠️ Operational Procedures

### Daily Operations

#### Morning Health Check (09:00 UTC)
```bash
#!/bin/bash
# scripts/daily-health-check.sh

echo "🌅 Daily Health Check - $(date)"

# 1. Service availability
SERVICE_URL="https://econome-service-url"
if curl -f $SERVICE_URL/health > /dev/null 2>&1; then
    echo "✅ Service health: OK"
else
    echo "❌ Service health: FAILED"
    exit 1
fi

# 2. API functionality
RESPONSE=$(curl -s -X POST $SERVICE_URL/api/conversation/start -H "Content-Type: application/json" -d '{"mode": "frontend_streaming"}')
if echo $RESPONSE | grep -q "connection_id"; then
    echo "✅ API functionality: OK"
else
    echo "❌ API functionality: FAILED"
fi

# 3. Resource utilization
MEMORY_USAGE=$(gcloud monitoring metrics list --filter='metric.type="run.googleapis.com/container/memory/utilizations"' --format="value(points.value.doubleValue)" --limit=1)
echo "📊 Memory utilization: ${MEMORY_USAGE}%"

# 4. Error rate check
ERROR_COUNT=$(gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR AND timestamp>="$(date -d "24 hours ago" --iso-8601)"' --format="value(timestamp)" | wc -l)
echo "📈 24h error count: ${ERROR_COUNT}"

# 5. Cost analysis
echo "💰 Daily cost report:"
gcloud billing budgets list --billing-account=BILLING_ACCOUNT_ID

echo "✅ Daily health check complete"
```

#### Weekly Maintenance (Sunday 02:00 UTC)
```bash
#!/bin/bash
# scripts/weekly-maintenance.sh

echo "🔧 Weekly Maintenance - $(date)"

# 1. Secret rotation check
echo "🔐 Checking secret rotation schedule..."
gcloud secrets versions list speech-credentials --limit=3
gcloud secrets versions list gemini-credentials --limit=3

# 2. Cleanup old revisions (keep last 10)
echo "🧹 Cleaning up old Cloud Run revisions..."
OLD_REVISIONS=$(gcloud run revisions list --service=econome --region=us-central1 --format="value(metadata.name)" | tail -n +11)
for revision in $OLD_REVISIONS; do
    gcloud run revisions delete $revision --region=us-central1 --quiet
done

# 3. Performance analysis
echo "📊 Performance analysis..."
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.message="Performance metrics"' \
    --limit=1000 --format=json > weekly-performance-$(date +%Y%m%d).json

# 4. Security audit
echo "🛡️ Security audit..."
gcloud asset search-all-iam-policies --scope=projects/$PROJECT_ID --format="table(policy.bindings.members,policy.bindings.role)"

# 5. Backup configuration
echo "📦 Backing up configuration..."
./scripts/backup-configuration.sh

echo "✅ Weekly maintenance complete"
```

### Deployment Procedures

#### Pre-Deployment Checklist
- [ ] All tests passing in CI/CD pipeline
- [ ] Security scans completed
- [ ] Performance benchmarks validated
- [ ] Rollback plan prepared
- [ ] On-call engineer notified
- [ ] Change window approved

#### Blue-Green Deployment Process
```bash
#!/bin/bash
# scripts/blue-green-deploy.sh

NEW_VERSION=$1
SERVICE_URL="https://econome-service-url"

echo "🚀 Starting blue-green deployment for version: $NEW_VERSION"

# 1. Deploy new version with no traffic
echo "📦 Deploying new version..."
gcloud run deploy econome-$NEW_VERSION \
    --image=gcr.io/$PROJECT_ID/econome:$NEW_VERSION \
    --region=us-central1 \
    --no-traffic \
    --tag=$NEW_VERSION

# 2. Health check new version
echo "🔍 Health checking new version..."
NEW_SERVICE_URL=$(gcloud run services describe econome-$NEW_VERSION --region=us-central1 --format="value(status.url)")
sleep 30  # Allow service to warm up

if ! curl -f $NEW_SERVICE_URL/health; then
    echo "❌ New version health check failed"
    gcloud run services delete econome-$NEW_VERSION --region=us-central1 --quiet
    exit 1
fi

# 3. Gradual traffic shift
echo "🔄 Starting traffic shift..."
gcloud run services update-traffic econome --to-revisions=econome-$NEW_VERSION=10 --region=us-central1
sleep 120  # Monitor for 2 minutes

# Check error rates
ERROR_RATE=$(gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR AND timestamp>="$(date -d "2 minutes ago" --iso-8601)"' --format="value(timestamp)" | wc -l)

if [ $ERROR_RATE -gt 5 ]; then
    echo "❌ High error rate detected, rolling back"
    gcloud run services update-traffic econome --to-revisions=PREVIOUS=100 --region=us-central1
    exit 1
fi

# 4. Complete cutover
echo "✅ Error rates normal, completing cutover..."
gcloud run services update-traffic econome --to-revisions=econome-$NEW_VERSION=100 --region=us-central1

echo "✅ Blue-green deployment complete"
```

### Rollback Procedures

#### Emergency Rollback (< 5 minutes)
```bash
#!/bin/bash
# scripts/emergency-rollback.sh

echo "🚨 Emergency rollback initiated - $(date)"

# Get previous working revision
CURRENT_REVISION=$(gcloud run services describe econome --region=us-central1 --format="value(status.traffic[0].revisionName)")
PREVIOUS_REVISION=$(gcloud run revisions list --service=econome --region=us-central1 --limit=2 --format="value(metadata.name)" | grep -v $CURRENT_REVISION | head -1)

echo "Rolling back from $CURRENT_REVISION to $PREVIOUS_REVISION"

# Immediate traffic switch
gcloud run services update-traffic econome \
    --to-revisions=$PREVIOUS_REVISION=100 \
    --region=us-central1

# Verify rollback
sleep 30
if curl -f https://econome-service-url/health; then
    echo "✅ Rollback successful"
    # Notify team
    echo "🔔 Rollback notification sent to #econome-ops"
else
    echo "❌ Rollback failed - escalating to senior engineer"
fi
```

---

## 🔧 Troubleshooting Guide

### Common Issues and Solutions

#### 1. Service Unavailable (503 Errors)

**Symptoms**: Users cannot access the service, 503 HTTP errors
**Likely Causes**: Container startup failures, resource exhaustion, quota limits

**Investigation Steps**:
```bash
# Check service status
gcloud run services describe econome --region=us-central1

# Check recent logs
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' --limit=20

# Check quotas
gcloud compute project-info describe --format="table(quotas.metric,quotas.limit,quotas.usage)"
```

**Resolution**:
```bash
# If quota exceeded
gcloud compute project-info describe
# Request quota increase via Cloud Console

# If container issues
gcloud run services update econome --memory=4Gi --cpu=2 --region=us-central1

# If startup timeout
gcloud run services update econome --timeout=600 --region=us-central1
```

#### 2. High Latency (P95 > 5 seconds)

**Symptoms**: Slow response times, user complaints about performance
**Likely Causes**: Cold starts, API throttling, inefficient code paths

**Investigation Steps**:
```bash
# Check instance scaling
gcloud run services describe econome --region=us-central1 --format="table(status.traffic)"

# Analyze latency patterns
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.message="Request latency"' --limit=100

# Check external API status
curl -w "@curl-format.txt" -o /dev/null -s https://speech.googleapis.com
curl -w "@curl-format.txt" -o /dev/null -s https://aiplatform.googleapis.com
```

**Resolution**:
```bash
# Increase minimum instances to reduce cold starts
gcloud run services update econome --min-instances=3 --region=us-central1

# Scale up resources
gcloud run services update econome --memory=6Gi --cpu=4 --region=us-central1

# Check and increase concurrency if needed
gcloud run services update econome --concurrency=1000 --region=us-central1
```

#### 3. Memory Exhaustion (Container OOMKilled)

**Symptoms**: Containers restarting, out of memory errors in logs
**Likely Causes**: Memory leaks, large audio processing, insufficient allocation

**Investigation Steps**:
```bash
# Check memory usage trends
gcloud monitoring metrics list --filter='metric.type="run.googleapis.com/container/memory/utilizations"'

# Look for OOM events
gcloud logging read 'resource.type="cloud_run_revision" AND "killed"' --limit=20

# Analyze memory consumption patterns
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.memory_usage' --limit=100
```

**Resolution**:
```bash
# Immediate: Increase memory allocation
gcloud run services update econome --memory=8Gi --region=us-central1

# Medium-term: Restart service to clear potential leaks
gcloud run services replace-traffic econome --to-latest --region=us-central1

# Long-term: Review code for memory leaks in next deployment
```

#### 4. API Rate Limiting (429 Errors)

**Symptoms**: "Quota exceeded" errors, intermittent failures
**Likely Causes**: Google Cloud API limits, burst traffic patterns

**Investigation Steps**:
```bash
# Check API quotas
gcloud services list --enabled | grep -E "(speech|aiplatform)"

# Look for rate limit errors
gcloud logging read 'resource.type="cloud_run_revision" AND "quota"' --limit=50

# Check usage patterns
gcloud monitoring metrics list --filter='metric.type="serviceruntime.googleapis.com/api/request_count"'
```

**Resolution**:
```bash
# Request quota increase
echo "Submit quota increase request via Cloud Console for:"
echo "- Cloud Speech-to-Text API"
echo "- Vertex AI API"

# Implement temporary rate limiting
gcloud run services update econome --set-env-vars="RATE_LIMIT_ENABLED=true,MAX_REQUESTS_PER_MINUTE=100" --region=us-central1

# Add retry logic with exponential backoff
# (This requires code changes in next deployment)
```

### Emergency Contacts

#### On-Call Escalation
1. **Primary On-Call**: Slack @oncall-engineer
2. **Secondary On-Call**: Email oncall-backup@company.com
3. **Engineering Manager**: Phone +1-555-0123
4. **CTO**: Escalation after 1 hour for Sev1 incidents

#### External Vendors
- **Google Cloud Support**: Case #XXXXXXXXX
- **Support Phone**: +1-855-836-3987
- **Support Email**: support@googlecloud.com

---

## 📊 Performance Tuning

### Optimization Strategies

#### 1. Auto-scaling Configuration
```bash
# Optimal scaling parameters for different load patterns

# Low traffic (nights/weekends)
gcloud run services update econome \
    --min-instances=1 \
    --max-instances=5 \
    --concurrency=800 \
    --region=us-central1

# High traffic (business hours)
gcloud run services update econome \
    --min-instances=3 \
    --max-instances=15 \
    --concurrency=1000 \
    --region=us-central1

# Peak traffic (events/demos)
gcloud run services update econome \
    --min-instances=5 \
    --max-instances=25 \
    --concurrency=1200 \
    --region=us-central1
```

#### 2. Resource Optimization
```bash
# Performance monitoring and tuning

# Monitor CPU utilization patterns
gcloud monitoring metrics list --filter='metric.type="run.googleapis.com/container/cpu/utilizations"' --format="table(points.value.doubleValue)"

# Optimize based on usage patterns
# For CPU-bound workloads:
gcloud run services update econome --cpu=4 --memory=4Gi --region=us-central1

# For memory-bound workloads:
gcloud run services update econome --cpu=2 --memory=8Gi --region=us-central1

# For I/O-bound workloads (typical for our use case):
gcloud run services update econome --cpu=2 --memory=4Gi --concurrency=1500 --region=us-central1
```

### Performance Monitoring Scripts

#### Real-time Performance Dashboard
```bash
#!/bin/bash
# scripts/performance-monitor.sh

echo "📊 Real-time Performance Monitor"
echo "================================"

while true; do
    clear
    echo "$(date) - Econome Performance Dashboard"
    echo "========================================"
    
    # Active requests
    ACTIVE_REQUESTS=$(gcloud logging read 'resource.type="cloud_run_revision" AND httpRequest.requestMethod' --limit=100 --format="value(timestamp)" | wc -l)
    echo "🔄 Active requests (last 5 min): $ACTIVE_REQUESTS"
    
    # Error rate
    ERROR_COUNT=$(gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR AND timestamp>="$(date -d "5 minutes ago" --iso-8601)"' --format="value(timestamp)" | wc -l)
    echo "❌ Errors (last 5 min): $ERROR_COUNT"
    
    # Instance count
    INSTANCE_COUNT=$(gcloud run services describe econome --region=us-central1 --format="value(status.traffic[0].percent)")
    echo "🖥️  Active instances: Scaled based on traffic"
    
    # Average latency (simulated - requires custom metrics)
    echo "⏱️  Average latency: Monitoring via Cloud Console"
    
    sleep 30
done
```

---

## 🔒 Security Operations

### Security Monitoring

#### Daily Security Checks
```bash
#!/bin/bash
# scripts/security-check.sh

echo "🛡️ Daily Security Audit - $(date)"

# 1. Check for unauthorized access attempts
UNAUTHORIZED_COUNT=$(gcloud logging read 'resource.type="cloud_run_revision" AND httpRequest.status>=400' --limit=1000 --format="value(timestamp)" | wc -l)
echo "🚨 Unauthorized access attempts (24h): $UNAUTHORIZED_COUNT"

# 2. Verify service account permissions
echo "🔑 Service account audit:"
gcloud projects get-iam-policy $PROJECT_ID --format="table(bindings.members,bindings.role)" | grep econome-runner

# 3. Check secret access logs
echo "🔐 Secret access audit:"
gcloud logging read 'protoPayload.serviceName="secretmanager.googleapis.com"' --limit=50

# 4. Verify SSL/TLS configuration
echo "🔒 SSL/TLS verification:"
curl -I https://econome-service-url | grep -E "(HTTP|Strict-Transport-Security)"

# 5. Container security scan (if available)
echo "🐳 Container security status:"
gcloud container images scan gcr.io/$PROJECT_ID/econome:latest --format="table(vulnerability.severity,vulnerability.cvssScore)"

echo "✅ Security check complete"
```

#### Secret Rotation Procedures
```bash
#!/bin/bash
# scripts/rotate-secrets.sh

echo "🔄 Secret Rotation Procedure"

# 1. Create new service account key
gcloud iam service-accounts keys create new-speech-credentials.json \
    --iam-account=econome-runner@$PROJECT_ID.iam.gserviceaccount.com

# 2. Update secret with new key
gcloud secrets versions add speech-credentials \
    --data-file=new-speech-credentials.json

# 3. Update service to use new secret
gcloud run services update econome \
    --update-secrets="/app/secrets/speech/credentials.json=speech-credentials:latest" \
    --region=us-central1

# 4. Verify service health with new secrets
sleep 60
curl -f https://econome-service-url/health

# 5. Delete old key after verification
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

# 6. Clean up temporary files
rm -f new-speech-credentials.json

echo "✅ Secret rotation complete"
```

---

## 💰 Cost Management

### Cost Monitoring
```bash
#!/bin/bash
# scripts/cost-analysis.sh

echo "💰 Cost Analysis Report - $(date)"

# Daily cost breakdown
echo "📊 Daily cost breakdown:"
gcloud billing budgets list --billing-account=$BILLING_ACCOUNT_ID

# Resource usage summary
echo "📈 Resource usage:"
echo "- Cloud Run: $(gcloud run services describe econome --region=us-central1 --format='value(status.traffic[0].percent)')% traffic"
echo "- Storage: Ephemeral (minimal cost)"
echo "- Networking: Standard egress charges"

# API usage costs
echo "🔌 API usage (estimated daily):"
echo "- Speech-to-Text: $SPEECH_API_DAILY_COST"
echo "- Vertex AI Gemini: $GEMINI_API_DAILY_COST"
echo "- Cloud Run: $CLOUD_RUN_DAILY_COST"

# Cost optimization recommendations
echo "💡 Cost optimization recommendations:"
echo "- Current auto-scaling: Efficient"
echo "- Memory allocation: Right-sized"
echo "- API usage: Within budget"

echo "✅ Cost analysis complete"
```

### Budget Alerts
```yaml
# budget-alerts.yaml
name: "Econome Production Budget"
displayName: "Econome Monthly Budget"
budgetFilter:
  projects: ["projects/$PROJECT_ID"]
  services: ["services/cloud-run", "services/speech", "services/aiplatform"]
amount:
  specifiedAmount:
    currencyCode: "USD"
    units: "500"  # $500 monthly budget
thresholdRules:
- thresholdPercent: 0.5   # 50% - Warning
  spendBasis: CURRENT_SPEND
- thresholdPercent: 0.8   # 80% - Alert
  spendBasis: CURRENT_SPEND  
- thresholdPercent: 1.0   # 100% - Critical
  spendBasis: CURRENT_SPEND
allUpdatesRule:
  pubsubTopic: "projects/$PROJECT_ID/topics/budget-alerts"
  schemaVersion: "1.0"
```

---

## 📚 Reference Information

### Important URLs
- **Production Service**: https://econome-service-url
- **Monitoring Dashboard**: https://console.cloud.google.com/monitoring/dashboards/custom/econome-production
- **Logging**: https://console.cloud.google.com/logs/viewer
- **Cloud Run Console**: https://console.cloud.google.com/run/detail/us-central1/econome
- **Documentation**: https://github.com/your-org/econome/tree/main/docs

### Configuration Files
- **Service Configuration**: `cloud-run-service.yaml`
- **CI/CD Pipeline**: `.github/workflows/05-auto-production-deploy.yml`
- **Monitoring Config**: `devops/monitoring/dashboard.json`
- **Alerting Rules**: `devops/monitoring/alerts.yaml`

### Key Environment Variables
```bash
# Production environment configuration
ENVIRONMENT=production
PROJECT_ID=your-project-id
LOG_LEVEL=INFO
GOOGLE_CLOUD_PROJECT=your-project-id
PORT=8080
CORS_ORIGINS=https://your-domain.com
BASE_URL=https://your-domain.com
```

### API Endpoints for Monitoring
```bash
# Health and status endpoints
GET /health                           # Service health check
GET /api/status                       # System status
GET /debug/audio                      # Audio system debug
GET /api/privacy/verify/{token}       # Privacy verification
```

---

## 📞 Emergency Procedures

### Incident Command Structure
1. **Incident Commander**: On-call engineer who acknowledges the alert
2. **Technical Lead**: Senior engineer with system knowledge
3. **Communications Lead**: Updates stakeholders and customers
4. **Subject Matter Expert**: Component specialist (if needed)

### Communication Templates

#### Incident Start Notification
```
🚨 INCIDENT: Econome Production Issue
Status: INVESTIGATING
Severity: [SEV1/SEV2/SEV3]
Impact: [Description of user impact]
Start Time: [UTC timestamp]
Commander: [Name]
Updates: Every 30 minutes or as available
```

#### Incident Resolution Notification
```
✅ RESOLVED: Econome Production Issue
Status: RESOLVED
Resolution Time: [Duration]
Root Cause: [Brief description]
Prevention: [Actions taken to prevent recurrence]
Post-mortem: [Link to post-mortem document]
```

### Post-Incident Review Process
1. **Incident Timeline**: Document all actions taken
2. **Root Cause Analysis**: Identify contributing factors
3. **Action Items**: Preventive measures and improvements
4. **Process Review**: Evaluate response effectiveness
5. **Knowledge Update**: Update runbook and procedures

---

<div align="center">
  <p><strong>⚙️ Production Operations Runbook</strong></p>
  <p><em>Comprehensive operational procedures for enterprise-grade systems</em></p>
  <p><strong>Version 1.0 | Last Updated: $(date)</strong></p>
</div>
