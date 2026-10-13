const crypto = require("crypto");

const json = (statusCode, body) => ({
  statusCode,
  headers: { "content-type": "application/json; charset=utf-8" },
  body: JSON.stringify(body)
});

function verifySignature(rawBody, signature, appSecret) {
  if (!appSecret || !signature || !rawBody) return false;
  const expected = "sha256=" + crypto.createHmac("sha256", appSecret).update(rawBody).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

async function sendWhatsAppPayload(payload) {
  const token = process.env.WHATSAPP_ACCESS_TOKEN;
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const version = process.env.META_GRAPH_VERSION || "v23.0";
  if (!token || !phoneNumberId) throw new Error("WhatsApp Cloud API credentials are not configured.");

  const response = await fetch(`https://graph.facebook.com/${version}/${encodeURIComponent(phoneNumberId)}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ messaging_product: "whatsapp", recipient_type: "individual", ...payload })
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`WhatsApp send failed (${response.status}): ${JSON.stringify(result).slice(0, 500)}`);
  return result;
}

async function sendWhatsAppText(to, text) {
  return sendWhatsAppPayload({
    to, type: "text",
    text: { preview_url: false, body: String(text).slice(0, 4000) }
  });
}

async function handleOutbound(event) {
  const configuredKey = process.env.WA_OUTBOUND_API_KEY;
  const headers = event.headers || {};
  const suppliedKey = headers["x-jbsn-outbound-key"] || headers["X-JBSN-OUTBOUND-KEY"];
  if (!configuredKey || !suppliedKey || suppliedKey.length !== configuredKey.length ||
      !crypto.timingSafeEqual(Buffer.from(suppliedKey), Buffer.from(configuredKey))) {
    return json(401, { ok: false, error: "Unauthorized" });
  }
  let data;
  try { data = JSON.parse(event.body || "{}"); }
  catch (_) { return json(400, { ok: false, error: "Invalid JSON" }); }
  const to = String(data.to || "").replace(/[^0-9]/g, "");
  if (!/^\d{8,15}$/.test(to)) return json(400, { ok: false, error: "to must be a WhatsApp number in international digits-only format" });

  try {
    let result;
    if (data.type === "template") {
      if (!data.templateName || !data.language) {
        return json(400, { ok: false, error: "templateName and language are required for template messages" });
      }
      result = await sendWhatsAppPayload({
        to, type: "template",
        template: {
          name: String(data.templateName).slice(0, 200),
          language: { code: String(data.language).slice(0, 20) },
          ...(Array.isArray(data.components) ? { components: data.components } : {})
        }
      });
    } else if (data.type === "text") {
      if (data.customerInitiatedWithin24Hours !== true) {
        return json(400, { ok: false, error: "Free-form text requires confirmation that the customer initiated contact within the last 24 hours. Otherwise use an approved template." });
      }
      if (!data.text || !String(data.text).trim()) return json(400, { ok: false, error: "text is required" });
      result = await sendWhatsAppText(to, String(data.text).trim());
    } else {
      return json(400, { ok: false, error: "type must be text or template" });
    }
    return json(200, { ok: true, messages: result.messages || [], result });
  } catch (error) {
    console.error("Outbound WhatsApp send failed:", error.message);
    return json(502, { ok: false, error: error.message });
  }
}

async function handleMessage(message, contact) {
  if (!message || message.type !== "text" || !message.from || !message.text || !message.text.body) return;
  const gasUrl = process.env.JBSN_APPS_SCRIPT_URL;
  if (!gasUrl) throw new Error("JBSN_APPS_SCRIPT_URL is not configured.");
  console.info("WA inbound: text accepted; forwarding to Apps Script.");

  const customerName = (contact && contact.profile && contact.profile.name) || "";
  const phone = String(message.from);
  const gasResponse = await fetch(gasUrl, {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=utf-8" },
    body: JSON.stringify({
      sessionId: "WA-" + phone,
      message: String(message.text.body).slice(0, 6000),
      name: customerName,
      phone,
      channel: "WHATSAPP"
    }),
    redirect: "follow"
  });

  const gasText = await gasResponse.text();
  console.info("WA inbound: Apps Script responded with HTTP", gasResponse.status, "body length", gasText.length);
  let result;
  try { result = JSON.parse(gasText); } catch (_) { throw new Error("Apps Script returned a non-JSON response."); }
  if (!gasResponse.ok || !result || result.ok !== true || !result.reply) {
    throw new Error("Apps Script did not return an AI reply: " + gasText.slice(0, 500));
  }
  console.info("WA inbound: Apps Script returned a reply; sending through WhatsApp Cloud API.");
  const sendResult = await sendWhatsAppText(phone, result.reply);
  console.info("WA inbound: WhatsApp API accepted reply; message id present:", Boolean(sendResult.messages && sendResult.messages[0] && sendResult.messages[0].id));
}

exports.handler = async (event) => {
  const verifyToken = (process.env.META_WEBHOOK_VERIFY_TOKEN || "").trim();

  if (event.httpMethod === "GET") {
    let p = event.queryStringParameters || {};
    try {
      if (event.rawUrl) {
        const urlParams = new URL(event.rawUrl).searchParams;
        p = {
          ...p,
          "hub.mode": urlParams.get("hub.mode") ?? p["hub.mode"],
          "hub.verify_token": urlParams.get("hub.verify_token") ?? p["hub.verify_token"],
          "hub.challenge": urlParams.get("hub.challenge") ?? p["hub.challenge"]
        };
      }
    } catch (_) {}

    if (!verifyToken) {
      console.error("META_WEBHOOK_VERIFY_TOKEN is missing in the active deployment context.");
      return { statusCode: 500, body: "Webhook verify token is not configured in this deployment" };
    }
    const suppliedToken = typeof p["hub.verify_token"] === "string" ? p["hub.verify_token"].trim() : "";
    if (p["hub.mode"] === "subscribe" && suppliedToken === verifyToken && p["hub.challenge"]) {
      return { statusCode: 200, headers: { "content-type": "text/plain; charset=utf-8" }, body: p["hub.challenge"] };
    }
    return { statusCode: 403, body: "Webhook verification failed" };
  }

  if (event.httpMethod !== "POST") return { statusCode: 405, body: "Method not allowed" };

  // Authenticated outbound API requests are separate from Meta's signed webhook requests.
  const requestHeaders = event.headers || {};
  if (requestHeaders["x-jbsn-outbound-key"] || requestHeaders["X-JBSN-OUTBOUND-KEY"]) {
    return handleOutbound(event);
  }

  const rawBody = event.isBase64Encoded
    ? Buffer.from(event.body || "", "base64")
    : Buffer.from(event.body || "", "utf8");
  const signature = requestHeaders["x-hub-signature-256"] || requestHeaders["X-Hub-Signature-256"];
  if (!verifySignature(rawBody, signature, process.env.META_APP_SECRET)) {
    console.warn("Rejected webhook: missing/invalid signature or META_APP_SECRET.");
    return { statusCode: 401, body: "Invalid signature" };
  }

  let payload;
  try { payload = JSON.parse(rawBody.toString("utf8")); }
  catch (_) { return json(400, { ok: false, error: "Invalid JSON" }); }
  if (payload.object !== "whatsapp_business_account") return json(404, { ok: false, ignored: true });
  console.info("WA webhook: signature valid; entries:", (payload.entry || []).length);

  try {
    for (const entry of payload.entry || []) {
      for (const change of entry.changes || []) {
        if (!change.value || change.field !== "messages") continue;
        const contacts = change.value.contacts || [];
        for (const message of change.value.messages || []) {
          const contact = contacts.find(c => c.wa_id === message.from) || null;
          await handleMessage(message, contact);
        }
      }
    }
    return json(200, { ok: true });
  } catch (error) {
    console.error("WhatsApp webhook processing failed:", error && error.stack ? error.stack : String(error));
    return json(500, { ok: false, error: "Webhook processing failed" });
  }
};
