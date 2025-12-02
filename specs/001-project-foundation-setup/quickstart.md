# Quickstart Guide: X-Crewter Project Setup

## Prerequisites

- Python 3.11 or higher
- Redis server (for Celery broker and backend)
- Git
- Pip (Python package installer)

## Initial Project Setup

### 1. Navigate to Project Directory
```bash
cd F:\Micro-SaaS Projects\X-Crewter\Software\TA_AI_SaaS\TI_AI_SaaS_Project
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Django and Create Project
```bash
pip install django
django-admin startproject x_crewter .
```

### 4. Create Core Applications
```bash
python manage.py startapp accounts
python manage.py startapp jobs
python manage.py startapp applications
python manage.py startapp analysis
python manage.py startapp subscription
```

### 5. Move Applications to apps Directory
Create the apps directory and move the applications:
```bash
mkdir apps
mv accounts apps/
mv jobs apps/
mv applications apps/  # Note: 'applications' is the name of the app, not a conflict with the directory
mv analysis apps/
mv subscription apps/
```

### 6. Create Directory Structure for Each App
For each app under `apps/`, create the required subdirectories:
```bash
# For accounts app
mkdir -p apps/accounts/templates apps/accounts/static/{js,css,images} apps/accounts/tests/{unit,integration,e2e}

# For jobs app
mkdir -p apps/jobs/templates apps/jobs/static/{js,css,images} apps/jobs/tests/{unit,integration,e2e}

# For applications app
mkdir -p apps/applications/templates apps/applications/static/{js,css,images} apps/applications/tests/{unit,integration,e2e}

# For analysis app
mkdir -p apps/analysis/templates apps/analysis/static/{js,css,images} apps/analysis/tests/{unit,integration,e2e}

# For subscription app
mkdir -p apps/subscription/templates apps/subscription/static/{js,css,images} apps/subscription/tests/{unit,integration,e2e}
```

### 7. Create Services Directory
```bash
mkdir -p services/{ai_analysis,email_service,file_storage}
```

### 8. Create Project-Level Directories
```bash
mkdir -p static templates config/settings
```

### 9. Create the requirements.txt File
Create a `requirements.txt` file with the following content:
```
Django==5.0.0
celery==5.3.0
redis==4.6.0
selenium==4.11.0
webdriver-manager==4.0.0
django-environ==0.11.2
djangorestframework==3.14.0
python-dotenv==1.0.0
django-cors-headers==4.2.0
langchain==0.0.300
langgraph==0.0.18
pypdf==3.16.0
python-docx==0.8.11
shadcn-django==0.0.1
```

### 10. Install Dependencies
```bash
pip install -r requirements.txt
```

### 11. Create Celery Configuration File
Create a `celery_app.py` file in the project root with the following content:
```python
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')

app = Celery('x_crewter')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
```

### 12. Set Up Environment Variables
Create a `.env` file in the project root with the following variables:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0
OLLAMA_ENDPOINT=http://localhost:11434
```

### 13. Update Django Settings
Update your `x_crewter/settings.py` to:
- Add the apps to `INSTALLED_APPS`
- Configure the database to use Sqlite3
- Add Celery configuration
- Configure static files and templates directories
- Add CORS configuration
- Add environment variable loading with django-environ

### 14. Create Basic Models (Before Running Migrations)
First, create minimal models for each app:

In `apps/accounts/models.py`:
```python
from django.db import models

class User(models.Model):
    # Basic user model for the accounts app
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.username
```

In `apps/jobs/models.py`:
```python
from django.db import models

class JobListing(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title
```

In `apps/applications/models.py`:
```python
from django.db import models

class Application(models.Model):
    resume_file = models.FileField(upload_to='resumes/')
    status = models.CharField(max_length=50, default='received')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Application {self.id}"
```

In `apps/analysis/models.py`:
```python
from django.db import models

class AnalysisResult(models.Model):
    application = models.ForeignKey('applications.Application', on_delete=models.CASCADE)
    score = models.IntegerField()  # 0-100 scoring system
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Analysis for {self.application.id}"
```

In `apps/subscription/models.py`:
```python
from django.db import models

class Subscription(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    plan_name = models.CharField(max_length=100)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan_name}"
```

Then create empty `__init__.py` files in each app's subdirectories to make them Python packages:
```bash
touch apps/accounts/__init__.py
touch apps/jobs/__init__.py
touch apps/applications/__init__.py
touch apps/analysis/__init__.py
touch apps/subscription/__init__.py
```

### 15. Start Redis Server
Make sure Redis is running on your system:
```bash
redis-server  # Or use your system's service manager
```

### 16. Start the Development Server
```bash
python manage.py runserver
```

### 17. (Optional) Start Celery Worker
In a separate terminal:
```bash
celery -A celery_app worker --loglevel=info
```

## Directory Structure Verification
After setup, your project should have the complete structure:
```
TI_AI_SaaS_Project/     # Project root
├── x_crewter/          # Django project directory
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/               # Container for all core Django applications
│   ├── accounts/       # TAS User Authentication, Registration, Login/Logout, Profile Management
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── jobs/           # Job Listing CRUD (Create, Read, Update, Deactivate), screening questions, and requirements definition
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── applications/   # Public form handler, Resume Upload/Storage, Applicant persistence, and initiates parsing/analysis via Celery
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── analysis/       # TAS Dashboard View, AI results display, bulk analysis initiation/filtering
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   └── subscription/   # Subscription scaffolding, Amazon Payment Services (APS) integration
│       ├── models.py
│       ├── views.py
│       ├── urls.py
│       ├── templates/  # Application-specific HTML templates
│       ├── static/     # Application-specific static assets
│       │   ├── js/
│       │   ├── css/
│       │   └── images/
│       └── tests/      # Application-specific tests
│           ├── unit/
│           ├── integration/
│           └── e2e/
├── services/           # Container for non-Django dependent core services (LLM, Email, File)
│   ├── ai_analysis/    # LangGraph definition, Ollama client, and scoring logic
│   ├── email_service/  # External email client wrapper and templating
│   └── file_storage/   # S3/GCS wrapper and file hash utilities
├── static/             # Global static files (compiled Tailwind, common images)
├── templates/          # Global base templates (footer, navbar, base.html)
├── requirements.txt    # Project dependencies
├── manage.py
└── celery_app.py       # Celery configuration file
```

## Verification Steps
1. Visit `http://127.0.0.1:8000/` - you should see the homepage
2. Check that environment variables are loaded correctly
3. Verify database connectivity
4. Test that static files are served properly
5. Confirm all required directories and subdirectories exist as specified

## Troubleshooting
- If you get a database error, ensure Django settings are configured correctly
- If static files don't load, check that `STATIC_URL` and `STATIC_ROOT` are configured
- For Celery issues, ensure Redis is running and URL is correct in settings
- If Django can't find apps, ensure they're added to INSTALLED_APPS and have proper __init__.py files