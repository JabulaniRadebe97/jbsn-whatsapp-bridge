# JBSN Creative — Lead Sourcing, Verification & Allocation Rules

This document supplements `JBSN_CREATIVE_FOUNDER_CRM_BUILD_SPEC.md`.

## 1. What qualifies as a sales-ready lead

A business is not sales-ready merely because an AI found a name and phone number. It must have:
- A valid, identifiable business record.
- A source URL or source record ID for every important field.
- Evidence of a review footprint meeting the configured minimum.
- Website status of `no_website_found` or `outdated`, with the reason recorded.
- At least one valid, publicly published business contact route.
- No duplicate, active customer, active opportunity, closed-business flag or suppression match.
- Human approval before it enters the dial queue.

## 2. Required source and field provenance

For every sourced field, save:
- source provider
- source URL / place ID / record ID
- observed value
- observation timestamp
- confidence score
- verification method
- attribution / licence restrictions
- human reviewer and decision (where reviewed)

Do not combine fields from unrelated people or businesses because names are similar. A decision-maker's name, title and phone must be linked by evidence to the same business and the same person.

### Contact confidence
- 95–100: direct business contact explicitly published by the business or verified from an official business source.
- 80–94: published company department contact or named business role with clear official evidence.
- 60–79: general company phone or contact form; valid route but not a direct decision-maker contact.
- 40–59: third-party directory or conflicting evidence; needs human verification.
- 0–39: unsupported, stale, guessed or conflicting; do not dial.

A phone number can be marked `verified` only after a human or approved verification service confirms it belongs to the business. A successful connection does not prove that the person is the CEO.

## 3. AI research workflow

For each candidate:
1. Search approved business source adapters for the requested category and geography.
2. Match the business identity and deduplicate.
3. Collect permitted business details and review-count/rating signals.
4. Check whether an official website is listed.
5. If a website exists, audit only publicly accessible pages for secure loading, mobile layout, working contact path, broken links/forms and clear evidence of outdated information.
6. Search official company pages for public owner/director/marketing/operations contact routes.
7. Store evidence URL and observed date per field.
8. Label contact type precisely: direct published business line, named work contact, department, reception, general line, contact form or social page.
9. Calculate lead score and contact confidence separately.
10. Run duplicate, client, opportunity and suppression checks.
11. Create a lead in `needs_review`, never directly in the dial queue.
12. Present a review card showing evidence, uncertain fields and why the lead qualifies.

The AI must say `not found` rather than infer missing information. Do not fabricate CEO names, direct numbers, emails, websites, review counts or ratings.

## 4. Assignment policy

Founder accounts:
- Jabulani
- Katleho

Default assignment method: balanced round-robin among active founders, considering open assigned leads and scheduled sales meetings.

Routing rules:
1. If a founder manually selects an owner, preserve that assignment.
2. If the business is in a configured exclusive territory or sector, route to its configured owner.
3. Otherwise assign to the founder with fewer open priority leads; use round-robin as the tie-breaker.
4. Do not assign a lead to a founder whose account is inactive.
5. Rebalance only uncontacted, unworked leads. Never silently reassign a lead after a founder has logged a call or meeting.
6. Founders can transfer a lead with a required reason.
7. Record assignment events in the activity log with previous owner, new owner, rule, timestamp and actor.
8. A lead can be assigned to a closer later without losing the original source and founder ownership history.

## 5. Automatic activity logs

The system should automatically log:
- source search job created/completed/failed
- provider and query parameters used
- business discovered
- duplicate matched / merged / rejected
- website audit completed and evidence
- contact field added/updated and source
- confidence score changed and why
- lead score changed and why
- human review approved/rejected and reviewer
- lead assigned/reassigned and routing rule
- call started/completed and call outcome (only from an authorised dialler integration; manual call outcomes are user-entered)
- follow-up created/completed
- appointment booked/rescheduled/cancelled
- do-not-contact or objection received
- export performed
- any source/API rate-limit or policy error

Never invent a call event. An AI research agent must not log a call unless a real call event exists from the dialler provider or an authorised user entered it.

## 6. Lead review card

Display:
- Business name, category and location.
- Rating and review count, source and observation time.
- Website status plus audit findings and evidence.
- Main business phone and contact route type.
- Decision-maker name/title only if evidenced.
- Contact confidence and evidence link.
- Lead score with reason breakdown.
- Duplicate/suppression/client check.
- Assigned founder and assignment reason.
- Approve, reject, request more research, correct field and suppress actions.

## 7. Daily sourcing batch

Founder chooses:
- Province / towns / radius.
- Business categories.
- Minimum review count.
- Website target: no website, outdated, or both.
- Minimum lead score.
- Maximum records to research.
- Assignment mode.
- Source adapters permitted for this batch.

Batch summary:
- businesses discovered
- duplicates excluded
- no website
- outdated website
- review threshold passed
- verified business contact routes
- named decision-maker contacts found
- needs human review
- rejected / suppressed
- API errors and estimated provider cost

Do not promise a fixed number of decision-maker mobile numbers. Public business data may only provide a general line or official contact route.

## 8. Outbound eligibility gates

A lead can enter the manual founder dial queue only when:
- Human reviewer approves it.
- The business identity and number are sufficiently verified.
- Source provenance is present.
- Suppression and duplicate checks pass.
- The contact route is appropriate for the intended call.
- Applicable direct-marketing rules and internal policy allow the call.

AI voice outbound is a separate feature flag, OFF by default. It requires legal review, a documented lawful contact/consent basis, appropriate disclosure, recording controls where relevant, opt-out handling, rate limits and a tested suppression mechanism before activation.
