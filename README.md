# JBSN WhatsApp Bridge

Separate Netlify Function for the JBSN Creative WhatsApp Cloud API webhook. It does not replace the JBSN Creative website or its checkout.

## Files
- `netlify/functions/whatsapp-webhook.js`: Meta GET verification, POST signature validation, forwards inbound text to the existing Apps Script CX endpoint, then sends the generated reply through WhatsApp Cloud API.
- `netlify.toml`: configures the functions directory.

## Deploy as a separate Netlify site
Connect this repository to a **new, separate Netlify site**. Do not link it to the existing `jbsncreative` site.

After deployment, the webhook URL is:
`https://YOUR-NEW-SITE.netlify.app/.netlify/functions/whatsapp-webhook`

## Required Netlify environment variables
Set these in the new site's environment variable settings. Never commit secrets to GitHub.

- `META_WEBHOOK_VERIFY_TOKEN`: a long random string you create and also enter in Meta Webhooks.
- `META_APP_SECRET`: App Secret from Meta app settings (not the App ID).
- `WHATSAPP_ACCESS_TOKEN`: a valid WhatsApp Cloud API access token with permission to send messages.
- `WHATSAPP_PHONE_NUMBER_ID`: the Cloud API Phone Number ID (not the displayed phone number).
- `JBSN_APPS_SCRIPT_URL`: the existing deployed JBSN Unified Client Experience Apps Script `/exec` URL.
- Optional `META_GRAPH_VERSION`: Graph API version, defaults to `v23.0`; use a currently supported version for your Meta app.

## Meta configuration
In Meta for Developers → Webhooks, choose object **WhatsApp Business Account**, set the callback URL above and the same verify token, then subscribe to the `messages` field.

The function validates `X-Hub-Signature-256` using `META_APP_SECRET`. Test GET verification after deployment, then test with an approved/test recipient. The WhatsApp phone number must be onboarded to Cloud API; an ordinary WhatsApp Business app number is not automatically API-ready.

## Current scope / safety
- Text inbound messages only; media and interactive messages are ignored.
- Apps Script currently generates and logs an AI reply; this bridge sends that reply to the sender.
- Delivery and retries are not yet idempotent; add durable message-ID deduplication before high-volume production.
- Do not deploy this repository over the existing JBSN Creative website.
