# JBSN Creative — Voice Workforce Blueprint (Zero-Budget First)

## Objective
Build a shared voice-agent platform with separate specialist roles. Start with browser-based voice tests and local/self-hosted components; do not depend on paid telephony or paid model APIs for the first proof of concept.

## Platform decision
- Candidate platform: Dograh AI, BSD-2-Clause open source, self-hostable, visual workflow builder, browser Test Audio/Web Call, tool calls and telephony adapters.
- Official repository: https://github.com/dograh-hq/dograh
- Documentation: https://docs.dograh.com
- First milestone is browser-based testing. A live public telephone number is explicitly out of scope until there is a no-cost route or funding.
- Do not assume a local LLM is fast enough on the Founder laptop; benchmark the available hardware first. Do not expose the local service to the public internet by default.

## Specialist agents

### 1. AI SDR — Thando
Goal: qualify a prospect and book a discovery meeting.
Flow: disclose AI identity → ask permission to continue → establish business type and decision-maker → discover current problem → understand urgency and desired outcome → check qualification criteria → request a real slot from the booking tool → confirm timezone and email → create booking → write outcome to CRM → send concise confirmation.
Rules: no invented case studies, pricing, guarantees, or available slots; never claim a booking until the calendar tool confirms it; respect opt-outs immediately.

### 2. AI Closer — Sibusiso
Goal: handle warm inbound leads and qualified follow-ups.
Flow: verify the prospect's requested service → clarify goals, scope, timeline and budget range → explain only approved packages and terms → answer supported objections → summarize scope → create a draft proposal or hand off for human approval.
Rules: do not sign contracts, promise unapproved discounts, charge money, or make unsupported guarantees. Founder approval required for binding terms.

### 3. Receptionist — Zinhle
Goal: answer inbound calls/web calls, identify intent, answer FAQs and route.
Flow: greeting and AI disclosure → caller intent → answer from approved knowledge base → book/reschedule/cancel only through a live booking tool → route to the right department → record a minimal call summary.
Fallback: offer human follow-up when information is missing or caller requests a person.

### 4. Onboarding Coordinator — Lerato
Goal: onboard new clients after confirmed payment/contract status.
Flow: verify status from trusted order system → gather required project inputs → explain next steps and timeline from approved records → book kickoff → create onboarding checklist → flag missing materials.
Rules: never infer payment from a caller's statement; do not reveal another client's data; don't promise a delivery date without an approved project record.

### 5. Fulfilment Coordinator — Mandla
Goal: collect project status and coordinate delivery updates.
Flow: look up authorized project → summarize current stage → request missing assets → schedule review → create follow-up task → escalate overdue/blocked work.
Rules: no invented progress, no exposing credentials or internal notes, no marking deliverables complete without a system confirmation.

### 6. Client Success / Support — Simphiwe
Goal: handle routine questions, triage issues and preserve customer satisfaction.
Flow: identify account safely → classify issue → retrieve approved help content → run allowlisted diagnostics → create support ticket → escalate sensitive or unresolved cases.
Rules: no destructive actions or sensitive account changes without verification and approval.

## Shared booking tool contract
Create one deterministic internal booking service used by all agents:
- `availability(service, duration_minutes, timezone, date_range)` returns real slots from the authoritative calendar.
- `book(slot_id, name, email, consent_to_contact, agent_id, reason)` validates that slot is still open and atomically reserves it.
- `reschedule(booking_id, verified_email, new_slot_id)` verifies ownership and reserves the new slot before releasing the old one.
- `cancel(booking_id, verified_email)` validates ownership and records cancellation.
- `get_booking(booking_id, verified_email)` returns only the caller's booking.
- Every mutation is idempotent, timestamped, and recorded in an audit log.
- First local test may use a clearly labelled mock calendar. Never present mock slots as real appointments.
- Production calendar connector can be Google Calendar or another calendar only after OAuth is configured. Do not store OAuth tokens in source control.

## CRM and event schema
Record: lead_id, contact_source, permission_basis, consent_timestamp, do_not_call, agent_id, call_session_id, intent, qualification_fields, appointment_id, appointment_status, follow_up_owner, outcome, created_at, updated_at.
Minimize personal data. Enforce opt-out suppression across all outbound campaigns. Retain only what is needed for the business purpose.

## Zero-budget build order
1. Run Dograh locally via its official Docker Compose setup and test in browser.
2. Build Receptionist and SDR workflows using mock data; validate speech, interruptions, disclosure and opt-out behavior.
3. Implement and test the booking tool contract with mock slots, including race conditions and duplicate requests.
4. Add a real calendar only after account authorization; verify timezones and confirmations.
5. Connect CRM through authenticated internal APIs with scoped credentials.
6. Test onboarding, fulfilment and support on synthetic client records.
7. Only later evaluate phone/SIP integration and legal requirements for outbound calls.

## Acceptance criteria before a real customer pilot
- Agent discloses it is AI and does not impersonate a human.
- Booking confirmations only follow successful calendar writes.
- No duplicate bookings under concurrent requests.
- Correct timezone and calendar availability.
- Opt-out immediately suppresses future outreach.
- Caller can request a human and receives a reliable handoff/follow-up.
- No cross-client data access in tests.
- All external actions have audit events.
- Voice routes and signature/auth checks pass in a staging environment.
- Production deployment and health checks are verified.
