# Quickstart Guide: AI Analysis & Scoring

**Feature**: 009-ai-analysis-scoring  
**Date**: 2026-02-28  
**Version**: 1.0.0

---

## Overview

This guide provides step-by-step instructions for setting up and using the AI Analysis & Scoring feature. This feature automates resume screening using LangGraph-based Map-Reduce workflow with Ollama LLM.

---

## Prerequisites

### System Requirements

- Python 3.11 or higher
- Redis 7.x (for Celery broker and distributed locking)
- Ollama server (local or remote) with at least 8GB RAM
- 10GB free disk space

### Software Dependencies

All dependencies are listed in `requirements.txt`:

```bash
# Core dependencies
Django==5.2.9
djangorestframework==3.15.2
celery==5.4.0
redis==7.1.0

# AI/LLM dependencies
langchain>=1.1.0,<2.0.0
langgraph>=1.0.2,<2.0.0

# Resume parsing
pypdf==5.1.0
python-docx==1.1.2
```

---

## Step 1: Install Dependencies

```bash
# Navigate to project root
cd F:\Micro-SaaS Projects\X-Crewter\Software\TA_AI_SaaS\TI_AI_SaaS_Project

# Create virtual environment (if not already done)
python -m venv venv

# Activate virtual environment
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Configure Ollama

### Install Ollama

**Windows:**
```powershell
# Download and install from https://ollama.ai/download
# Or use winget
winget install Ollama.Ollama
```

### Pull Required Model

```bash
# Pull Llama 2 7B model (or your preferred model)
ollama pull llama2:7b

# Verify model is available
ollama list
```

### Start Ollama Server

```bash
# Start Ollama server (default port: 11434)
ollama serve
```

**Note**: Keep Ollama server running in a separate terminal window.

---

## Step 3: Configure Environment Variables

Create or update `.env` file in project root:

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2:7b

# Redis Configuration (Celery broker)
REDIS_URL=redis://localhost:6379/0

# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Sqlite3 for development)
DATABASE_URL=sqlite:///db.sqlite3

# File Storage (local development)
USE_S3=False
MEDIA_ROOT=./media
```

---

## Step 4: Start Redis Server

**Windows:**
```powershell
# Using Docker (recommended)
docker run -d -p 6379:6379 --name redis redis:7

# Or download Redis for Windows from https://github.com/microsoftarchive/redis/releases
# Then run:
redis-server.exe
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

---

## Step 5: Run Database Migrations

```bash
# Navigate to project root
cd TI_AI_SaaS_Project

# Apply migrations
python manage.py migrate

# Create superuser (for admin access)
python manage.py createsuperuser
```

---

## Step 6: Start Celery Worker

**Terminal 1 (Celery Worker):**
```bash
cd TI_AI_SaaS_Project

# Start Celery worker with info logging
celery -A TI_AI_SaaS_Project worker --loglevel=info --pool=solo

# Or with multiple workers (for production)
celery -A TI_AI_SaaS_Project worker --loglevel=info --concurrency=4
```

**Expected Output:**
```
 -------------- celery@DESKTOP-ABC123 v5.4.0 (clarity)
--- ***** ----- 
-- ******* ---- Windows-10-10.0.19041-SP0 2026-02-28 10:00:00
- *** --- * --- -- celery-
- * ---------- ---
- ** ---------- [config]
- ** ---------- .> app:         TI_AI_SaaS_Project:0x12345678
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     disabled://
- *** --- * --- .> concurrency: 1 (solo)
-- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery
```

---

## Step 7: Start Django Development Server

**Terminal 2 (Django Server):**
```bash
cd TI_AI_SaaS_Project

# Activate virtual environment if not already active
.\venv\Scripts\Activate.ps1

# Start development server
python manage.py runserver
```

**Expected Output:**
```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
February 28, 2026 - 10:05:00
Django version 5.2.9, using settings 'TI_AI_SaaS_Project.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

---

## Step 8: Verify Setup

### Check Ollama Connection

```bash
# Test Ollama connection
curl http://localhost:11434/api/tags
```

**Expected Response:**
```json
{
  "models": [
    {
      "name": "llama2:7b",
      "size": 3826793024,
      "modified_at": "2026-02-28T09:00:00Z"
    }
  ]
}
```

