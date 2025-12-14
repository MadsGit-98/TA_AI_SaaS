# Quickstart Guide: User Authentication Setup

This guide provides step-by-step instructions to set up the user authentication system for the X-Crewter platform.

## Prerequisites

- Python 3.11
- Django 4.x
- Django REST Framework
- PostgreSQL (or Sqlite3 for development)

## Installation

### 1. Install Required Packages if not installed.

```bash
pip install django
pip install djangorestframework
pip install djoser
pip install social-auth-app-django
pip install djangorestframework-simplejwt
pip install python-dotenv  # for environment management
```

### 2. Update Django Settings

Add the following to your `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'django.contrib.sites',
    'rest_framework',
    'rest_framework_simplejwt',
    'djoser',
    'social_django',
    'apps.accounts',  # Your accounts app
]

MIDDLEWARE = [
    # ... other middleware
    'social_django.middleware.SocialAuthExceptionMiddleware',
    # ... rest of middleware
]

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),  # Matches session timeout requirement
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Djoser Configuration
DJOSER = {
    'USER_CREATE_PASSWORD_RETYPE': True,
    'PASSWORD_RESET_CONFIRM_URL': 'password/reset/confirm/{uid}/{token}',
    'USERNAME_RESET_CONFIRM_URL': 'username/reset/confirm/{uid}/{token}',
    'ACTIVATION_URL': 'activate/{uid}/{token}',
    'SEND_ACTIVATION_EMAIL': True,
    'SERIALIZERS': {},
}

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOpenId',
    'social_core.backends.google.GoogleOAuth2',
    'social_core.backends.linkedin.LinkedinOAuth2',
    'social_core.backends.microsoft.MicrosoftOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

# Site ID for Django Sites Framework (required for social auth)
SITE_ID = 1

# Email Configuration (use console backend for development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# For production, use: 'django.core.mail.backends.smtp.EmailBackend'

# Social Auth Settings (add your actual keys in production)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('GOOGLE_OAUTH2_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('GOOGLE_OAUTH2_SECRET')

SOCIAL_AUTH_LINKEDIN_OAUTH2_KEY = os.environ.get('LINKEDIN_OAUTH2_KEY')
SOCIAL_AUTH_LINKEDIN_OAUTH2_SECRET = os.environ.get('LINKEDIN_OAUTH2_SECRET')

SOCIAL_AUTH_MICROSOFT_GRAPH_KEY = os.environ.get('MICROSOFT_GRAPH_KEY')
SOCIAL_AUTH_MICROSOFT_GRAPH_SECRET = os.environ.get('MICROSOFT_GRAPH_SECRET')

# Social Auth Pipeline (to connect social auth with existing users)
SOCIAL_AUTH_PIPELINE = [
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'social_core.pipeline.user.create_user',
    'apps.accounts.pipeline.save_profile',  # Custom pipeline for extended user data
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
]
```

### 3. Configure Password Hashing

Ensure Argon2 is your primary password hasher by adding this to your settings:

```python
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]
```

### 4. Update URL Configuration

In your main `urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.api_urls')),  # Authentication API routes
    path('auth/', include('social_django.urls', namespace='social')),  # Social auth routes
    # ... other URLs
]
```

### 5. Create Custom Models

Create a model that extends user information with subscription details in `apps/accounts/models.py`:

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    SUBSCRIPTION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('trial', 'Trial'),
        ('cancelled', 'Cancelled'),
    ]

    SUBSCRIPTION_PLAN_CHOICES = [
        ('none', 'None'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='inactive'
    )
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    chosen_subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default='none'
    )
    is_talent_acquisition_specialist = models.BooleanField(default=True)
```

### 6. Set Up Rate Limiting

Add the following to your settings to implement rate limiting:

```python
REST_FRAMEWORK = {
    # ... other settings
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',  # General anonymous request limit
        'user': '1000/day',  # General user request limit
        'login_attempts': '5/15m',  # 5 attempts per 15 minutes
    }
}
```

Then update your login view to use this specific rate limit.

### 7. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 8. Environment Variables

Create a `.env` file for sensitive information:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True

# Database settings
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Social Auth Keys (for production)
GOOGLE_OAUTH2_KEY=your_google_key
GOOGLE_OAUTH2_SECRET=your_google_secret
LINKEDIN_OAUTH2_KEY=your_linkedin_key
LINKEDIN_OAUTH2_SECRET=your_linkedin_secret
MICROSOFT_GRAPH_KEY=your_microsoft_key
MICROSOFT_GRAPH_SECRET=your_microsoft_secret

# Email settings for production
EMAIL_HOST=smtp.your-email-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True
```

## Running the Application

1. Start the development server:
   ```bash
   python manage.py runserver
   ```

2. Access the API endpoints:
   - Register: `POST /api/auth/register/`
   - Login: `POST /api/auth/login/`
   - Social login: `POST /api/auth/social/{provider}/`
   - Password reset: `POST /api/auth/password/reset/`
   - User profile: `GET /api/auth/users/me/`

## Testing

Run the authentication tests:

```bash
python manage.py test apps.accounts.tests
```

Ensure you maintain at least 90% test coverage as specified in the X-Crewter Constitution.

## Next Steps

1. Implement the frontend authentication forms using Tailwind CSS
2. Add password complexity validation
3. Implement proper email delivery for production
4. Set up monitoring and logging for authentication events