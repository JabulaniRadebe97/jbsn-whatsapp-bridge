# ElevenLabs outbound voice integration

This integration lets the authenticated JBSN AI OS API request a real outbound call
through ElevenLabs' Twilio-linked phone-number integration. It does not provide a
phone number, telecom credit, or ElevenLabs account credits.

## Required provider setup

1. Create/configure an ElevenLabs Conversational AI agent.
2. Link an outbound-capable Twilio phone number to that agent in ElevenLabs.
3. Store the API key and IDs only in Render environment variables (never in GitHub,
   dashboard HTML, request bodies, or chat):
   - `ELEVENLABS_API_KEY`
   - `ELEVENLABS_AGENT_ID`
   - `ELEVENLABS_AGENT_PHONE_NUMBER_ID`
4. Keep `JBSN_ELEVENLABS_VOICE_ENABLED=false` and
   `JBSN_ELEVENLABS_CAMPAIGN_APPROVED=false` until provider billing, destination
   support, caller ID, consent records, opt-out handling, and applicable law have
   been reviewed.
5. For a manually launched, approved single call only, set both flags to true.
   The endpoint is protected by the existing JBSN bearer-token authentication.

## Endpoint

`POST /v1/voice/elevenlabs-calls`

Example body (use only a prospect with documented permission to receive this call):

```json
{
  "campaign_approved": true,
  "prospect": {
    "phone": "+27123456789",
    "contact_permission": true,
    "permission_source": "documented opt-in record ID",
    "do_not_call": false,
    "opted_out": false
  }
}
```

The phone number above is a format example, not a real prospect. The adapter rejects
calls unless all gates pass and sends `call_recording_enabled: false` by default.
One API request initiates at most one call; no bulk dialer or automatic retry loop is
provided.

## Cost and deployment limits

- ElevenLabs usage and the linked carrier's phone number/minutes are billed separately
  according to each account's plan and destination rates.
- A successful HTTP response means the provider accepted the call request; it does not
  guarantee the recipient answered or that the conversation completed.
- Do not enable live calling until the account has a linked outbound-capable number and
  sufficient billing/credits. Do not test on real prospects without documented consent.
- The current integration calls ElevenLabs' documented
  `POST /v1/convai/twilio/outbound-call` endpoint.

## Trial-number fallback (no ElevenLabs phone-number import)

The optional register-call route lets JBSN AIOS create the Twilio call directly and pass ElevenLabs-returned TwiML to Twilio. It avoids the ElevenLabs phone-number import step, but **does not bypass Twilio trial restrictions**, destination verification, regional calling permissions, or billing.

Required Render environment variables:
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_AGENT_ID`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER` (E.164, e.g. `+17372508034`)
- `JBSN_ELEVENLABS_TWILIO_FALLBACK_ENABLED=false` (keep false until configured and verified)
- `JBSN_ELEVENLABS_CAMPAIGN_APPROVED=false` (keep false until a founder-approved, consented pilot)

Authenticated endpoint: `POST /v1/voice/elevenlabs-twilio-fallback-calls`. Request body matches the existing voice endpoint and requires `campaign_approved: true` plus a prospect object containing E.164 `phone`, `contact_permission: true`, a non-empty `permission_source`, and no opt-out/do-not-call flags.

No calls are initiated by deployment or health checks. Do not enable the flags until credentials, destination verification, lawful calling basis, opt-out controls, and a manually approved test recipient have been verified. Twilio and ElevenLabs usage may incur charges.
