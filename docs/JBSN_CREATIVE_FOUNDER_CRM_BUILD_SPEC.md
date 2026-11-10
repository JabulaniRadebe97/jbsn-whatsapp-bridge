# JBSN Creative — Founder-Led CRM & Customer Zone Build Specification

**Version:** 1.0  
**Date:** 10 November 2026  
**Target:** Founder-led MVP to use for outbound sales immediately after acceptance testing  
**Repository:** JabulaniRadebe97/jbsn-whatsapp-bridge  
**Existing stack direction:** PostgreSQL + Render-hosted application + GitHub; preserve the existing runtime and extend it rather than replacing it without an explicit migration plan.

## 0. Product objective

Build one secure, responsive, browser-based JBSN Creative operating system with:

- Separate founder accounts for Jabulani and Katleho.
- A CRM with lead sourcing, enrichment, deduplication, qualification, call queues, call logs and sales pipeline.
- Separate personal calendars plus a company-wide view governed by permissions.
- A customer zone accessible from the JBSN Creative public website.
- Client website, retainer, support, appointment and results management.
- Paystack payment initiation and server-side payment verification.
- A configurable system control centre for enabling/disabling features.
- Audit logs, role-based access, consent/suppression handling and secure client-data boundaries.
- AI-assisted lead research and record creation, with human review before a lead is dial-ready.
- Future-ready interfaces for AI SDRs, Success companions, HR sourcing, finance assistance and website-delivery agents, but do not block the founder-led launch on these later capabilities.

Commercial baseline:
- Website/setup: R5,000 once-off.
- Retainer: R5,000 monthly.
- Initial invoice may collect setup plus first retainer (R10,000), if that is the agreed customer billing choice.
- Closer commission: R500 per qualifying cleared setup payment, subject to a written commission policy.
- Founder salaries: R0 in the model; dividends only when legally distributable and approved.

## 1. MVP priorities and release gates

### P0 — required before first outbound session
1. Authentication and separate founder accounts.
2. Role-based access control and audit trail.
3. Leads, businesses, contacts, source evidence and deduplication.
4. Lead qualification and priority scoring.
5. Call queue with click-to-call / manual dialling support.
6. Call outcomes, notes, follow-up tasks and suppression/opt-out controls.
7. Separate calendars and appointment booking.
8. Dashboard with leads, calls, appointments, pipeline and next actions.
9. CSV import/export with validation and duplicate warnings.
10. Backup and basic error monitoring.

### P1 — required before taking a first customer payment through the CRM
1. Paystack checkout/payment request creation on the server.
2. Signed webhook verification and idempotent event handling.
3. Payment ledger and reconciliation status.
4. Customer record creation only after verified payment.
5. Customer zone account invitation and password reset.
6. Customer subscription/retainer record and next billing date.
7. Invoice/receipt history and payment status.

### P2 — after the founder-led flow is proven
- Client website/project management and staging/live links.
- Customer support tickets, update requests and support calendar.
- Client results reporting.
- Success companion with proactive briefings and approval-gated actions.
- AI SDR / appointment reminders / HR / finance / delivery agents.
- Voice calling integrations and automated call summaries.

Do not represent an incomplete feature as live. Use feature flags to hide or disable unfinished modules.

## 2. User roles and permissions

### Founder accounts
Create two individual founder users: Jabulani and Katleho. Do not use a shared founder login.

Founder permissions:
- Read company-wide dashboard and all operational records.
- View all leads, clients, payments, projects and department performance.
- Assign leads and staff.
- Configure feature flags and integration settings.
- Approve refunds, discounts, large expenses, staff access and website publication according to approval thresholds.
- View audit logs and export authorised reports.
- Manage their own calendar and view the other founder's availability subject to calendar privacy settings.

High-risk actions should support dual approval (configurable), including refunds above a threshold, bank/payment configuration changes, bulk data export, deletion of customer records and changing privileged users.