### Check Redis Connection

```bash
redis-cli ping
# Should return: PONG
```

### Check Celery Worker

In Django shell:
```bash
python manage.py shell
```

```python
from celery import current_app
app = current_app._get_current_object()
print(app.connection().transport.driver_name)
# Should print: redis
```

---

## Step 9: Create Test Data

### Create a Job Listing

```bash
python manage.py shell
```

```python
from django.utils import timezone
from datetime import timedelta
from apps.jobs.models import JobListing
from django.contrib.auth import get_user_model

User = get_user_model()

# Get or create a test user
user, _ = User.objects.get_or_create(
    email='tas@example.com',
    defaults={'username': 'tas_test'}
)

# Create a job listing (expired yesterday to allow analysis)
job = JobListing.objects.create(
    title='Senior Software Engineer',
    description='We are looking for a Senior Software Engineer with 5+ years of experience...',
    required_skills=['Python', 'Django', 'AWS', 'PostgreSQL'],
    required_experience=5,
    job_level='Senior',
    start_date=timezone.now() - timedelta(days=30),
    expiration_date=timezone.now() - timedelta(days=1),  # Expired yesterday
    status='Inactive',  # Manually deactivated
    created_by=user
)

print(f"Created job listing: {job.id}")
print(f"Title: {job.title}")
print(f"Status: {job.status}")
print(f"Expired: {job.expiration_date < timezone.now()}")
```

### Create Test Applicants

```python
from apps.applications.models import Applicant
import uuid

# Create test applicants
for i in range(5):
    applicant = Applicant.objects.create(
        job_listing=job,
        first_name=f'Test',
        last_name=f'Applicant {i+1}',
        email=f'applicant{i+1}@example.com',
        phone=f'+1-555-000{i}',
        resume_file=f'applications/resumes/resume_{i+1}.pdf',
        resume_file_hash=uuid.uuid4().hex,
        resume_parsed_text=f'''
        John Doe {i+1}
        Senior Software Engineer
        
        EXPERIENCE:
        - 7 years of Python development
        - 5 years with Django framework
        - AWS certified solutions architect
        
        EDUCATION:
        - Master's in Computer Science
        - BS in Software Engineering
        
        SKILLS:
        Python, Django, Flask, AWS, Docker, Kubernetes, PostgreSQL, MongoDB
        
        PROJECTS:
        - Led migration to microservices architecture
        - Improved system performance by 40%
        '''.strip()
    )
    print(f"Created applicant: {applicant.id} - {applicant.first_name} {applicant.last_name}")

print(f"\nTotal applicants for job: {job.applicants.count()}")
```

---

## Step 10: Initiate AI Analysis

### Via API (Recommended)

```bash
# Get JWT token first (using Djoser)
curl -X POST http://localhost:8000/auth/jwt/create/ \
  -H "Content-Type: application/json" \
  -d '{"email": "tas@example.com", "password": "yourpassword"}'

# Store the access token
ACCESS_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# Initiate analysis
curl -X POST http://localhost:8000/api/jobs/{job_id}/analysis/initiate/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "started",
    "job_id": "550e8400-e29b-41d4-a716-446655440001",
    "applicant_count": 5,
    "estimated_duration_seconds": 30
  }
}
```

### Via Django Shell

```python
from apps.analysis.tasks import run_ai_analysis

# Start analysis task
task = run_ai_analysis.delay(str(job.id))

print(f"Task ID: {task.id}")
print(f"Task State: {task.state}")
```

---

## Step 11: Monitor Analysis Progress

### Check Task Status

