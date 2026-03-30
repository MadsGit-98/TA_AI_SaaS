# TA_AI_SaaS - AI Talent Acquisition Platform

## Project Overview

TA_AI_SaaS is an intelligent Talent Acquisition Software as a Service platform that leverages cutting-edge AI technologies to revolutionize the recruitment process. This platform enables recruiters and hiring managers to efficiently manage job listings, process applications, and analyze candidate resumes using advanced AI-powered scoring and matching algorithms.

### 🎯 Purpose

The platform is designed to streamline talent acquisition workflows by:
- Automating resume analysis and candidate evaluation
- Providing intelligent candidate-job matching
- Reducing time-to-hire through AI-powered insights
- Enabling data-driven hiring decisions

## ✨ Key Features

### User Authentication & Account Management
- Secure JWT-based authentication with HTTP-only cookies
- User registration and email verification
- Password reset functionality
- "Remember Me" functionality for extended sessions
- Social authentication integration (python-social-auth)

### Job Management Dashboard
- Create and manage job listings
- Track job applications in real-time
- View candidate metrics and analytics
- Subscription-based access for job posting

### AI-Powered Resume Analysis
- Intelligent resume parsing and analysis using LangChain and LangGraph
- Automated candidate scoring based on job requirements
- Real-time analysis progress tracking via WebSocket
- Support for multiple document formats (PDF, DOCX, TXT)
- Candidate ranking and matching algorithms

### Real-time Updates
- WebSocket-based real-time analysis status updates
- Live progress notifications during resume processing
- Fallback polling for legacy browser support
- Efficient message delivery with minimal server overhead

### Application Management
- Online application form submission
- File upload support for resumes and documents
- Application tracking and status management
- Candidate communication workflows

### File Management
- Secure file upload and storage
- Amazon S3 / Google Cloud Storage integration
- Local development media storage
- File validation and security checks

## 🛠️ Technology Stack

### Backend
- **Framework**: Django 5.2.9, Django REST Framework 3.15.2
- **Language**: Python 3.11
- **Authentication**: djangorestframework-simplejwt, djoser, python-social-auth
- **Task Queue**: Celery 5.4.0
- **Cache/Messaging**: Redis 7.1.0
- **Database**: SQLite3 (initial), upgradeable to PostgreSQL

### Frontend
- **Language**: JavaScript (ES6)
- **Styling**: Tailwind CSS
- **Components**: shadcn_django
- **Real-time Communication**: WebSocket with fallback mechanisms

### AI & Machine Learning
- **LLM Integration**: LangChain 1.1.x
- **Graph Processing**: LangGraph 1.0.x
- **Text Processing**: python-hashlib
- **Document Processing**: python-docx, PyPDF2

### Real-time Features
- **WebSocket**: Django Channels 4.x
- **Message Broker**: Redis 7.1.0
- **Session Management**: Redis with JWT tokens

### File Storage
- **Cloud Storage**: Amazon S3 / Google Cloud Storage (via django-storages)
- **Local Development**: Media directory storage
- **File Type Support**: PDF, DOCX, TXT, and other document formats

### Development & DevOps
- **Version Control**: Git
- **Task Automation**: Celery with Redis
- **Testing**: Django test runner (python manage.py test)

## 📦 Installation & Setup

### Prerequisites
- Python 3.11 or higher
- Redis 7.1.0 or higher
- Node.js (for frontend dependencies, optional)
- Virtual environment management tool (venv or conda)

### Step 1: Clone the Repository
```bash
git clone https://github.com/MadsGit-98/TA_AI_SaaS.git
cd TA_AI_SaaS

### Step 2: Install Python Dependencies
pip install -r requirements.txt

### Step 3: Configure Environment Variables
Create a .env file in the project root:


# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3
# For PostgreSQL: postgresql://user:password@localhost:5432/ta_ai_saas

# Redis
REDIS_URL=redis://localhost:6379/0

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@x-crewter.com

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name

# Google Cloud Storage (optional)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_STORAGE_BUCKET=your-bucket-name

# Frontend URLs
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
