# App Deployment Runbook

## Environments

- `app-staging`
- `app-production`

## Required Secrets

- `APP_STAGING_URL`
- `APP_PRODUCTION_URL`
- `AI_SERVICE_BASE_URL`
- `AI_SERVICE_API_KEY`
- `AI_SERVICE_WEBHOOK_SECRET`
- `REDIS_URL`

## Cutover Steps

1. Set staging `AI_SERVICE_BASE_URL` to the service staging endpoint.
2. Ensure `AI_SERVICE_API_KEY` exists in service `API_KEYS`.
3. Ensure `AI_SERVICE_WEBHOOK_SECRET` matches service `WEBHOOK_SECRET`.
4. Deploy app to staging.
5. Validate: initiate, rerun, cancel, progress, completed, failed flows.
6. Promote same app artifact to production.

## Rollback

1. Restore previous app release.
2. Restore previous `AI_SERVICE_BASE_URL` and related secrets if changed.
3. Validate analysis initiation and webhook processing.
