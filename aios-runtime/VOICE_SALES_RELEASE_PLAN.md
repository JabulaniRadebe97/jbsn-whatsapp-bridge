# JBSN AI OS Voice Sales — release plan

## Tier 1 outcome

Build an AI SDR/closer that can qualify prospects, explain JBSN Creative offers, handle common objections, book meetings or request a human handoff, and record CRM outcomes. The voice should sound natural, but the agent must identify itself as an AI assistant at the start of each call.

## What this change adds

- A provider adapter foundation for Twilio outbound calls.
- Fail-closed controls: feature flag off by default, campaign approval, documented permission source, E.164 validation, and do-not-call/opt-out rejection.
- An opening TwiML prompt with AI disclosure and an opt-out phrase.
- No API route is exposed by this module alone; call creation must be wired to authenticated runtime routes and Twilio webhook signature validation before use.

## Required production sequence

1. Connect Twilio account, verified caller ID, public callback URL, and approved calling regions.
2. Implement authenticated founder-only campaign launch, prospect permission records, suppression list, campaign caps, retry windows, and audit events.
3. Add signed Twilio webhook validation for call instructions, speech turns, and status callbacks.
4. Connect the voice conversation to a supported language model and speech provider; use bounded turn latency, interruption handling, fallback/handoff, and redacted logs.
5. Test with internal numbers only; then enable a small approved pilot after compliance review.
6. Add CRM disposition, follow-up tasks, call recordings only when lawful and disclosed, and conversion metrics.

## Do not enable by default

Do not set `JBSN_VOICE_ENABLED=true` until webhook routes and signature validation are deployed and tested. Do not make unsolicited or automated marketing calls without confirming lawful basis, consent/permission, do-not-call requirements, calling-hour rules, and recording notices for the target market. Never let the agent invent pricing, guarantees, contractual terms, or close a binding agreement outside the approved offer and authority.

## Current limitations

This is not yet a production voice agent and does not deliver a human-like realtime conversation by itself. It is the outbound telephony foundation; authenticated route integration, signed webhooks, the live dialogue engine, CRM writes, and end-to-end tests remain release gates. OpenAI API quota was previously exhausted, so the voice design must not assume OpenAI usage is currently available or free.
