# Rollback Plan: AI Analysis & Scoring

**Purpose**: Steps to disable feature and remove data if needed  
**Version**: 1.0.0  
**Last Updated**: 2026-02-28

---

## Overview

This document provides step-by-step instructions to rollback the AI Analysis & Scoring feature in case of critical issues or business requirement changes.

---

## Rollback Scenarios

### Full Rollback
- Disable feature completely
- Remove all analysis data
- Revert database schema

### Partial Rollback
- Disable analysis initiation
- Keep existing data for audit
- Revert to manual screening

---

## Full Rollback Steps

### Step 1: Stop Analysis Tasks

```bash
# List all running Celery tasks
celery -A TI_AI_SaaS_Project inspect active

# Revoke all analysis tasks
celery -A TI_AI_SaaS_Project control revoke --terminate <task_id>
```

### Step 2: Remove Redis Locks

```python
import redis
r = redis.from_url('redis://localhost:6379/0')

# Delete all analysis-related keys
keys = r.keys('analysis_*')
if keys:
    r.delete(*keys)
```

### Step 3: Delete Analysis Data

```bash
# Django shell
python manage.py shell
```

```python
from apps.analysis.models import AIAnalysisResult

# Delete all analysis results (irreversible!)
count, _ = AIAnalysisResult.objects.all().delete()
print(f"Deleted {count} analysis results")
```

### Step 4: Revert Database Schema

```bash
# Unapply migration
python manage.py migrate analysis zero

# Or revert to specific migration
python manage.py migrate analysis 0000_initial
```

### Step 5: Remove Code Files

```bash
# Backup first!
cp -r apps/analysis apps/analysis.backup

# Remove analysis app files
rm -rf apps/analysis/models/
rm apps/analysis/api.py
rm apps/analysis/tasks.py
rm -rf apps/analysis/graphs/
rm -rf apps/analysis/nodes/
rm -rf apps/analysis/templates/analysis/
rm -rf apps/analysis/static/
```

### Step 6: Remove Service Files

```bash
# Backup first!
cp services/ai_analysis_service.py services/ai_analysis_service.py.backup

# Remove AI analysis service
rm services/ai_analysis_service.py
```

### Step 7: Update Configuration

**Remove from settings.py:**
```python
# Remove OLLAMA settings
OLLAMA_BASE_URL = ...
OLLAMA_MODEL = ...
```

**Remove from requirements.txt:**
```
langchain>=1.1.0,<2.0.0
langgraph>=1.0.2,<2.0.0
```

Then run:
```bash
pip uninstall langchain langgraph
```

### Step 8: Update URLs

**Remove from urls.py:**
```python
# Remove analysis API routes
path('api/jobs/<uuid:job_id>/analysis/initiate/', ...),
path('api/jobs/<uuid:job_id>/analysis/status/', ...),
# ... etc
```

### Step 9: Verify Rollback

```bash
# Run tests to ensure no broken imports
python manage.py test

# Check server starts
python manage.py runserver
```

---

## Partial Rollback (Disable Only)

### Disable Analysis Initiation

**In api.py, modify InitiateAnalysisView:**
```python
def post(self, request, job_id):
    return Response({
        'success': False,
        'error': {
            'code': 'FEATURE_DISABLED',
            'message': 'AI Analysis is currently disabled'
        }
    }, status=503)
```

### Hide UI Components

**In templates, add feature flag:**
```html
{% if ENABLE_AI_ANALYSIS %}
    {% include 'analysis/_loading_indicator.html' %}
{% endif %}
```

---

## Data Export (Before Deletion)

```python
import csv
from django.utils import timezone

# Export all results to CSV
with open('analysis_backup_%s.csv' % timezone.now().strftime('%Y%m%d_%H%M%S'), 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Applicant', 'Score', 'Category', 'Created'])
    
    for result in AIAnalysisResult.objects.all():
        writer.writerow([
            result.id,
            result.applicant.get_full_name(),
            result.overall_score,
            result.category,
            result.created_at
        ])
```

---

## Post-Rollback Verification

### Checklist

- [ ] No analysis tasks running
- [ ] Redis keys cleared
- [ ] Database tables dropped or empty
- [ ] Code files removed
- [ ] Configuration cleaned up
- [ ] Tests passing
- [ ] Server running without errors
- [ ] UI components hidden/removed

### Monitoring

Watch for errors in logs:
```bash
# Check for import errors
tail -f logs/error.log | grep -i analysis

# Check for missing routes
curl http://localhost:8000/api/jobs/<uuid>/analysis/status/
# Should return 404
```

---

## Emergency Contacts

- **Technical Lead**: [Contact Info]
- **DevOps**: [Contact Info]
- **Database Admin**: [Contact Info]

---

## Rollback Time Estimates

| Step | Estimated Time |
|------|----------------|
| Stop tasks | 5 minutes |
| Clear Redis | 2 minutes |
| Delete data | 10 minutes |
| Revert schema | 5 minutes |
| Remove code | 15 minutes |
| Testing | 30 minutes |
| **Total** | **~67 minutes** |

---

## Lessons Learned Template

After rollback, document:

1. **Reason for rollback**
2. **Issues encountered**
3. **Time taken**
4. **Data loss (if any)**
5. **Recommendations for future**
