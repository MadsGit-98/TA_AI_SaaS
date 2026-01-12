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

- Python 3.11 + Django, Django REST Framework (DRF), Tailwind CSS, shadcn_django (002-compliant-home-page)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.11: Follow standard conventions

## Recent Changes
- 006-remember-me-functionality: Added Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser, Celery, Redis, uuid6, nanoid
- 005-uuid-migration: Added Python 3.11 + Django, Django REST Framework (DRF), uuid6, nanoid, Celery, Redis
- 004-secure-jwt-cookies: Added Python 3.11 + Django, Django REST Framework (DRF), djangorestframework-simplejwt, djoser


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
