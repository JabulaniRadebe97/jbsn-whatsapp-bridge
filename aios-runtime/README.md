# JBSN AI OS Core Runtime — bootstrap 0.1.0

A safe bootstrap service for the JBSN autonomous handover engine. Python standard library only; SQLite-backed task queue and audit events.

## Endpoints
- `GET /health` (public liveness only)
- `GET /v1/tasks` (Bearer token required)
- `POST /v1/tasks` with `{ "title":"Draft launch plan", "task_type":"plan", "payload":{"objective":"Build JBSN Creative launch workflow"}, "risk":"green" }`
- `POST /v1/worker/run-one` (executes one queued plan task)
- `POST /v1/tasks/{id}/approval` with `{ "decision":"approved", "decision_by":"founder", "reason":"Reviewed" }`
- `GET /v1/tasks/{id}` and `/v1/tasks/{id}/events`

## Safety scope
Only the `plan` worker is enabled. It returns a plan; it does not write or execute generated code, deploy applications, send outreach, spend money, or call external AI models. Amber/red tasks require recorded approval. Unknown task types are rejected.

## Required deployment configuration
Set `JBSN_API_TOKEN` to a strong random secret. SQLite on a free ephemeral service is not durable; task history may be lost on restart or redeploy. Do not use this bootstrap as production-of-record until persistent storage, backups, rate limiting, monitoring and security review are in place.

## Run locally
`python main.py` (Python 3.10+; no external packages). Set `JBSN_API_TOKEN` before starting.
