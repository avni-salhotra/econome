# 📋 Econome Production Operations Runbook

## 🎯 Overview

This runbook provides step-by-step procedures for operating, monitoring, and troubleshooting the Econome production system. The system uses HTTP-based audio streaming with Server-Sent Events (SSE) for real-time communication and parallel AI processing.

## 🚨 Emergency Procedures

### **Service Down (P0 - Critical)**

#### **Immediate Response (0-5 minutes)**
1. **Check service health**:
   ```bash
   # Test main health endpoint
   curl -f https://econome-*.a.run.app/health
   
   # Expected response:
   {
     "status": "healthy",
     "timestamp": "2024-01-01T12:00:00Z",
     "version": "production",
     "dependencies": {
       "speech_api": "healthy",
       "gemini_api": "healthy", 
       "firestore": "healthy"
     }
   }
   ```

2. **Check Cloud Run service status**:
   ```bash
   gcloud run services describe econome --region=us-central1 \
     --format="table(metadata.name,status.conditions[0].type,status.conditions[0].status)"
   ```

3. **If service is down, initiate immediate rollback**:
   ```bash
   # Trigger emergency rollback via GitHub Actions
   gh workflow run "99-manual-operations.yml" \
     --field operation="rollback-production" \
     --field confirm-operation="EMERGENCY-ROLLBACK"
   ```

#### **Investigation Phase (5-15 minutes)**
1. **Check recent deployments**:
   ```bash
   # Check last 5 production deployments
   gh run list --workflow="04-deploy-production.yml" --limit=5
   
   # Check for failed deployments
   gh run list --status=failure --limit=10
   ```

2. **Analyze error logs**:
   ```bash
   # Check for critical errors in last hour
   gcloud logs read "resource.type=cloud_run_revision AND severity>=ERROR" \
     --limit=100 --freshness=1h \
     --format="table(timestamp,severity,jsonPayload.message)"
   ```

3. **Monitor resource utilization**:
   ```bash
   # Check current instances and resource usage
   gcloud run services describe econome --region=us-central1 \
     --format="value(status.traffic[0].percent,status.allocatedTraffic[0].revisionName)"
   ```

### **High Error Rate (P1 - Major)**

#### **Response Steps**
1. **Measure error rate**:
   ```bash
   # Count errors in last hour
   ERROR_COUNT=$(gcloud logs read "resource.type=cloud_run_revision AND severity=ERROR" \
     --limit=1000 --freshness=1h --format="value(timestamp)" | wc -l)
   
   TOTAL_REQUESTS=$(gcloud logs read "resource.type=cloud_run_revision AND httpRequest.requestMethod" \
     --limit=10000 --freshness=1h --format="value(timestamp)" | wc -l)
   
   echo "Error rate: $((ERROR_COUNT * 100 / TOTAL_REQUESTS))%"
   ```

2. **Identify error patterns**:
   ```bash
   # Group errors by type
   gcloud logs read "resource.type=cloud_run_revision AND severity=ERROR" \
     --limit=200 --freshness=1h \
     --format="value(jsonPayload.component,jsonPayload.error_type)" | \
     sort | uniq -c | sort -nr
   ```

3. **Check specific component health**:
   ```bash
   # Speech Agent errors
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.component=speech_agent" \
     --limit=50 --freshness=1h
   
   # AI processing errors  
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.component=gemini_agent" \
     --limit=50 --freshness=1h
   ```

4. **Scale up if resource-related**:
   ```bash
   gh workflow run "99-manual-operations.yml" \
     --field operation="scale-up-production" \
     --field scale-instances="15" \
     --field confirm-operation="SCALE-UP"
   ```

### **AI Processing Failure (P2 - High)**

#### **Response Steps**
1. **Check parallel AI agent status**:
   ```bash
   # Look for AI processing failures
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.pipeline_stage=ai_analysis" \
     --limit=100 --freshness=1h \
     --format="table(timestamp,severity,jsonPayload.agent,jsonPayload.error_type)"
   ```

