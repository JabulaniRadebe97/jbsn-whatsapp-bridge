# JBSN AI OS Core Runtime — bootstrap 0.4.0

A safe bootstrap service for the JBSN autonomous handover engine. It supports PostgreSQL persistence when `DATABASE_URL` is set and `JBSN_DATABASE_BACKEND=postgres`; otherwise it uses local SQLite for development.

## Endpoints
- `GET /health` (liveness and database connectivity)
- `GET /v1/tasks` (Bearer token required)
- `POST /v1/tasks` with `{ "title":"Draft launch plan", "task_type":"plan", "payload":{"objective":"Build JBSN Creative launch workflow"}, "risk":"green" }`
- `POST /v1/worker/run-one` (executes one queued allowlisted task: `plan` or Gemini `business_plan`)
- `POST /v1/tasks/{id}/approval` with `{ "decision":"approved", "decision_by":"founder", "reason":"Reviewed" }`
- `GET /v1/tasks/{id}` and `/v1/tasks/{id}/events`

## Persistence
In Render, configure `DATABASE_URL` using the database's **internal** connection string when service and database are in the same region. Set `JBSN_DATABASE_BACKEND=postgres`. Never commit or paste the connection string into source control. Install dependencies with `pip install -r aios-runtime/requirements.txt` from the repository root before starting the service.

## Safety scope
The deterministic `plan` task needs no external model. The `business_plan` task uses Google Gemini to generate and validate a structured plan. Prefer the existing Apps Script provider by setting `JBSN_GEMINI_PROXY_URL` to the deployed Apps Script web-app URL and `JBSN_GEMINI_PROXY_TOKEN` to a shared secret. Add `apps-script/JBSN_AIOS_GEMINI_PROXY.gs` to the existing UCX project, route `action: 'aios_business_plan'` in `doPost`, set Script Property `JBSN_AIOS_PROXY_TOKEN` to the same secret, and redeploy that Apps Script web app. The adapter reads the existing `GEMINI_API_KEY` Script Property; it does not create customer or lead records. Do not expose or commit either secret. Direct `GEMINI_API_KEY` in Render remains a fallback if no proxy URL is configured. It does not write or execute generated code, deploy applications, send outreach, spend money, or take external actions. Configure `GEMINI_API_KEY` as a secret environment variable; never commit it. Amber/red tasks require recorded approval. Unknown task types are rejected.

## Required deployment configuration
Set `JBSN_API_TOKEN` to a strong random secret. A PostgreSQL database needs backups, monitoring, and a tested restore procedure before it should be treated as production-of-record.

## Run locally
From repository root: `pip install -r aios-runtime/requirements.txt` then `cd aios-runtime && python main.py`. Set `JBSN_API_TOKEN`. For PostgreSQL mode, also set `DATABASE_URL` and `JBSN_DATABASE_BACKEND=postgres`.
