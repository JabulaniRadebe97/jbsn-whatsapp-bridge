# JBSN AI OS Core Runtime — bootstrap 0.2.0

A safe bootstrap service for the JBSN autonomous handover engine. It supports PostgreSQL persistence when `DATABASE_URL` is set and `JBSN_DATABASE_BACKEND=postgres`; otherwise it uses local SQLite for development.

## Endpoints
- `GET /health` (liveness and database connectivity)
- `GET /v1/tasks` (Bearer token required)
- `POST /v1/tasks` with `{ "title":"Draft launch plan", "task_type":"plan", "payload":{"objective":"Build JBSN Creative launch workflow"}, "risk":"green" }`
- `POST /v1/worker/run-one` (executes one queued plan task)
- `POST /v1/tasks/{id}/approval` with `{ "decision":"approved", "decision_by":"founder", "reason":"Reviewed" }`
- `GET /v1/tasks/{id}` and `/v1/tasks/{id}/events`

## Persistence
In Render, configure `DATABASE_URL` using the database's **internal** connection string when service and database are in the same region. Set `JBSN_DATABASE_BACKEND=postgres`. Never commit or paste the connection string into source control. Install dependencies with `pip install -r aios-runtime/requirements.txt` from the repository root before starting the service.

## Safety scope
Only the `plan` worker is enabled. It returns a plan; it does not write or execute generated code, deploy applications, send outreach, spend money, or call external AI models. Amber/red tasks require recorded approval. Unknown task types are rejected.

## Required deployment configuration
Set `JBSN_API_TOKEN` to a strong random secret. A PostgreSQL database needs backups, monitoring, and a tested restore procedure before it should be treated as production-of-record.

## Run locally
From repository root: `pip install -r aios-runtime/requirements.txt` then `cd aios-runtime && python main.py`. Set `JBSN_API_TOKEN`. For PostgreSQL mode, also set `DATABASE_URL` and `JBSN_DATABASE_BACKEND=postgres`.