### Staff roles
- Closer: assigned leads, contact history, own calendar, proposals and deals; no payroll or unrestricted finance access.
- SDR: approved lead queues, business contact data, call logs and follow-ups; no payment secrets or full finance data.
- Customer Success: assigned customers, onboarding, support tickets, client websites and service status.
- Engineer/delivery: assigned projects, requirements, staging/live deployment controls and QA.
- Finance: invoices, payment ledger, expenses and reconciliation; no ability to change payment credentials without founder approval.
- HR: applicants, recruitment pipeline and authorised staff records; no unrestricted client financial information.
- Admin: narrowly scoped technical administration; privileged actions audited.

Enforce permissions server-side on every API endpoint. Hiding a button in the UI is not access control.

## 3. Core application navigation

Use one authenticated shell and one Chrome tab with a persistent left navigation:

1. Home / Founder HQ
2. Lead Finder
3. CRM / Businesses
4. Contacts
5. Dialler Queue
6. Calendar
7. Sales Pipeline
8. Clients
9. Customer Zone Admin
10. Websites / Delivery
11. Retainers / Support
12. Payments / Finance
13. Reports
14. AI Agents
15. System Control Centre
16. Settings / Audit Log

Open the public JBSN Creative website in an embedded preview or a new authenticated tab/window as appropriate. Do not embed third-party sites where their security headers prohibit framing. Provide a clear external-open action.

## 4. CRM data model

Use PostgreSQL with migrations, foreign keys, indexes, created_at/updated_at timestamps and soft deletion where appropriate. Minimum entities:

### users
- id (UUID primary key)
- full_name
- email (unique, normalised)
- password_hash or external auth subject
- role
- status (invited/active/suspended)
- timezone
- last_login_at
- created_at, updated_at

### businesses
- id
- legal_or_trading_name
- category / industry
- registration_number (optional; do not guess)
- physical_address
- service_area
- city, province, country
- google_place_id (optional; identifier only)
- public_business_phone
- public_business_email
- public_website_url
- website_status (none/outdated/modern/unknown)
- website_assessment (JSON with evidence and checks)
- google_rating
- google_review_count
- lead_score
- qualification_status
- owner_user_id / assigned_to
- pipeline_stage
- do_not_contact (boolean)
- suppression_reason
- created_at, updated_at

### contacts
- id
- business_id
- full_name (only if reliably sourced)
- job_title / decision_role (owner, CEO, director, marketing, operations, admin, unknown)
- contact_type (public_business_line, published_work_mobile, published_work_email, contact_form, social_page, other)
- phone_e164 (nullable)
- email (nullable)
- source_id
- verification_status (unverified/verified/invalid)
- confidence_score (0-100)
- directness (direct_decision_maker / department / reception / general_business)
- last_verified_at
- do_not_contact
- created_at, updated_at

### sources
- id
- provider (google_places, official_website, facebook_page, instagram_business_profile, linkedin_company_url, directory, user_entry, other)
- source_url
- source_record_id / place_id
- accessed_at
- attribution_text / attribution_url where required
- permitted_storage_class
- evidence_summary
- confidence
- created_at

### lead_evidence
- id
- business_id
- source_id
- field_name
- observed_value
- evidence_url
- observed_at
- confidence_score
- reviewer_id
- review_status (pending/accepted/rejected)
- notes

### activities
- id
- business_id
- contact_id (nullable)
- user_id
- activity_type (call, email, meeting, note, task, source_review, payment, website_audit)
- outcome
- started_at
- duration_seconds
- summary
- next_action_at
- created_at

### appointments
- id
- business_id
- contact_id
- assigned_closer_id
- created_by
- start_at, end_at
- timezone
- meeting_type
- meeting_link
- status (booked/confirmed/attended/no_show/rescheduled/cancelled)
- reminder_status
- notes

