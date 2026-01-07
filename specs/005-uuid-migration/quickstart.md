# Quickstart Guide: UUID Migration

## Overview
This guide provides a quick overview of the UUID migration implementation, detailing the key changes and how to work with the new identifier system.

## Prerequisites
- Python 3.11+
- Django 4.x+
- Django REST Framework
- uuid6 library
- nanoid library
- Redis server running
- Celery configured

## Installation
1. Install required packages:
```bash
pip install uuid6 nanoid
```

2. Update your Django settings to include the new dependencies

## Key Changes

### 1. CustomUser Model
The CustomUser model has been updated to use UUIDv6 as the primary key:

```python
import uuid
from uuid6 import uuid6
from django.db import models

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid6, editable=False)
    uuid_slug = models.CharField(max_length=22, unique=True, editable=False)
    
    def save(self, *args, **kwargs):
        if not self.uuid_slug:
            import nanoid
            self.uuid_slug = nanoid.generate(size=11, alphabet="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        super().save(*args, **kwargs)
```

### 2. URL Patterns
URLs have been updated to use UUID and slug parameters:

```python
# Before
path('users/<int:pk>/', views.user_detail, name='user-detail'),

# After
path('users/<uuid:uuid>/', views.user_detail, name='user-detail'),
path('users/slug/<str:slug>/', views.user_by_slug, name='user-by-slug'),
```

### 3. Foreign Key Updates
Related models now reference the UUID:

```python
# UserProfile model
class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, db_column='user_id')
    # other fields...
```

### 4. Redis Key Updates
Session and cache keys now use UUIDs:

```python
# Before
cache_key = f"user_sessions:{user.id}"

# After
cache_key = f"user_sessions:{user.id}"
```

## Migration Steps

### 1. Prepare Migration
Before running the migration, ensure all services are stopped:
```bash
# Stop Celery workers
pkill -f celery

# Stop Django server
# Ctrl+C to stop the server
```

### 2. Run Database Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Populate UUIDs
Run the data population script:
```bash
python manage.py populate_user_uuids
```

### 4. Update Foreign Keys
Run the foreign key update script:
```bash
python manage.py update_foreign_keys_to_uuid
```

### 5. Flush Redis
Clear existing session data:
```bash
redis-cli FLUSHALL
```

## Testing
Run the test suite to ensure everything works correctly:
```bash
python manage.py test apps.accounts.tests.test_uuid_migration
```

## Rollback (if needed)
If issues occur, you can rollback to the previous state:
```bash
python manage.py migrate accounts 000X  # Previous migration number
```

## Important Notes
- The migration is atomic and should be performed during scheduled maintenance
- All existing sessions will be invalidated after the migration
- External integrations referencing user IDs will need to be updated
- Monitor application logs closely after deployment