# priloj123

# Maintenance API

FastAPI backend for a maintenance workflow with RBAC, CQRS-style command/query separation, Redis/Celery background jobs, audit logging and BFF endpoints for web, mobile and desktop clients.

## Architecture

- `main.py` exposes HTTP endpoints and BFF orchestration.
- `schemas.py` contains DTOs. Incoming payloads reject unknown fields to protect against mass assignment.
- `services/commands.py` changes state: measurements, faults, recommendations, plans, tasks and report queueing.
- `services/queries.py` reads projections for dashboards, lists, reports and monitoring.
- `services/cache.py` stores short-lived read responses and invalidates them after commands.
- `workers.py` processes report-generation jobs from Celery/Redis.
- `dependencies.py`, `rbac.py` and `supabase_auth.py` handle tokens, roles and ownership checks.
- `audit.py` writes transaction logs for command/query activity.
- `observability.py` collects request counts, errors, durations and record counts.

## Run

1. Copy `.env.example` to `.env` and fill database, Supabase and Redis values.
2. Apply schema:

```bash
psql "postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME" -f setup_rbac_cqrs_queue.sql
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start Redis, API and worker:

```bash
redis-server
uvicorn main:app --reload
celery -A workers.celery_app worker --loglevel=info
```

Swagger UI is available at `/docs`.

## API Overview

- Auth: `POST /login`, `POST /auth/refresh`
- Metrologist: `POST /metrolog/collect-data`
- Expert: `GET /expert/faults`, `POST /expert/confirm`, `POST /expert/recommendation`
- Dispatcher: `POST /specialist/create-plan`, `GET /specialist/recommendations`
- Mechanic: `GET /mechanic/tasks`, `POST /mechanic/start/{task_id}`, `POST /mechanic/finish/{task_id}`, `POST /mechanic/cancel/{task_id}`
- Quality: `GET /quality/tasks`, `POST /quality/check/{task_id}`
- Reports: `POST /reports/generate`, `POST /reports/generate-delayed`, `GET /reports/status/{task_id}`, `GET /reports/jobs`, `GET /reports/document/{task_id}`
- BFF: `/bff/web/*`, `/bff/mobile/*`, `/bff/desktop/*`
- Observability: `GET /observability/metrics`, `GET /observability/hot-points`

## CQRS And Queue

Command endpoints write to normalized tables and domain events. Query endpoints read list/dashboard/report projections from `services/queries.py`. Report generation is queued through Celery, stores state in Redis via `task_status.py`, and updates `report_read_model` plus `report_documents` after the worker completes.

Read-cache entries are short-lived and are invalidated after every command that changes measurements, faults, recommendations, plans, tasks, quality checks or reports.

## Security

- Input validation checks required fields, types, ranges and string lengths.
- DTOs reject unknown fields, so clients cannot submit hidden fields like `is_admin`.
- Ownership checks use `owner_id` from the authenticated token context, not from request bodies.
- SQL calls use bound parameters instead of string-concatenated input.
- CORS is restricted with `ALLOWED_CORS_ORIGINS`.
- Rate limiting is enabled with `SECURITY_RATE_LIMIT_PER_MINUTE`.
- Responses include security headers, including CSP, frame denial and content sniffing protection.
- Local development tokens have configurable TTL and refresh flow. Supabase refresh tokens are proxied through `/auth/refresh`.

## Git Workflow

The repository uses:

- Branch strategy: `main` for stable code, `develop` for integration, `feature/<task-name>` for each task.
- Feature branches: one task equals one branch, for example `feature/security-validation`.
- Pull request: include what changed, how to verify it, and screenshots/log snippets if relevant.
- Commit messages: use a standard prefix, for example `feat: add commands`, `fix: handle invalid state`, `refactor: query layer`.

## Verification

Useful checks before submitting:

```bash
python -m compileall .
uvicorn main:app --reload
celery -A workers.celery_app worker --loglevel=info
```

Then verify `/docs`, run login, call a command endpoint, and inspect `/observability/hot-points` as an admin.

## Defense Checklist

Use this checklist during the teacher review:

1. Git workflow:
   `git branch -a` and `git log --oneline --graph --decorate --all` show `main`, `develop`, `feature/*`, standardized commits and merge flow.
2. Pull Request quality:
   `.github/pull_request_template.md` documents what changed, how to verify it and the security checklist.
3. Observability:
   `/observability/metrics` shows requests, errors, average duration, record counts and grouped areas: `GET list`, `command`, `worker`.
4. Hot points:
   `/observability/hot-points` ranks slow/error-prone/high-traffic endpoints.
5. Cache:
   `services/cache.py` provides read cache, and command handlers call `invalidate_read_cache()` after writes.
6. CQRS:
   `services/commands.py` contains state-changing operations, while `services/queries.py` contains read models/lists.
7. Queue:
   `queue_app.py` configures Celery and `workers.py` processes report generation in the background.
8. Validation and mass assignment:
   `schemas.py` uses strict DTOs with `extra="forbid"` so fields like `is_admin`, `role` or `owner_id` are rejected.
9. Access control:
   `rbac.py` and query ownership filters use the user from the token, not user-controlled request fields.
10. API security:
    `main.py` contains rate limiting, CSP, CORS allow-listing and no-store auth responses.
