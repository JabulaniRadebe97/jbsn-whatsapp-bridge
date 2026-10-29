# JBSN World HQ — Locked UI/UX and Integration Contract

Status: approved visual direction; architecture baseline is locked.
Version: 2026-10-29
Base branch: jbsn-aios-runtime-bootstrap
Working branch: jbsn-hq-locked-integration

## Non-negotiable visual direction
- Preserve the approved cinematic executive HQ: black/charcoal, restrained gold, warm architectural lighting, editorial typography, bespoke spacing, realistic synthetic character portraits, rich media, motion graphics, and a responsive one-tab founder workspace.
- This is the canonical JBSN World HQ direction. Do not replace it with a generic admin template or a simplified competing dashboard.
- The HQ must be accessible on laptop and phone, support reduced motion, and have clear loading, empty, error, offline, and permission states.
- Never display demo values as live business metrics. Every panel must show source and last-updated time or a clearly labelled demo/placeholder state.
- AI employee identities are fictional characters. They should feel personable and consistent, but customer-facing identity must not be deceptive where disclosure is required.

## Locked business and control architecture
JBSN World (holding company)
-> Founder / Chairman Command Centre
-> JBSN World Control Plane™
-> JBSN AI OS™ / AIOS Director
-> Agent Registry + Identity/Permissions + Memory + Knowledge Engine + Model Router
-> Task Engine + Workflow Engine + Checkpointed Worker Execution + Audit + Health + Recovery
-> AI Workforce and business engines
-> JBSN Creative™ first revenue business
-> future subsidiaries.

## Existing canonical baseline to preserve
- Google Apps Script + Google Workspace/Sheets/Drive Control Plane and Command Centre.
- Existing command-centre web app URL: https://script.google.com/macros/s/AKfycbyMs8HZAd-0usMxwfl8xHdyQZQAjhxQgWU0NQEbi0JhQ4Yu3oV2S5WHjW0QUeF3RqouvA/exec
- Website: https://jbsncreative.netlify.app/
- Existing AIOS runtime service: https://jbsn-aios-core.onrender.com
- Existing AIOS runtime repo: https://github.com/JabulaniRadebe97/jbsn-whatsapp-bridge/tree/jbsn-aios-runtime-bootstrap
- Existing prospect demo site: https://jbsn-prospect-demos.onrender.com
- Existing WhatsApp bridge must remain separate from the main JBSN Creative website deployment.
- Stack direction: OpenAI Responses API/model routing; Claude/Claude Code; Hyperagent/Paperclip; n8n; GitHub; Supabase/PostgreSQL/Auth/Storage/RLS; Next.js/Vercel target; existing Netlify website; Meta/WhatsApp; analytics; STT/LLM/TTS voice; CRM/Customer 360; customer portal; finance; delivery; QA; knowledge; autonomous build factory.
- Do not claim every listed component is connected just because it is in the architecture. Integration status must be verified per service.

## Locked execution and safety rules
- One controlled worker per Apps Script cycle.
- Execution budget: 210,000 ms; safety margin: 30,000 ms.
- Checkpoint and exit safely before runtime limit; continuation trigger every 5 minutes.
- OpenAI failure cooldown: 60 minutes. Overpass cooldown: 30 minutes.
- GREEN: low-risk, pre-authorized actions.
- YELLOW: Founder approval required.
- RED: Chairman-controlled security, credentials, payment confirmation, governance, emergency stop, and critical production changes.
- Preserve architecture lock, audit logging, idempotency, retries/backoff, failure recovery, and subsystem health monitoring.
- Never put secrets in browser code, static files, Git commits, or client logs.

## Required HQ modules
1. Founder overview and daily briefing.
2. Sales / CRM: lead source, B2C qualification, attempts, callback, appointment, proposal, won/lost, consent/legal basis, notes, owner, timestamps, next action.
3. Customer 360 and customer zone: orders, contracts, files, messages, tickets, approvals, payment/invoice state, delivery status, support, reports.
4. Payments and finance: Paystack integration readiness; server-side transaction initialization; signed webhook verification; idempotent payment records; EFT fallback; no payment marked paid without provider-confirmed evidence.
5. Projects and delivery: milestones, deliverables, review, QA, approval, handover, retention and upsell.
6. AI workforce: registry, role, personality, tools, permissions, KPIs, autonomy score, health, audit trail.
7. Thando companion: authenticated cloud chat, durable approved memory, voice input/output, session continuity, proactive briefings via authorized channels, user-controlled mood check-ins, task creation and status. Browser speech alone does not satisfy cloud voice requirements.
8. Media and motion studio: brand library, synthetic employee portraits, playable videos, animated visualisations, creative briefs, asset metadata, reduced-motion mode.
9. Autonomous Build OS: Observe -> Analyse -> Design -> Plan -> Build -> Test -> Security QA -> Verify -> Deploy (approval gated) -> Monitor -> Measure -> Improve.
10. Systems, knowledge, analytics, settings, security, approvals, notifications, audit, health and emergency stop.

## Integration requirements
- The visual frontend must call an authenticated backend adapter, never directly expose provider credentials.
- The Apps Script Control Plane remains the orchestration/governance source until an explicit migration is designed and approved.
- Build a compatibility adapter for existing Command Centre functions and Sheets records; do not duplicate canonical state in localStorage.
- Browser localStorage may hold harmless display preferences only. Business records and agent memory require durable server-side persistence and access control.
- Backend health is not proof that model, voice, memory, CRM, payments or messaging are configured. Each capability has its own status and verification timestamp.
- Cloud agent work must be checkpointed, resumable, idempotent, permissioned, observable and recoverable.
- Outbound messages, payment/refund actions, production deployments, credentials changes and other sensitive operations require explicit approval according to GREEN/YELLOW/RED policy.
- Voice should be natural and expressive but the agent must not falsely claim to be a biological human. Recordings, microphone access and external communication require appropriate consent and disclosure.

## Definition of done
A module is production-ready only when:
- real data is connected through authenticated APIs;
- access control and audit logs work;
- success, failure, timeout, retry and empty states are tested;
- records persist across devices/sessions;
- monitoring and recovery are documented;
- no secrets are exposed;
- tests and deployment verification pass;
- live status labels are supported by fresh checks;
- founder approvals and emergency stop are verified.

## Current truth
The local creative HQ package is a UI/media build, not the live production HQ. The canonical Apps Script code and Render service exist, but live data, persistent memory, always-on voice, Paystack payment processing and full integration must be individually connected and tested. Do not label them live until verified.
