# Deployment Configuration for Job Listing Feature

## Environment Variables
The following environment variables are required for the job listing feature:

### Required Variables
- `REDIS_URL`: URL for Redis server (used for Celery broker)
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Django secret key for cryptographic signing

### Optional Variables
- `CELERY_BROKER_URL`: Override default Redis URL for Celery (defaults to REDIS_URL)
- `CELERY_RESULT_BACKEND`: Override default Redis URL for results (defaults to REDIS_URL)
- `DEBUG`: Set to False in production (defaults to False)

## Celery Configuration
The job listing feature uses Celery for background tasks, specifically for:
- Automatic job activation/deactivation based on start/end dates
- Periodic checks every 60 seconds

### Required Services
- Redis server for Celery broker and results backend
- Worker processes running `celery -A x_crewter worker`
- Beat scheduler running `celery -A x_crewter beat`

## Database Migrations
Before deploying, run the following commands:
```
python manage.py makemigrations
python manage.py migrate
```

## Static Files
Collect static files before deployment:
```
python manage.py collectstatic --no-input
```

## Security Considerations
- Ensure all API endpoints require authentication
- Use HTTPS in production
- Set proper CORS policies
- Configure Content Security Policy headers

## Monitoring
- Monitor Celery worker processes
- Check logs for task execution
- Monitor database connections
- Track API response times

## Scaling Recommendations
- Scale Celery workers based on job listing volume
- Monitor Redis memory usage
- Consider database indexing for job listing queries
- Cache frequently accessed job listing data

## Rollback Plan
If deployment fails:
1. Revert code changes
2. Run previous migration commands if needed
3. Restart application servers
4. Verify functionality