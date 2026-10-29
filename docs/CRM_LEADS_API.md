# JBSN AIOS CRM Leads API

Status: implemented on `jbsn-world-production-build-2026-10-29`; not deployed to production.
Budget: R0 new spend.
Persistence: the existing runtime database abstraction (PostgreSQL when `DATABASE_URL` is configured and the driver is installed; otherwise SQLite). Production must use durable PostgreSQL, not ephemeral-host SQLite.

## Authentication

All `/v1/leads` endpoints require the existing bearer token configured as `JBSN_API_TOKEN`. Send:

```http
Authorization: Bearer <JBSN_API_TOKEN>
Content-Type: application/json
```

The token must be stored in the hosting provider's secret settings and in a trusted server-side client configuration only. Never embed it in a public website bundle or commit it to Git.

## Endpoints

### List leads

`GET /v1/leads?limit=100&status=callback`

- `limit`: optional integer 1–200, default 100.
- `status`: optional filter from the supported status list.
- Returns persisted lead records and count.
- Does not trigger outreach.

### Create a lead

`POST /v1/leads`

Example:

```json
{
  "business_name": "Example Business",
  "contact_name": "",
  "phone": "",
  "email": "",
  "website": "https://example.co.za",
  "source": "manual_research",
  "segment": "B2C",
  "status": "new",
  "next_action": "research_contact_basis",
  "next_action_at": "",
  "notes": "",
  "contact_basis": "unknown",
  "owner": "founder"
}
```

Only `business_name` is required. No outbound communication is sent by this API. Contact basis defaults to `unknown` and must be verified before outreach.

### Update a lead

`PATCH /v1/leads/{lead_id}`

Send only fields that need updating. Supported fields are the same as lead creation. Invalid fields, statuses, email formats, and oversized values are rejected.

## Status lifecycle

`new`, `researching`, `qualified`, `attempt_1`, `attempt_2`, `callback`, `appointment`, `proposal`, `won`, `lost`, `disqualified`.

These are CRM state labels only. They do not imply a call, appointment, sale, consent, or payment happened.

## Audit and safety

Create/update events are recorded in the existing persistent event table with field names or limited metadata, not full lead payloads. API responses include `outreach_sent: false` on create/update to make the no-contact boundary explicit.

Before production release, test authenticated CRUD against the configured PostgreSQL database, verify access controls and backups, add a dedicated lead activity table if separate CRM audit retention is required, and confirm the frontend sends requests only through a protected backend adapter.
