# Quickstart: Job Application Submission

**Feature**: 008-job-application-submission  
**Date**: 2026-02-19  
**Purpose**: Get developers up and running quickly with the application submission feature

---

## Prerequisites

Ensure you have the following installed:

- Python 3.11
- Redis (for Celery)
- Sqlite3 (included with Python)

---

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**New dependencies for this feature**:
```
django-storages>=1.14
boto3>=1.34        # For S3 (production)
google-cloud-storage>=2.10  # For GCS (production)
PyPDF2>=3.0
python-docx>=1.1
phonenumbers>=8.13
email-validator>=2.1
```

---

## 2. Configure Environment Variables

Create or update `.env` file in project root:

```bash
# File Storage (Development - Local)
DEFAULT_FILE_STORAGE=django.core.files.storage.FileSystemStorage
MEDIA_ROOT=./media
MEDIA_URL=/media/

# File Storage (Production - S3 Example)
# DEFAULT_FILE_STORAGE=storages.backends.s3boto3.S3Boto3Storage
# AWS_STORAGE_BUCKET_NAME=x-crewter-resumes
# AWS_S3_REGION_NAME=us-east-1
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key

# File Storage (Production - GCS Example)
# DEFAULT_FILE_STORAGE=storages.backends.gcloud.GoogleCloudStorage
# GS_BUCKET_NAME=x-crewter-resumes
# GS_PROJECT_ID=your-project-id

# Redis (for Celery + Rate Limiting)
REDIS_URL=redis://localhost:6379/0

# Email (Development - Console Backend)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Email (Production - SMTP Example)
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.sendgrid.net
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-username
# EMAIL_HOST_PASSWORD=your-password
# DEFAULT_FROM_EMAIL=noreply@x-crewter.com

# Rate Limiting
RATE_LIMIT_WINDOW=3600  # 1 hour in seconds
RATE_LIMIT_MAX=5  # 5 submissions per window
```

---

## 3. Run Migrations

```bash
python manage.py makemigrations applications
python manage.py migrate
```

---

## 4. Start Redis

**Windows (with Docker Desktop)**:
```bash
docker run -d -p 6379:6379 redis:latest
```

**Linux/macOS**:
```bash
redis-server
```

---

## 5. Start Celery Worker

**Terminal 1**:
```bash
celery -A TI_AI_SaaS_Project worker --loglevel=info
```

---

## 6. Start Celery Beat (for cleanup tasks)

**Terminal 2**:
```bash
celery -A TI_AI_SaaS_Project beat --loglevel=info
```

---

## 7. Start Django Development Server

**Terminal 3**:
```bash
python manage.py runserver
```

---

## 8. Verify Setup

### Test File Upload Validation

```bash
curl -X POST http://localhost:8000/api/applications/validate-file/ \
  -F "job_listing_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "resume=@/path/to/test-resume.pdf"
```

**Expected Response**:
```json
{
  "valid": true,
  "file_size": 524288,
  "file_format": "pdf",
  "checks": {
    "format_valid": true,
    "size_valid": true,
    "duplicate": false
  }
}
```

### Test Application Submission

```bash
curl -X POST http://localhost:8000/api/applications/ \
  -F "job_listing_id=550e8400-e29b-41d4-a716-446655440000" \
  -F "first_name=John" \
  -F "last_name=Doe" \
  -F "email=john.doe@example.com" \
  -F "phone=+12025551234" \
  -F "country_code=US" \
  -F "resume=@/path/to/test-resume.pdf" \
  -F 'screening_answers=[{"question_id": "660e8400-e29b-41d4-a716-446655440001", "answer": "Test answer"}]'
```

**Expected Response**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "submitted_at": "2026-02-19T10:30:00Z",
  "message": "Application submitted successfully. A confirmation email has been sent to john.doe@example.com"
}
```

---

## 9. Run Tests

```bash
python manage.py test applications
```

**Coverage requirement**: 90% minimum

---

## Common Issues

### Issue: Redis Connection Error

**Error**: `Error 111 connecting to localhost:6379. Connection refused.`

**Solution**: Ensure Redis is running:
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG
```

### Issue: File Size Validation Failing

**Error**: `File size must be between 50KB and 10MB`

**Solution**: Create a test file in the valid range:
```bash
# Create a 100KB test PDF
python -c "
with open('test-resume.pdf', 'wb') as f:
    f.write(b'%PDF-1.4\\n' + b'A' * 102400)
"
```

### Issue: Email Not Sending

**Error**: No email appears in console (development)

**Solution**: Check Celery worker is running and EMAIL_BACKEND is set to console backend for development.

### Issue: Duplicate Detection Not Working

**Error**: Duplicate submissions allowed

**Solution**: Verify database constraints are applied:
```bash
python manage.py dbshell
# In Sqlite3:
.schema applications_applicant
# Should show UNIQUE constraints on (job_listing_id, resume_file_hash), etc.
```

---

## Next Steps

1. **Review API Contract**: See `contracts/api-contract.md` for full endpoint documentation
2. **Understand Data Model**: See `data-model.md` for entity relationships
3. **Read Research Decisions**: See `research.md` for technical rationale
4. **Implement Tasks**: See `tasks.md` (after `/speckit.tasks` command)

---

## Development Workflow

1. Create feature branch (already done: `008-job-application-submission`)
2. Implement models (`applications/models.py`)
3. Implement serializers (`applications/serializers.py`)
4. Implement views (`applications/views.py`)
5. Implement Celery tasks (`applications/tasks.py`)
6. Create templates (`applications/templates/applications/application_form.html`)
7. Add static assets (`applications/static/css/`, `applications/static/js/`)
8. Write tests (`applications/tests/Unit/`, `applications/tests/Integration/`, `applications/tests/E2E/`)
9. Run tests and verify 90% coverage
10. Commit and push

---

## Production Deployment Checklist

- [ ] Set `DEFAULT_FILE_STORAGE` to S3 or GCS backend
- [ ] Configure AWS/GCS credentials in environment
- [ ] Set `EMAIL_BACKEND` to SMTP or transactional email service
- [ ] Configure `DEFAULT_FROM_EMAIL` with production domain
- [ ] Enable HTTPS and set `SECURE_SSL_REDIRECT=True`
- [ ] Set `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True`
- [ ] Configure rate limiting with production Redis instance
- [ ] Set up Celery beat for cleanup task (daily at 2 AM)
- [ ] Test file upload with production storage backend
- [ ] Test email delivery with production SMTP
- [ ] Verify duplication detection with production database