### opportunities
- id
- business_id
- owner_user_id
- stage (new/qualified/contacted/meeting_booked/meeting_held/proposal/won/lost/nurture)
- setup_amount
- retainer_amount
- expected_close_date
- lost_reason
- payment_status
- created_at, updated_at

### clients
- id
- business_id
- primary_contact_id
- account_status
- onboarding_status
- service_start_date
- assigned_cs_owner
- client_portal_user_id
- created_at, updated_at

### subscriptions
- id
- client_id
- provider (paystack/manual_eft)
- paystack_subscription_code (nullable)
- amount
- currency (ZAR)
- interval
- billing_anchor
- next_billing_date
- status
- cancellation_requested_at
- created_at, updated_at

### payments
- id
- client_id / opportunity_id
- provider_reference (unique)
- provider
- amount
- currency
- status (initiated/pending/success/failed/refunded/disputed)
- paid_at
- raw_webhook_event_id
- verified_at
- created_at

### client_websites, projects, tickets, expenses, commissions, approvals, feature_flags, audit_events
Create these as separate relational entities with clear ownership, status and timestamps. Never store payment card data or secret API credentials in these tables.

## 5. Lead sourcing and enrichment engine

### Primary target profile
Find real businesses that:
- Operate in selected South African service categories, initially contractors and trades.
- Have a meaningful public review footprint (configurable minimum; default 5 reviews).
- Have either no website or a demonstrably outdated/poor website.
- Have an identifiable public business phone, official email, contact form or published business social channel.
- Are not already clients, active opportunities, duplicates or on a suppression list.

Suggested initial filters:
- Minimum review count: 5 (configurable).
- Minimum rating: optional; do not reject a business solely for a low rating if the user wants all reviewed businesses.
- Website status: no website OR outdated.
- Business status: open/operating where reliable status is available.
- Geography and category: founder-configurable (e.g. Lejweleputswa / Welkom / Free State; builders, electricians, plumbers, roofers, painters, paving, renovations, solar, HVAC, security, landscaping).
- Exclude chains/franchises or irrelevant categories where configured.

### Source adapters and platform rules

**Google Maps / Google Places API**
- Use the official Google Places API (New): Text Search / Nearby Search, then Place Details.
- Request only needed fields: place id, display name, formatted address, national/international phone, website URI, rating, user rating count, business status and required attributions.
- Avoid requesting review text by default; rating and review count are sufficient for the first qualification pass and are cheaper than requesting review content.
- Follow Google Maps Platform storage, caching, attribution and display requirements. Do not assume Places content can be permanently copied into the CRM. Store the Place ID and permitted metadata; retain/re-display data only within Google's current terms and permitted exceptions. Provide required Google branding/attribution wherever Places data is displayed.
- Use server-side API keys, restrict keys by API and environment, set quotas and billing alerts.

**Official business websites**
- Visit only public pages that are accessible without login.
- Extract business-published contact channels and company role information, with source URL and timestamp.
- Respect robots.txt, site terms, rate limits and privacy law. Do not bypass authentication or technical controls.
- Prefer company contact pages, About pages, team pages and official business contact pages.
- Store the evidence URL and the exact context showing why a number/email is considered a business contact.

**LinkedIn**
- Do not scrape LinkedIn pages, automate logged-in browsing, use fake accounts, or export profile data into a prospecting CRM.
- LinkedIn's terms restrict scraping and its Marketing API member data is not permitted as a general sales-lead enrichment feed.
- Store a company LinkedIn URL as a manual research reference if supplied or lawfully discovered, but do not ingest member profiles or personal contact data into the CRM through unauthorised scraping.
- If LinkedIn offers a specific authorised product/API for a permitted use case, implement only within that product's written scope and terms.

