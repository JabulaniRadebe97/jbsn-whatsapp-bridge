# JBSN AI OS departmental workforce

The runtime now registers 12 named departmental agents: Executive Office, Sales & Revenue, Marketing & Growth, Creative Production, Client Success & Support, Operations & Delivery, Finance & Billing, People & Recruitment, Engineering & AI OS, Security/Privacy/Compliance, Analytics & Intelligence, and SEO/Reputation.

## Activation state

The registry is available from the authenticated API route `GET /v1/departments`. This activates the workforce manifest in the Command Centre API, not full autonomous execution for every department. Current worker task types remain `plan` and `business_plan`; department-specific tools, CRM connections, persistent memory, permission scopes, and department workflows still need to be implemented.

Sales voice calls use the separate guarded voice adapter. Outbound calls are disabled by default and require documented contact permission, a Founder-approved campaign, configured Twilio credentials/caller ID/callback URL, and a working Gemini key. Do not enable until the deployed signed webhook routes have been tested end to end.

## Autonomy rollout

- Phase 1: register workforce and show capability/activation state.
- Phase 2: add department-specific task schemas, KPIs, event/audit records, and least-privilege tool scopes.
- Phase 3: connect CRM, lead sources, delivery tools, calendar, and reporting; test in sandbox.
- Phase 4: automate low-risk internal workflows and drafts.
- Phase 5: run an approved voice pilot and measure contact rate, qualification, bookings, opt-outs, and cost per booked meeting.
- Keep payments, binding contracts, mass outreach, personal-data exports, and high-risk deployments approval-gated.
