# TA_AI_SaaS Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-04

## Active Technologies
- Python 3.11 + Django, Django REST Framework (DRF), djoser, python-social-auth, JWT (003-user-authentication)
- Sqlite3 for initial implementation (003-user-authentication)
- Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser (004-secure-jwt-cookies)
- Server-side Http-Only, Secure, SameSite=Lax cookies for both Access and Refresh tokens (004-secure-jwt-cookies)
- Python 3.11 + Django, Django REST Framework (DRF), uuid6, nanoid, Celery, Redis (005-uuid-migration)
- Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser, Celery, Redis, uuid6, nanoid (006-remember-me-functionality)
- Sqlite3 (initial implementation) with Redis for session/token management (006-remember-me-functionality)
- Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser, Celery, Redis, uuid, shadcn_django (007-job-listings)
- Sqlite3 (initial implementation) with potential upgrade path to PostgreSQL (007-job-listings)
- Python 3.11 + Django, Django REST Framework (DRF), django-storages, Celery, Redis, python-hashlib, python-docx, PyPDF2 (008-job-application-submission)
- Sqlite3 (initial), Amazon S3 or Google Cloud Storage for files (django-storages backend), media/ for local dev (008-job-application-submission)

- Python 3.11 + Django, Django REST Framework (DRF), Tailwind CSS, shadcn_django (002-compliant-home-page)

## Project Structure

```text
F:\Micro-SaaS Projects\X-Crewter\Software\TA_AI_SaaS\
├───.gitignore
├───LICENSE
├───QWEN.md
├───README.md
├───-p\
├───.git\...
├───.qwen\
│   └───commands\
├───.specify\
│   ├───memory\
│   ├───scripts\
│   └───templates\
├───docs\
├───specs\
│   ├───001-project-foundation-setup
│   ├───002-compliant-home-page
│   ├───003-user-authentication
│   ├───004-secure-jwt-cookies
│   ├───005-uuid-migration
│   └───...
└───TI_AI_SaaS_Project\
    └───apps\
        ├───accounts\
        ├───jobs\
        └───...
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.11: Follow standard conventions

## Development Rules and Guidelines

1. **Import Placement**: In Python files, all imports must always reside at the top of the file. No imports should be placed inside methods or functions.

2. **Testing Requirement**: Any functionality that has been added must have a corresponding test file created to test the functionality.

3. **Test Execution**: Do not use pytest to run any of the tests created. You must use the "python manage.py test" command.

## Recent Changes
- 008-job-application-submission: Added Python 3.11 + Django, Django REST Framework (DRF), django-storages, Celery, Redis, python-hashlib, python-docx, PyPDF2
- 007-job-listings: Added Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser, Celery, Redis, uuid, shadcn_django
- 006-remember-me-functionality: Added Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser, Celery, Redis, uuid6, nanoid


<!-- MANUAL ADDITIONS START -->
- Always make sure that the urls paths in any of the tests match the configured urls in the urls.py of the application.
- If there are some ratelimits that hinders the integration tests or any other tests use a teardown method that clears the cache so the rate limits are not reached during the testing
- views.py must not contain APIs or endpoints it must only render views, APIs must be defined in api.py
- Loggiing anywhere within the project must not contain any confidential information of users such as e-mail. Follow PII best practice.
- JS are not to be embedded within HTML 
- All code must comply with PEP 8 standards, with 90% unit test coverage minimum using Python's unittest module. [No imports are to be within the python functions]
- Integration tests are not to use Mocks in any ways it must test integrating the newly implemented unit interactions with the old implemented units.
- Tests must fall with their intended sub-directories.
- Strictly use the django template language (DTL) in developing html pages.
- Check imports before adding them if they already exist.

<!-- MANUAL ADDITIONS END -->