**Facebook and Instagram**
- Use Meta's official APIs only for assets/accounts that JBSN owns or is authorised to manage, and only for API-approved use cases.
- For third-party prospects, the first release may store the public business page/profile URL as a research reference and allow a human researcher to verify published business contact options. Do not scrape login-only content, private messages, hidden data or personal profiles.
- Use the page's public contact button or official business website as the preferred contact route.
- Do not claim that a social profile's administrator is the owner or CEO unless there is explicit public evidence.

**Other public business sources**
- Only integrate a directory or enrichment provider after checking its data provenance, licence, permitted CRM use, refresh policy and POPIA obligations. Do not buy or ingest opaque personal mobile lists.

### Decision-maker contact hierarchy
For each business, attempt to identify the best legitimate route in this order:
1. Publicly published direct business number for the owner/CEO/director.
2. Publicly published work mobile for a named decision-maker.
3. Published marketing / business development / operations department number or email.
4. Official business landline and ask reception for the person responsible for marketing or new business enquiries.
5. Official contact form or official business social channel.

Record the contact as DIRECT only if the source explicitly identifies it as a direct business contact. Otherwise classify as department, reception or general business line. Never guess a mobile number from a name, reverse-engineer private numbers, or label an unverified number as the CEO's.

### Website status classifier
- No website: Google Places website field absent AND no official website found after a reasonable search. Label “no website found”, not “definitely no website”.
- Outdated: a website exists and two or more measurable signals are found, such as broken HTTPS, mobile layout failure, broken pages/forms, severe load/performance issue, obsolete content/contact details, non-functional calls to action or obvious desktop-only layout.
- Modern/acceptable: website loads securely, is usable on mobile, has working contact path and no material defect detected.
- Unknown: insufficient evidence; send to human review.

Do not classify a site as outdated merely because its design is not fashionable. Save the audit findings and URLs.

### Lead scoring (0–100)
Initial configurable scoring model:
- No website: +30.
- Outdated website with at least two documented defects: +25.
- 20+ public reviews: +15; 5–19 reviews: +10.
- Rating 4.0+ : +10 (rating is a signal, not a quality guarantee).
- Verified public business phone: +10.
- Verified decision-maker or department contact: +10.
- Active/open business evidence: +5.
- Duplicate, closed, suppressed or do-not-contact: disqualify regardless of score.

Buckets:
- 80–100: Priority A — human review then dial queue.
- 60–79: Priority B — verify contact and website evidence.
- 40–59: Research required.
- Below 40: hold or reject.

Do not let AI invent missing fields to improve a score. Scores must show a reason breakdown and source evidence.

### Lead ingestion pipeline
1. User chooses geography, category, review threshold and target count.
2. Sourcing job searches the approved source adapters.
3. Normalise business names, phone formats, website domains and addresses.
4. Deduplicate using place ID, domain, phone, name + address and fuzzy matching.
5. Enrich only through permitted sources.
6. Audit website status and capture evidence.
7. Score and categorise the lead.
8. Run suppression and existing-client checks.
9. Put new records in “Needs review”.
10. Human approves or rejects the record.
11. Approved leads enter the dial queue and are assigned to Jabulani or Katleho.

Never send unreviewed AI-sourced records directly to automated outbound calls.

## 6. Dialler and call-log workflow

MVP supports manual calls from an Android/MTN phone and click-to-call where possible. Do not block today's launch on a paid telephony integration.

Dialler queue fields:
- Business, category, location, rating/review count.
- Website status and website audit reason.
- Best contact name and role, if verified.
- Number/email, contact type and source evidence.
- Assigned founder/closer.
- Last contact date and attempt count.
- Do-not-contact / consent / contact restrictions.
- Lead score and priority.
- Next action.

Call outcome options:
- No answer
- Busy
- Wrong number
- Reception answered
- Decision-maker reached
- Asked to call back
- Interested
- Meeting booked
- Not interested
- Already has provider
- Number invalid
- Do not contact / objection
- Follow-up email requested