2. **Verify Gemini API connectivity**:
   ```bash
   # Test API endpoint access
   curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     https://generativelanguage.googleapis.com/v1/models
   ```

3. **Check for quota exhaustion**:
   ```bash
   # Check for quota/rate limit errors
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.error_type=quota_exceeded" \
     --limit=50 --freshness=1h
   ```

### **Audio Processing Issues (P2 - High)**

#### **Response Steps**
1. **Check audio pipeline health**:
   ```bash
   # Monitor audio chunk processing
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.pipeline_stage=audio_processing" \
     --limit=100 --freshness=1h \
     --format="table(timestamp,jsonPayload.audio_chunk_size,jsonPayload.processing_time_ms)"
   ```

2. **Verify Speech API connectivity**:
   ```bash
   # Check Speech API health
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.component=speech_agent AND jsonPayload.status=success" \
     --limit=10 --freshness=30m
   ```

3. **Monitor chunk size violations**:
   ```bash
   # Look for oversized chunks
   gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.error_type=chunk_size_violation" \
     --limit=20 --freshness=1h
   ```

## 📊 System Monitoring

### **Key Performance Indicators**

#### **Real-Time Health Metrics**
```bash
# Create monitoring dashboard script
cat > check_system_health.sh << 'EOF'
#!/bin/bash

echo "=== Econome System Health Check ==="
echo "Timestamp: $(date)"
echo

# 1. Service availability
echo "🌐 Service Health:"
curl -s https://econome-*.a.run.app/health | jq -r '.status'

# 2. Error rate (last hour)
echo "📊 Error Rate (last hour):"
ERROR_COUNT=$(gcloud logs read "resource.type=cloud_run_revision AND severity=ERROR" \
  --limit=1000 --freshness=1h --format="value(timestamp)" | wc -l)
echo "Errors: $ERROR_COUNT"

# 3. Active instances
echo "🏗️ Active Instances:"
gcloud run services describe econome --region=us-central1 \
  --format="value(status.traffic[0].revisionName)" | \
  xargs -I {} gcloud run revisions describe {} --region=us-central1 \
  --format="value(status.observedGeneration)"

# 4. Recent deployments
echo "🚀 Recent Deployments:"
gh run list --workflow="04-deploy-production.yml" --limit=3 \
  --json="conclusion,createdAt,headSha" | jq -r '.[] | "\(.conclusion) - \(.createdAt)"'

echo "=== End Health Check ==="
EOF

chmod +x check_system_health.sh
./check_system_health.sh
```

#### **Component-Specific Monitoring**
```bash
# Audio processing performance
gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.pipeline_stage=audio_processing" \
  --limit=100 --freshness=1h \
  --format="value(jsonPayload.processing_time_ms)" | \
  awk '{sum+=$1; count++} END {print "Avg audio processing:", sum/count "ms"}'

# Speech recognition latency
gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.component=speech_agent" \
  --limit=100 --freshness=1h \
  --format="value(jsonPayload.latency_ms)" | \
  awk '{sum+=$1; count++} END {print "Avg speech latency:", sum/count "ms"}'

# AI processing time (parallel)
gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.pipeline_stage=ai_analysis" \
  --limit=50 --freshness=1h \
  --format="value(jsonPayload.ai_processing_time)" | \
  awk '{sum+=$1; count++} END {print "Avg AI processing:", sum/count "s"}'
```

### **Server-Sent Events Health**
```bash
# Test SSE endpoint connectivity
curl -N -H "Accept: text/event-stream" \
  "https://econome-*.a.run.app/api/conversation/test-connection-id/events" \
  --max-time 10

# Monitor SSE message delivery
gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.event_type=sse_sent" \
  --limit=50 --freshness=30m \
  --format="table(timestamp,jsonPayload.connection_id,jsonPayload.event_name)"
```

## 🔧 Routine Maintenance

