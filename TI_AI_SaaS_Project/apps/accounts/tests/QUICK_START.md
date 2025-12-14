# Quick Start Guide for Unit Tests

## 🚀 Quick Commands

### Run All Tests
```bash
cd TI_AI_SaaS_Project
python manage.py test apps.accounts.tests.unit
```

### Run Tests for Specific Module
```bash
# API helpers and utilities
python manage.py test apps.accounts.tests.unit.test_api_helpers

# Authentication backend
python manage.py test apps.accounts.tests.unit.test_authentication_backend

# RBAC middleware
python manage.py test apps.accounts.tests.unit.test_middleware

# Social auth pipeline
python manage.py test apps.accounts.tests.unit.test_pipeline_extended

# API endpoints
python manage.py test apps.accounts.tests.unit.test_api_endpoints

# Serializers
python manage.py test apps.accounts.tests.unit.test_serializers

# Models
python manage.py test apps.accounts.tests.unit.test_models
```

### Run with Coverage
```bash
coverage run --source='apps.accounts' manage.py test apps.accounts.tests.unit
coverage report
coverage html  # Generate HTML report
```

## 📁 Test File Structure