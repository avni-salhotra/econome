# 📋 Econome Operations Runbook

## 🎯 Overview

This runbook provides step-by-step procedures for operating, monitoring, and troubleshooting the Econome system in production.

## 🚨 Emergency Procedures

### **Service Down (P0)**

#### **Immediate Response (0-5 minutes)**
1. **Check service status**:
   ```bash
   curl -f https://econome-*.a.run.app/health
   ```

2. **Check Cloud Run status**:
   ```bash
   gcloud run services describe econome --region=us-central1
   ```

3. **If service is down, initiate rollback**:
   ```bash
   gh workflow run "99 - Manual Operations" \
     --field operation="rollback-production" \
     --field confirm-operation="CONFIRM"
   ```

#### **Investigation (5-15 minutes)**
1. **Check recent deployments**:
   ```bash
   gh run list --workflow="04 - Deploy Production" --limit=5
   ```

2. **Review error logs**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND severity>=ERROR" \
     --limit=50 --freshness=1h
   ```

3. **Check resource utilization**:
   ```bash
   gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
   ```

### **High Error Rate (P1)**

#### **Response Steps**
1. **Check error rate**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND severity=ERROR" \
     --limit=100 --freshness=1h | wc -l
   ```

2. **Identify error patterns**:
   ```bash
   gcloud logs read "resource.type=cloud_run_revision AND severity=ERROR" \
     --limit=50 --format="value(textPayload)" | sort | uniq -c
   ```

3. **Scale up if needed**:
   ```bash
   gh workflow run "99 - Manual Operations" \
     --field operation="scale-up-production" \
     --field scale-instances="15" \
     --field confirm-operation="CONFIRM"
   ```

### **Performance Degradation (P2)**

#### **Response Steps**
1. **Check response times**:
   ```bash
   for i in {1..5}; do
     time curl -s https://econome-*.a.run.app/health > /dev/null
   done
   ```

2. **Check instance count**:
   ```bash
   gcloud run services describe econome --region=us-central1 \
     --format="value(status.traffic[0].percent,spec.template.metadata.annotations.autoscaling\.knative\.dev/maxScale)"
   ```

3. **Review resource usage**:
   ```bash
   gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
   ```

## 📊 Monitoring & Alerting

### **Key Metrics to Monitor**

#### **Application Metrics**
- **Response Time**: < 2000ms (P95)
- **Error Rate**: < 1% (5-minute window)
- **Availability**: > 99.9% (monthly)
- **Request Rate**: Monitor for unusual spikes

#### **Infrastructure Metrics**
- **CPU Utilization**: < 80% average
- **Memory Usage**: < 80% of allocated
- **Instance Count**: Monitor scaling patterns
- **Cold Starts**: < 10% of requests

### **Health Check Procedures**

#### **Automated Health Checks**
```bash
# Production health check
curl -f https://econome-*.a.run.app/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "1.0.0",
  "dependencies": {
    "speech_api": "healthy",
    "gemini_api": "healthy",
    "firestore": "healthy"
  }
}
```

#### **Manual Health Verification**
```bash
# Test WebSocket connection
wscat -c wss://econome-*.a.run.app/ws/conversation

# Test API endpoints
curl https://econome-*.a.run.app/docs
curl https://econome-*.a.run.app/
```

## 🔧 Routine Maintenance

### **Daily Tasks**

#### **Morning Health Check (9 AM)**
```bash
# Run comprehensive health check
gh workflow run "99 - Manual Operations" \
  --field operation="health-check" \
  --field confirm-operation="CONFIRM"

# Check overnight logs for errors
gcloud logs read "resource.type=cloud_run_revision AND severity>=WARNING" \
  --freshness=24h --limit=20
```

#### **Evening Review (6 PM)**
```bash
# Check daily metrics
gcloud logging read "resource.type=cloud_run_revision" \
  --freshness=24h --format="value(timestamp,severity)" | \
  sort | uniq -c

# Review scaling patterns
gcloud run services describe econome --region=us-central1
```

### **Weekly Tasks**

#### **Monday: Security Review**
```bash
# Check for security updates
gcloud components update

# Review access logs
gcloud logs read "resource.type=cloud_run_revision" \
  --freshness=7d --filter="httpRequest.status>=400"

# Verify secret rotation dates
gcloud secrets versions list speech-credentials
gcloud secrets versions list gemini-credentials
```

#### **Wednesday: Performance Review**
```bash
# Analyze response times
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"

# Check resource utilization trends
gcloud run services describe econome --region=us-central1

# Review scaling efficiency
gcloud logs read "resource.type=cloud_run_revision" \
  --freshness=7d --filter="textPayload:scaling"
```

#### **Friday: Deployment Review**
```bash
# Review recent deployments
gh run list --workflow="04 - Deploy Production" --limit=10

# Check staging environment health
curl -f https://econome-staging-*.a.run.app/health

# Verify backup procedures
gcloud container images list-tags gcr.io/PROJECT_ID/econome --limit=10
```