### **Daily Tasks**

#### **Morning Health Check (9:00 AM)**
```bash
# Comprehensive daily health verification
cat > daily_health_check.sh << 'EOF'
#!/bin/bash

echo "📅 Daily Health Check - $(date)"
echo "=================================="

# 1. Overall system health
echo "🏥 System Health:"
./check_system_health.sh | grep -E "(Service Health|Error Rate|Active Instances)"

# 2. Performance metrics
echo "⚡ Performance Summary:"
echo "Audio processing avg latency: $(gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.pipeline_stage=audio_processing" --limit=200 --freshness=24h --format="value(jsonPayload.processing_time_ms)" | awk '{sum+=$1; count++} END {print sum/count "ms"}')"

echo "Speech recognition avg latency: $(gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.component=speech_agent" --limit=200 --freshness=24h --format="value(jsonPayload.latency_ms)" | awk '{sum+=$1; count++} END {print sum/count "ms"}')"

# 3. Error analysis
echo "🚨 Error Summary (24h):"
gcloud logs read "resource.type=cloud_run_revision AND severity>=WARNING" \
  --freshness=24h --limit=100 \
  --format="value(severity)" | sort | uniq -c

# 4. Usage statistics
echo "📈 Usage Stats (24h):"
TOTAL_SESSIONS=$(gcloud logs read "resource.type=cloud_run_revision AND jsonPayload.message:Starting new conversation" --freshness=24h --format="value(timestamp)" | wc -l)
echo "Total conversations started: $TOTAL_SESSIONS"

echo "✅ Daily check complete"
EOF

chmod +x daily_health_check.sh
./daily_health_check.sh
```

#### **Evening Performance Review (6:00 PM)**
```bash
# Daily performance analysis
echo "📊 Daily Performance Review - $(date)"
echo "====================================="

# Response time analysis
echo "🕐 Response Time Analysis:"
gcloud monitoring timeseries list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_latencies"' \
  --interval.end-time=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval.start-time=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)

# Resource utilization
echo "💾 Resource Utilization:"
gcloud run services describe econome --region=us-central1 \
  --format="table(spec.template.spec.containers[0].resources.limits)"
```

### **Weekly Tasks**

#### **Monday: Security & Access Review**
```bash
# Weekly security audit
echo "🔒 Weekly Security Review - $(date)"
echo "================================="

# 1. Check service account key rotation
echo "🔑 Service Account Key Status:"
gcloud iam service-accounts keys list \
  --iam-account=econome-service@$(gcloud config get-value project).iam.gserviceaccount.com \
  --format="table(name,keyAlgorithm,validAfterTime)"

# 2. Review secret versions
echo "🤫 Secret Manager Status:"
gcloud secrets versions list speech-credentials --format="table(name,state,createTime)"
gcloud secrets versions list gemini-credentials --format="table(name,state,createTime)"

# 3. Check for unauthorized access attempts
echo "🚨 Security Events:"
gcloud logs read "resource.type=cloud_run_revision AND httpRequest.status>=400" \
  --freshness=7d --limit=20 \
  --format="table(timestamp,httpRequest.status,httpRequest.remoteIp)"
```

#### **Wednesday: Performance Optimization Review**
```bash
# Mid-week performance analysis
echo "⚡ Performance Optimization Review - $(date)"
echo "==========================================="

# 1. Analyze response time trends
echo "📈 Response Time Trends (7 days):"
gcloud logs read "resource.type=cloud_run_revision AND httpRequest.latency" \
  --freshness=7d --limit=1000 \
  --format="value(httpRequest.latency)" | \
  awk '{sum+=$1; count++} END {print "Average latency:", sum/count "ms"}'

# 2. Check scaling efficiency
echo "📊 Auto-scaling Performance:"
gcloud run services describe econome --region=us-central1 \
  --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/maxScale'])"

# 3. Resource optimization opportunities
echo "💾 Resource Usage Analysis:"
gcloud monitoring timeseries list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/container/memory/utilizations"' \
  --interval.end-time=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --interval.start-time=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
```

