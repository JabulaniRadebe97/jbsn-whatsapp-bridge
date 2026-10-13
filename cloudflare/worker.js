const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

function constantTimeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function bytesToHex(bytes) {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifySignature(rawBody, signature, appSecret) {
  if (!appSecret || !signature || !signature.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(appSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, rawBody);
  return constantTimeEqual("sha256=" + bytesToHex(digest), signature);
}

async function sendWhatsAppPayload(env, payload) {
  if (!env.WHATSAPP_ACCESS_TOKEN || !env.WHATSAPP_PHONE_NUMBER_ID) {
    throw new Error("WhatsApp Cloud API credentials are not configured.");
  }
  const version = env.META_GRAPH_VERSION || "v23.0";
  const response = await fetch(
    `https://graph.facebook.com/${version}/${encodeURIComponent(env.WHATSAPP_PHONE_NUMBER_ID)}/messages`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.WHATSAPP_ACCESS_TOKEN}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ messaging_product: "whatsapp", recipient_type: "individual", ...payload }),
    },
  );
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    console.error("WhatsApp API rejected send", { status: response.status, code: result?.error?.code });
    throw new Error(`WhatsApp send failed with HTTP ${response.status}`);
  }
  return result;
}

async function sendWhatsAppText(env, to, text) {
  return sendWhatsAppPayload(env, {
    to,
    type: "text",
    text: { preview_url: false, body: String(text).slice(0, 4000) },
  });
}

async function handleOutbound(request, env) {
  const configuredKey = env.WA_OUTBOUND_API_KEY || "";
  const suppliedKey = request.headers.get("x-jbsn-outbound-key") || "";
  if (!constantTimeEqual(configuredKey, suppliedKey) || !configuredKey) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  let data;
  try { data = await request.json(); }
  catch { return json({ ok: false, error: "Invalid JSON" }, 400); }

  const to = String(data.to || "").replace(/[^0-9]/g, "");
  if (!/^\d{8,15}$/.test(to)) {
    return json({ ok: false, error: "to must be a WhatsApp number in international digits-only format" }, 400);
  }

  try {
    let result;
    if (data.type === "template") {
      if (!data.templateName || !data.language) {
        return json({ ok: false, error: "templateName and language are required for template messages" }, 400);
      }
      result = await sendWhatsAppPayload(env, {
        to,
        type: "template",
        template: {
          name: String(data.templateName).slice(0, 200),
          language: { code: String(data.language).slice(0, 20) },
          ...(Array.isArray(data.components) ? { components: data.components } : {}),
        },
      });
    } else if (data.type === "text") {
      if (data.customerInitiatedWithin24Hours !== true) {
        return json({ ok: false, error: "Free-form text requires confirmation that the customer initiated contact within the last 24 hours. Otherwise use an approved template." }, 400);
      }
      if (!data.text || !String(data.text).trim()) return json({ ok: false, error: "text is required" }, 400);
      result = await sendWhatsAppText(env, to, String(data.text).trim());
    } else {
      return json({ ok: false, error: "type must be text or template" }, 400);
    }
    return json({ ok: true, messages: result.messages || [], result });
  } catch (error) {
    console.error("Outbound WhatsApp send failed", error.message);
    return json({ ok: false, error: error.message }, 502);
  }
}

async function handleMessage(env, message, contact) {
  if (!message || message.type !== "text" || !message.from || !message.text?.body) return;

  if (!env.JBSN_APPS_SCRIPT_URL) throw new Error("JBSN_APPS_SCRIPT_URL is not configured.");
  const phone = String(message.from);
  const customerName = contact?.profile?.name || "";
  const response = await fetch(env.JBSN_APPS_SCRIPT_URL, {
    method: "POST",
    headers: { "content-type": "text/plain;charset=utf-8" },
    body: JSON.stringify({
      sessionId: "WA-" + phone,
      message: String(message.text.body).slice(0, 6000),
      name: customerName,
      phone,
      channel: "WHATSAPP",
    }),
    redirect: "follow",
  });

  const responseText = await response.text();
  let result;
  try { result = JSON.parse(responseText); }
  catch { throw new Error("Apps Script returned a non-JSON response."); }

  if (!response.ok || result?.ok !== true || !result?.reply) {
    console.error("Apps Script reply failure", { status: response.status, ok: result?.ok === true, hasReply: Boolean(result?.reply) });
    throw new Error("Apps Script did not return a usable reply.");
  }
  await sendWhatsAppText(env, phone, result.reply);
}

function getQueryValue(url, dottedName) {
  const direct = url.searchParams.get(dottedName);
  if (direct !== null) return direct;
  const hubName = dottedName.replace(/^hub\./, "");
  return url.searchParams.get("hub." + hubName);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "GET") {
      const mode = url.searchParams.get("hub.mode");
      const suppliedToken = (url.searchParams.get("hub.verify_token") || "").trim();
      const challenge = url.searchParams.get("hub.challenge");
      const expectedToken = (env.META_WEBHOOK_VERIFY_TOKEN || "").trim();

      if (!expectedToken) return new Response("Webhook verify token is not configured", { status: 500 });
      if (mode === "subscribe" && challenge && constantTimeEqual(suppliedToken, expectedToken)) {
        return new Response(challenge, { status: 200, headers: { "content-type": "text/plain; charset=utf-8" } });
      }
      return new Response("Webhook verification failed", { status: 403 });
    }

    if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });

    // Preserve the existing authenticated outbound API path.
    if (request.headers.has("x-jbsn-outbound-key")) return handleOutbound(request, env);

    const rawBody = await request.arrayBuffer();
    const signature = request.headers.get("x-hub-signature-256") || "";
    if (!(await verifySignature(rawBody, signature, env.META_APP_SECRET))) {
      console.warn("Rejected webhook: missing/invalid signature or META_APP_SECRET.");
      return new Response("Invalid signature", { status: 401 });
    }

    let payload;
    try { payload = JSON.parse(new TextDecoder().decode(rawBody)); }
    catch { return json({ ok: false, error: "Invalid JSON" }, 400); }
    if (payload.object !== "whatsapp_business_account") return json({ ok: true, ignored: true });

    try {
      for (const entry of payload.entry || []) {
        for (const change of entry.changes || []) {
          if (!change.value || change.field !== "messages") continue;
          const contacts = change.value.contacts || [];
          for (const message of change.value.messages || []) {
            const contact = contacts.find((item) => item.wa_id === message.from) || null;
            await handleMessage(env, message, contact);
          }
        }
      }
      return json({ ok: true });
    } catch (error) {
      console.error("WhatsApp webhook processing failed", error.message);
      return json({ ok: false, error: "Webhook processing failed" }, 500);
    }
  },
};