```bash
# Check analysis status via API
curl http://localhost:8000/api/jobs/{job_id}/analysis/status/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected Response (In Progress):**
```json
{
  "success": true,
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "processing",
    "progress_percentage": 60,
    "processed_count": 3,
    "total_count": 5,
    "started_at": "2026-02-28T10:30:00Z"
  }
}
```

**Expected Response (Completed):**
```json
{
  "success": true,
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "completed",
    "progress_percentage": 100,
    "processed_count": 5,
    "total_count": 5,
    "completed_at": "2026-02-28T10:34:15Z",
    "results_summary": {
      "analyzed_count": 5,
      "unprocessed_count": 0,
      "best_match_count": 2,
      "good_match_count": 2,
      "partial_match_count": 1,
      "mismatched_count": 0,
      "average_score": 78
    }
  }
}
```

### View Celery Task Logs

In the Celery worker terminal, you should see:

```
[2026-02-28 10:30:05,123: INFO/MainTask] Starting AI analysis for job 550e8400-e29b-41d4-a716-446655440001
[2026-02-28 10:30:05,456: INFO/MainTask] Found 5 applicants to analyze
[2026-02-28 10:30:06,789: INFO/ForkPoolWorker-1] Processing applicant: Test Applicant 1
[2026-02-28 10:30:08,012: INFO/ForkPoolWorker-2] Processing applicant: Test Applicant 2
[2026-02-28 10:30:10,345: INFO/ForkPoolWorker-1] Completed analysis for Test Applicant 1 - Score: 85 (Good Match)
[2026-02-28 10:30:12,678: INFO/ForkPoolWorker-2] Completed analysis for Test Applicant 2 - Score: 92 (Best Match)
...
[2026-02-28 10:34:15,901: INFO/MainTask] Analysis completed: 5 analyzed, 0 unprocessed
```

---

## Step 12: View Analysis Results

### Get All Results

```bash
curl http://localhost:8000/api/jobs/{job_id}/analysis/results/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Get Detailed Result for Specific Applicant

```bash
curl http://localhost:8000/api/analysis/results/{result_id}/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "applicant": {
      "name": "Test Applicant 1",
      "reference_number": "XC-A1B2C3"
    },
    "scores": {
      "education": {
        "score": 85,
        "justification": "Candidate holds a Master's degree..."
      },
      "skills": {
        "score": 90,
        "justification": "Strong technical skills match..."
      },
      "experience": {
        "score": 88,
        "justification": "7 years of relevant experience..."
      },
      "overall": {
        "score": 87,
        "category": "Good Match",
        "justification": "Strong candidate with solid qualifications..."
      }
    },
    "status": "Analyzed"
  }
}
```

### Get Analysis Statistics

```bash
curl http://localhost:8000/api/jobs/{job_id}/analysis/statistics/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Common Operations

### Cancel Running Analysis

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/analysis/cancel/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

### Re-run Analysis (Deletes Previous Results)

```bash
curl -X POST http://localhost:8000/api/jobs/{job_id}/analysis/re-run/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

### Filter Results by Category

```bash
# Get only Best Match candidates
curl "http://localhost:8000/api/jobs/{job_id}/analysis/results/?category=Best%20Match" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## Troubleshooting

### Ollama Connection Error

**Error:** `Connection refused to http://localhost:11434`

**Solution:**
```bash
# Ensure Ollama server is running
ollama serve

# Check if port 11434 is in use
netstat -ano | findstr :11434
```

### Redis Connection Error

**Error:** `Error connecting to Redis: Connection refused`

**Solution:**
```bash
# Start Redis server
docker start redis

# Or install and run Redis locally
redis-server.exe
```

### Celery Worker Not Processing Tasks

**Error:** Tasks stay in PENDING state

**Solution:**
1. Ensure Celery worker is running
2. Check Redis connection
3. Verify task is registered:
   ```bash
   celery -A TI_AI_SaaS_Project inspect registered
   ```

### Analysis Takes Too Long

**Expected:** ~6 seconds per applicant (10 resumes/minute)

**If slower:**
- Check Ollama model response time
- Reduce thread pool size if system is overloaded
- Verify network connectivity to Ollama server

### Unprocessed Results

**Check error message:**
```bash
curl http://localhost:8000/api/analysis/results/{result_id}/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Look for `error_message` field in response.

---

## Next Steps

After successful setup and testing:

1. **Review API Documentation**: See `contracts/api.yaml` for full API specification
2. **Data Model Reference**: See `data-model.md` for AIAnalysisResult model details
3. **Architecture Details**: See `research.md` for technical decisions and patterns
4. **Implementation Tasks**: Run `/speckit.tasks` to generate task breakdown

---

## Support

For issues or questions:
- Check logs in Celery worker terminal
- Review Django server logs
- Consult `research.md` for architectural decisions
- Refer to API contracts in `contracts/api.yaml`