#### **Friday: Deployment & Release Review**
```bash
# Weekly deployment review
echo "🚀 Weekly Deployment Review - $(date)"
echo "===================================="

# 1. Review deployment history
echo "📋 Deployment History (7 days):"
gh run list --workflow="04-deploy-production.yml" --limit=10 \
  --json="conclusion,createdAt,headSha,workflowName" | \
  jq -r '.[] | "\(.createdAt): \(.conclusion) - \(.headSha[0:7])"'

# 2. Check staging environment health
echo "🧪 Staging Environment Status:"
curl -s https://econome-staging-*.a.run.app/health | jq -r '.status'

# 3. Verify backup and rollback procedures
echo "🔄 Rollback Readiness:"
gh workflow run "99-manual-operations.yml" \
  --field operation="health-check" \
  --field confirm-operation="DRY-RUN"
```

## 🚨 Alerting & Escalation

### **Alert Thresholds**

#### **P0 - Critical (Immediate Response)**
- Service availability < 99%
- Error rate > 5% (5-minute window)
- Zero successful requests in 5 minutes
- All instances down

#### **P1 - Major (Response within 15 minutes)**
- Error rate > 2% (15-minute window)
- Average response time > 5 seconds
- AI processing failures > 20%
- Memory usage > 90%

#### **P2 - Minor (Response within 1 hour)**
- Error rate > 1% (1-hour window)
- Average response time > 3 seconds
- Unusual traffic patterns
- Resource utilization > 80%

### **Escalation Contacts**
```bash
# Emergency contact information
cat > emergency_contacts.txt << 'EOF'
=== ECONOME EMERGENCY CONTACTS ===

P0 - Critical Issues:
  Primary: On-call engineer
  Secondary: Tech lead
  Escalation: Engineering manager

P1 - Major Issues:
  Primary: Development team
  Secondary: Tech lead

P2 - Minor Issues:
  Primary: Development team
  
Business Hours: 9 AM - 6 PM PST
After Hours: P0/P1 only

Incident Communication:
  - Slack: #econome-incidents
  - Email: team-econome@company.com
EOF
```

## 🔧 Operational Procedures

### **Deployment Rollback**
```bash
# Emergency production rollback
gh workflow run "99-manual-operations.yml" \
  --field operation="rollback-production" \
  --field rollback-revision="econome-00042-abc" \
  --field confirm-operation="EMERGENCY-ROLLBACK"
```

### **Traffic Scaling**
```bash
# Scale up during high traffic
gh workflow run "99-manual-operations.yml" \
  --field operation="scale-up-production" \
  --field scale-instances="20" \
  --field confirm-operation="SCALE-UP"

# Scale down during low traffic
gh workflow run "99-manual-operations.yml" \
  --field operation="scale-down-production" \
  --field scale-instances="3" \
  --field confirm-operation="SCALE-DOWN"
```

### **Configuration Updates**
```bash
# Update environment variables
gcloud run services update econome \
  --region=us-central1 \
  --set-env-vars=NEW_CONFIG=value

# Update resource limits
gcloud run services update econome \
  --region=us-central1 \
  --memory=4Gi \
  --cpu=4
```

## 📚 Troubleshooting Playbooks

### **High Memory Usage**
1. Check for memory leaks in audio processing
2. Monitor session cleanup 
3. Verify TTL configuration in Firestore
4. Scale up memory if needed

### **Slow AI Processing**
1. Check Gemini API quotas
2. Verify parallel processing is working
3. Monitor transcript length vs processing time
4. Consider request batching optimizations

### **Audio Upload Failures**
1. Verify HTTPS enforcement (required for MediaRecorder)
2. Check chunk size violations
3. Test FFmpeg processing pipeline
4. Monitor Speech API connectivity

---

**📋 This runbook is maintained alongside the production system and updated with each operational learning.**