On every call, record timestamp, caller, number used, contact reached, outcome, notes, next action and follow-up date. A “do not contact” outcome immediately suppresses the relevant contact and, where appropriate, the business from future campaigns.

Use an approved human calling script for the founder-led phase. Keep AI outbound calling disabled until the applicable POPIA/CPA requirements, consent model, disclosures, recording rules and suppression handling have been reviewed. POPIA section 69 specifically addresses unsolicited electronic direct marketing and automatic calling machines; do not assume an AI voice agent may cold-call every scraped public number.

## 7. Calendar and appointments

- Each founder has their own calendar and working hours.
- Calendar booking checks availability and prevents double booking.
- Store timezone explicitly (Africa/Johannesburg).
- Appointment links include business, contact, assigned closer, meeting type and notes.
- Confirmation and reminders must use approved channels and respect contact preferences.
- Appointment statuses: booked, confirmed, attended, no-show, rescheduled, cancelled.
- Provide a company-wide view with privacy controls.
- Later connect Google Calendar using OAuth and least-privilege scopes; do not store calendar passwords.

## 8. Customer zone and client lifecycle

Customer portal:
- Secure invitation and login.
- Business profile and authorised contacts.
- Website URL, staging preview and live status.
- Project milestones and approval requests.
- Retainer plan, billing date, payment status and invoices.
- Support tickets and update requests.
- Support/review calendar.
- Agreed performance reports (traffic, leads, calls, forms) only where analytics are installed and data is reliable.
- Documents, signed scope and service terms.
- Notifications and update history.

Strict tenant isolation: every client-facing query must be scoped to the authenticated client_id. Add automated tests proving Client A cannot view Client B's records, websites, invoices, support tickets or reports.

Client lifecycle:
1. Deal won.
2. Payment verified.
3. Client record created.
4. Portal invitation sent.
5. Human Customer Success owner assigned.
6. Onboarding form and assets collected.
7. Project brief approved.
8. Website delivery and QA.
9. Client approval.
10. Website published.
11. Retainer service begins and monthly tasks are scheduled.
12. Monthly report and support/review appointment.

## 9. Paystack integration

- Create checkout/payment requests server-side.
- Store secret keys only in server environment variables.
- Verify webhook signature using the raw request body and Paystack's documented method.
- Verify transaction status server-side before activating a client.
- Make webhook processing idempotent; duplicate webhooks must not create duplicate payments or clients.
- Store reference, amount, currency, status, event ID and verification timestamp.
- Reconcile Paystack transaction records with the internal ledger.
- Never store card numbers, CVV or full payment credentials.
- Provide test/live mode separation and founder-controlled feature flag.
- Do not enable recurring billing until subscription terms, cancellation and Paystack recurring-payment capabilities are confirmed.

## 10. Founder dashboard and Success companion

Founder dashboard widgets:
- Today's meetings and follow-ups.
- New leads, approved leads and dial queue.
- Calls made, conversations and outcomes.
- Appointments booked / show rate.
- Deals won, setup revenue and new MRR.
- Active clients, onboarding backlog and overdue support.
- Payments received, failed payments and expenses.
- Tasks awaiting founder approval.
- Department and system health.

Success companion (later P2):
- Separate personal experience for each founder.
- Morning/evening briefing, voice and text chat.
- Query authorised CRM data and cite the records used in its answers.
- Proactive alerts only for configured events and quiet hours.
- Draft tasks/messages/reports.
- Ask for approval before sending messages, making calls, issuing refunds, changing subscription status, publishing websites, hiring or changing system settings.
- Optional background music with user-controlled play/pause/volume; no automatic audible playback until the user interacts with the player.

## 11. System Control Centre / feature flags

