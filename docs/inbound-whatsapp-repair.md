# JBSN WhatsApp inbound repair checklist

This is the operational repair plan for the current Netlify → Google Apps Script → WhatsApp Cloud API path. It intentionally does not bypass Meta webhook signature validation or change the working outbound sender.

## What the live function requires

Netlify function `netlify/functions/whatsapp-webhook.js` reads these runtime environment variables:

- `META_WEBHOOK_VERIFY_TOKEN`: GET subscription verification only.
- `META_APP_SECRET`: validates Meta's `X-Hub-Signature-256` on POST.
- `JBSN_APPS_SCRIPT_URL`: deployed Google Apps Script web-app URL that accepts POST and returns JSON `{ "ok": true, "reply": "..." }`.
- `WHATSAPP_ACCESS_TOKEN`: WhatsApp Cloud API token with permission to send messages.
- `WHATSAPP_PHONE_NUMBER_ID`: numeric WhatsApp Cloud API Phone Number ID.
- `WA_OUTBOUND_API_KEY`: protects the separate outbound endpoint.

Do not share any secret values in chat, screenshots, logs, or a public issue.

## Repair order

1. Restore a production deploy for Netlify site `jbsn-creative-wa-bridge-926`. Until the deploy is published, GitHub commits do not change the running function.
2. In Netlify's runtime environment, verify that the five required inbound variables above exist in the production context. Verify the Apps Script URL is the deployed web-app URL, not the script editor URL.
3. Confirm the Meta app's App Secret matches `META_APP_SECRET`; do not remove signature validation to make tests pass.
4. Confirm the Google Apps Script web app is deployed to execute as its owner and is accessible to the bridge. Its `doPost` must return JSON with `ok:true` and a non-empty `reply`.
5. Confirm the Meta app is in the appropriate Live mode and the WhatsApp Business Account's `messages` webhook subscription is active for the actual business number.
6. Send one new inbound text and inspect Netlify function logs for the stage that fails. A successful outbound API call or HTTP 200 webhook acknowledgement alone is not a delivery receipt; confirm a WhatsApp delivery status.

## Important finding in the saved Apps Script source

The UCX reply generator has a fallback response when no AI provider key is configured. Therefore, missing Gemini/Claude credentials would reduce reply quality but should not by itself prevent a reply from being returned. The transport path and runtime configuration must be validated first.

## Current limitation

Recent production deploys were reported as skipped because the Netlify team's credit limit was reached. Until Netlify permits a production deploy again, a source-code change in this repository cannot repair the currently running function. No live repair should be claimed until a real inbound message receives a reply.
