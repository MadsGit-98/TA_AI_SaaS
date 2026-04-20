# Service Deployment Runbook

## Environments

- `service-staging`
- `service-production`

## Required Secrets

- `SERVICE_STAGING_URL`
- `SERVICE_PRODUCTION_URL`
- `API_KEYS`
- `REDIS_URL`
- `DJANGO_WEBHOOK_URL`
- `WEBHOOK_SECRET`

## Cutover Steps

1. Deploy `main` to `service-staging`.
2. Confirm `/health` and `/ready` return HTTP 200.
3. Confirm webhook delivery reaches app staging endpoint.
4. Promote exact artifact to `service-production`.

## Rollback

1. Re-deploy previous stable release tag.
2. Confirm `/health` and `/ready` return HTTP 200.
3. Verify webhooks recover in app logs.