Founder-only controls:
- Lead sourcing enabled/disabled.
- Each source adapter enabled/disabled.
- Website audit enabled/disabled.
- Manual dialling workflow enabled/disabled.
- AI outbound calling (default OFF).
- Appointment reminders (default OFF until consent/approved channel).
- Paystack checkout (test/live separately).
- Client portal enabled/disabled.
- Client website publishing requires approval / authorised publisher.
- AI Success enabled/disabled.
- AI HR, finance and delivery agents enabled/disabled.
- Staff user activation/suspension.
- Export and bulk actions.
- Usage limits and spend caps.

Every setting change records who changed it, old value, new value, timestamp and reason.

## 12. Security, privacy and compliance

- POPIA-aligned privacy notice, purpose limitation, data minimisation, retention and access controls.
- Keep a suppression list and honour objections promptly.
- Record source and lawful basis/consent status for personal contact details.
- Distinguish business entity information from identifiable natural-person information.
- Review direct marketing rules before automated calling, bulk email or messaging.
- Apply source-specific API terms; do not scrape LinkedIn or restricted Meta content.
- Follow Google Places attribution, storage and caching requirements.
- Encrypt traffic, hash passwords using a modern password-hashing algorithm, protect sessions and use MFA for founders.
- Rate-limit login, password reset and public endpoints.
- Validate and sanitise all inputs.
- Keep secrets in Render environment variables; never commit secrets.
- Back up PostgreSQL and test restore.
- Log security-sensitive activity and provide a process for data access/correction/deletion requests.

## 13. Acceptance tests for today's launch

### Founder / security
- Jabulani and Katleho can log in separately.
- Both see correct founder dashboard and separate calendars.
- A staff test account cannot access founder-only finance or settings.
- All privileged changes appear in the audit log.

### CRM / leads
- Create, edit, assign, search and archive a lead.
- Import a CSV and detect duplicates.
- Store multiple source-evidence records.
- Show website status, review count, phone provenance and contact confidence.
- A suppressed lead cannot enter the dial queue.
- A lead without a verified number is not dial-ready.

### Calling
- Create a call activity with outcome, notes and next action.
- A do-not-contact outcome suppresses future calls.
- Two founders can see their own assigned queue and authorised company totals.

### Calendar
- Book an appointment for either founder.
- Prevent overlapping appointments.
- Store Africa/Johannesburg timezone correctly.

### Payments / client zone
- Test payment can be verified server-side.
- Duplicate webhook does not duplicate a payment or client.
- Failed/unverified payment does not activate a paid client.
- Client A cannot access Client B's data.
- Portal invitation and password reset work.

### Operations
- Feature flags actually disable their server-side feature, not just the UI button.
- Database backup succeeds and restoration procedure is documented.
- No API keys or passwords appear in browser code, logs or Git history.

## 14. Definition of “ready to dial”

The team may start founder-led manual calling once:
- Both founder accounts work.
- Lead records and call logs persist after refresh.
- Each lead has source evidence and an identifiable public business contact channel.
- Duplicate and suppression checks work.
- Call outcomes and next actions work.
- Founder calendars can book meetings.
- A backup exists.
- The human calling process has been checked for legal compliance.

AI sourcing can assist with discovery and enrichment, but all leads must pass evidence, deduplication, suppression and human review before being dialled. AI voice outbound remains disabled until legal and consent controls are approved.

## 15. Claude implementation instructions

Work in small, testable increments. First inspect the existing repository, runtime, database migrations and deployment. Preserve existing working functionality. Do not overwrite the production database or expose secrets.

For each increment:
1. Report files and existing architecture inspected.
2. Propose a minimal migration and implementation plan.
3. Implement one module.
4. Add tests and run them.
5. Check access control and tenant isolation.
6. Summarise changed files, migration steps, environment variables and deployment steps.
7. Wait for founder approval before production deployment, destructive migration, changing payment mode or enabling outbound AI calls.

Start with P0 authentication, CRM schema, lead management, source evidence, suppression, call logging and founder dashboards. Then implement P1 payments and customer portal. Do not claim completion until acceptance tests pass in the deployed environment.
