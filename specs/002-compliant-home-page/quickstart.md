# Quickstart Guide: Compliant Home Page & Core Navigation

## Prerequisites

- Python 3.11+
- pip package manager
- Virtual environment tool (venv or virtualenv)

## Setup

### 1. Clone and Navigate to Project
```bash
cd F:\Micro-SaaS Projects\X-Crewter\Software\TA_AI_SaaS\TI_AI_SaaS_Project
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Unix/MacOS
# source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Collect Static Files (if using production settings)
```bash
python manage.py collectstatic
```

### 6. Create Superuser (for admin access)
```bash
python manage.py createsuperuser
```

## Running the Application

### Development Server
```bash
python manage.py runserver
```

The application will be accessible at `http://127.0.0.1:8000/`

## Key Configuration

### Settings
The home page and related functionality are configured in:
- `x_crewter/settings.py` - Main Django settings
- `apps/accounts/views.py` - Home page view logic
- `apps/accounts/urls.py` - URL routing for home page and auth
- `apps/accounts/templates/accounts/index.html` - Main home page template

### Admin Interface
After creating a superuser, access the admin interface at:
`http://127.0.0.1:8000/admin/`

Here you can manage home page content through the HomePageContent model.

## Testing

### Run All Tests
```bash
python manage.py test
```

### Run Specific Test Suites
```bash
# Unit tests
python manage.py test apps.accounts.tests.unit

# Integration tests
python manage.py test apps.accounts.tests.integration

# E2E tests
python manage.py test apps.accounts.tests.e2e
```

## Key Endpoints

- Home Page: `GET /` - Main landing page
- Login: `GET/POST /login/` - User authentication
- Register: `GET/POST /register/` - User registration
- Privacy Policy: `GET /privacy/` - Privacy policy page
- Terms & Conditions: `GET /terms/` - Terms of service page
- Contact: `GET /contact/` - Contact information page

## Security Headers

The application implements the following security headers as required:
- Strict-Transport-Security (HSTS)
- Content-Security-Policy (CSP)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy

These are configured in `x_crewter/settings.py`.