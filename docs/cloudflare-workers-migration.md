# Cloudflare Workers migration for JBSN WhatsApp

This Worker replaces only the Netlify webhook endpoint. It preserves the existing Google Apps Script reply engine and the authenticated outbound API route.

## Deploy from the Cloudflare dashboard

1. In Cloudflare, open **Workers & Pages** and create a Worker.
2. Name it `jbsn-creative-whatsapp-bridge`.
3. Open **Edit code** and replace the starter code with the complete contents of `cloudflare/worker.js` from this repository.
4. Deploy the Worker.
5. In the Worker settings, add these as **Secrets** (not plain-text variables):
   - `META_WEBHOOK_VERIFY_TOKEN` — same verify token configured for the existing Meta webhook.
   - `META_APP_SECRET` — App Secret from Meta app settings; do not share it in chat.
   - `WHATSAPP_ACCESS_TOKEN` — existing WhatsApp Cloud API access token.
   - `WA_OUTBOUND_API_KEY` — existing key used by the JBSN outbound sender.
6. Add these as Worker variables (or secrets if preferred):
   - `WHATSAPP_PHONE_NUMBER_ID` — existing WhatsApp Phone Number ID.
   - `JBSN_APPS_SCRIPT_URL` — deployed Google Apps Script web-app URL.
   - `META_GRAPH_VERSION` — optional; if omitted, defaults to `v23.0`.
7. Save settings and deploy again if the dashboard asks you to.
8. Copy the Worker URL. It should resemble `https://jbsn-creative-whatsapp-bridge.<your-subdomain>.workers.dev`.
9. In Meta Developer dashboard, update the webhook callback URL to that Worker URL. Use the exact existing verify token, verify, and ensure the WhatsApp `messages` webhook field remains subscribed.
10. Test by sending a new WhatsApp message to the business number and inspect the Worker logs.

## Important safety and testing notes

- Do not paste tokens, App Secret, API keys, or the full Apps Script URL into chat or commit them to GitHub.
- Keep Meta's `X-Hub-Signature-256` verification enabled; this Worker rejects unsigned/invalid webhook POSTs.
- Keep the existing Netlify URL until Cloudflare's GET verification succeeds and a real inbound reply has been confirmed. Then update any outbound integration that calls the old Netlify endpoint, because the Worker also preserves the authenticated outbound API route.
- This is a deployment alternative, not proof that the live WhatsApp integration works. Confirm with a real message after deployment.
- If the Apps Script endpoint is not deployed or does not return JSON with `{ "ok": true, "reply": "..." }`, inbound replies will still fail.
