# Production Readiness (Ops Checklist)

This checklist focuses on small, low-risk steps to make the current system safe to run in production without changing core behavior.

## 1) Pre-flight checks (must pass)
- Confirm API keys and providers for the configured retrievers/LLMs.
- Ensure storage directories are writable and persisted (`outputs`, `logs`, and `DOC_PATH`).
- Enable readiness checks to fail fast in misconfigured environments.

Recommended env:
- `STRICT_ENV=true` to fail startup if required keys are missing.
- `REQUIRED_ENV=OPENAI_API_KEY,TAVILY_API_KEY` if you want explicit enforcement beyond auto-detected providers.

Use health endpoints:
- `GET /healthz` returns uptime + timestamp.
- `GET /readyz` returns readiness and missing env/storage issues.

## 2) Security baseline
- Set `API_KEY` to protect write/expensive endpoints.
- Set `CORS_ALLOW_ORIGINS` to the exact frontend domain(s). Avoid `*` in production.
- Use a reverse proxy (nginx/traefik) for TLS and rate limiting.

## 3) Logging & observability
- Logs are emitted to stdout and rotated files (`logs/app.log`).
- Configure log rotation:
  - `LOG_FILE_MAX_BYTES` and `LOG_FILE_BACKUP_COUNT`
  - or set `LOG_TO_FILE=false` to rely only on stdout.
- Request logging can be toggled with `REQUEST_LOGGING`.

## 4) Storage, backup & data retention
- Persist and back up:
  - `outputs/` (generated reports)
  - `logs/` (diagnostics)
  - `DOC_PATH/` (uploaded documents)
- Use a persistent volume and periodic snapshots.
- For regulated environments, add lifecycle policies to delete old outputs/logs.

## 5) Deployment & rollback
- Prefer immutable images and explicit tags.
- Keep the previous image tag available for fast rollback.
- Use `STRICT_ENV=true` and `/readyz` in your deployment health checks.

## 6) Runtime safety knobs
- `MAX_UPLOAD_MB` to cap uploads.
- `DISABLE_RUNTIME_PIP=true` to prevent runtime package installs.
- `RELOAD=false` for production.

## 7) Quick smoke test
- Start server with production env values.
- Verify:
  - `GET /healthz` -> 200
  - `GET /readyz` -> ready: true
  - create a report and download output
  - logs are present in stdout or rotated files