### **Monthly Tasks**

#### **First Monday: Capacity Planning**
```bash
# Review monthly usage patterns
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"

# Analyze cost trends
gcloud billing budgets list

# Plan for upcoming capacity needs
gcloud run services describe econome --region=us-central1
```

#### **Third Monday: Security Audit**
```bash
# Review IAM permissions
gcloud projects get-iam-policy PROJECT_ID

# Check service account usage
gcloud iam service-accounts list

# Verify secret access patterns
gcloud logging read "protoPayload.serviceName=secretmanager.googleapis.com" \
  --freshness=30d
```

## 🔄 Deployment Procedures

### **Standard Deployment**

#### **Pre-Deployment Checklist**
- [ ] All tests passing in staging
- [ ] Performance benchmarks met
- [ ] Security scans completed
- [ ] Rollback plan prepared
- [ ] Stakeholders notified

#### **Deployment Steps**
```bash
# 1. Deploy to staging (automatic)
git push origin main

# 2. Validate staging deployment
curl -f https://econome-staging-*.a.run.app/health

# 3. Run staging tests
gh workflow run "03 - Deploy Staging" --field image-tag="latest"

# 4. Deploy to production (manual)
gh workflow run "04 - Deploy Production" \
  --field image-tag="BUILD_ID" \
  --field confirm-production="DEPLOY"

# 5. Validate production deployment
curl -f https://econome-*.a.run.app/health
```

#### **Post-Deployment Checklist**
- [ ] Health checks passing
- [ ] Error rates normal
- [ ] Response times acceptable
- [ ] Monitoring alerts configured
- [ ] Documentation updated

### **Emergency Deployment**

#### **Hotfix Procedure**
```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-fix

# 2. Make minimal changes
git commit -m "hotfix: critical security fix"

# 3. Fast-track through pipeline
git push origin hotfix/critical-fix

# 4. Emergency production deployment
gh workflow run "04 - Deploy Production" \
  --field image-tag="HOTFIX_BUILD_ID" \
  --field confirm-production="DEPLOY" \
  --field skip-staging-check="true"
```

## 🔍 Troubleshooting Guide

### **Common Issues**

#### **Issue: Service Not Responding**
**Symptoms**: Health check failures, 502/503 errors
**Investigation**:
```bash
# Check service status
gcloud run services describe econome --region=us-central1

# Check recent logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Check resource limits
gcloud run services describe econome --region=us-central1 \
  --format="value(spec.template.spec.template.spec.containers[0].resources)"
```

**Resolution**:
```bash
# Option 1: Restart service
gcloud run services update econome --region=us-central1

# Option 2: Scale up
gh workflow run "99 - Manual Operations" \
  --field operation="scale-up-production" \
  --field scale-instances="10"

# Option 3: Rollback
gh workflow run "99 - Manual Operations" \
  --field operation="rollback-production"
```

#### **Issue: High Memory Usage**
**Symptoms**: OOM errors, slow responses
**Investigation**:
```bash
# Check memory configuration
gcloud run services describe econome --region=us-central1 \
  --format="value(spec.template.spec.template.spec.containers[0].resources.limits.memory)"

# Check memory usage patterns
gcloud monitoring metrics list --filter="metric.type=run.googleapis.com/container/memory/utilizations"
```

**Resolution**:
```bash
# Increase memory allocation
gcloud run services update econome \
  --region=us-central1 \
  --memory=4Gi
```

#### **Issue: API Rate Limits**
**Symptoms**: 429 errors, quota exceeded messages
**Investigation**:
```bash
# Check quota usage
gcloud logging read "protoPayload.serviceName=speech.googleapis.com" \
  --freshness=1h --filter="protoPayload.status.code=8"

# Check API usage patterns
gcloud monitoring metrics list --filter="resource.type=consumed_api"
```

**Resolution**:
```bash
# Request quota increase
gcloud alpha services quota update \
  --service=speech.googleapis.com \
  --consumer=projects/PROJECT_ID \
  --metric=speech.googleapis.com/quota/requests_per_minute \
  --value=NEW_LIMIT
```

## 📞 Escalation Procedures

### **Escalation Matrix**

| Severity | Response Time | Escalation Path |
|----------|---------------|-----------------|
| P0 (Service Down) | 5 minutes | On-call → Team Lead → Management |
| P1 (High Error Rate) | 15 minutes | On-call → Team Lead |
| P2 (Performance) | 1 hour | On-call → Team |
| P3 (Minor Issues) | 4 hours | Team → Backlog |

### **Contact Information**
- **On-call Engineer**: [Slack/Phone]
- **Team Lead**: [Contact Info]
- **Google Cloud Support**: [Support Case System]

---

*This runbook is reviewed monthly and updated with operational learnings.*
