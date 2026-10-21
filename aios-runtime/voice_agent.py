"""JBSN AI OS outbound voice foundation.

Outbound calls are disabled unless explicitly enabled and approved. This module
never places calls to records lacking documented permission and campaign approval.
It is a foundation for the Twilio voice adapter; HTTP routes are wired separately.
"""
import base64
import os
import re
import urllib.parse
import urllib.request
import urllib.error
import json


E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def voice_enabled():
    return os.environ.get("JBSN_VOICE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def validate_call_request(prospect, campaign_approved=False):
    """Fail closed before any billable external telephony request."""
    if not voice_enabled():
        raise PermissionError("Outbound voice is disabled")
    if not campaign_approved or os.environ.get("JBSN_VOICE_CAMPAIGN_APPROVED", "false").lower() not in ("1", "true", "yes", "on"):
        raise PermissionError("Founder-approved voice campaign required")
    if not isinstance(prospect, dict):
        raise ValueError("prospect must be an object")
    phone = str(prospect.get("phone", "")).strip()
    if not E164_RE.fullmatch(phone):
        raise ValueError("prospect.phone must be E.164 format")
    if prospect.get("do_not_call") is True or prospect.get("opted_out") is True:
        raise PermissionError("Prospect is opted out or on the do-not-call list")
    if prospect.get("contact_permission") is not True:
        raise PermissionError("Documented permission to call is required")
    if not str(prospect.get("permission_source", "")).strip():
        raise PermissionError("permission_source is required for audit")
    return phone


def build_disclosure_twiml(company_name="JBSN Creative"):
    """Return safe opening TwiML; voice is transparently identified as AI."""
    company = _xml_text(company_name)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response><Say voice="Polly.Joanna-Neural" language="en-US">'
        f'Hello, this is an AI voice assistant calling on behalf of {company}. '
        'Is now a good time for a brief conversation? '
        'You can say stop at any time to end this call.</Say>'
        '<Gather input="speech" action="/voice/turn" method="POST" '
        'speechTimeout="auto" timeout="5">'
        '<Say voice="Polly.Joanna-Neural" language="en-US">Please tell me how I can help.</Say>'
        '</Gather><Hangup/></Response>'
    )


def _xml_text(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def create_outbound_call(prospect, campaign_approved=False):
    """Create a Twilio call only after fail-closed permission and campaign checks."""
    phone = validate_call_request(prospect, campaign_approved=campaign_approved)
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    caller_id = os.environ.get("TWILIO_CALLER_ID", "").strip()
    public_base = os.environ.get("JBSN_PUBLIC_BASE_URL", "").rstrip("/")
    if not all((sid, token, caller_id, public_base)):
        raise RuntimeError("Twilio credentials, caller ID, and public callback URL must be configured")
    if not E164_RE.fullmatch(caller_id):
        raise RuntimeError("TWILIO_CALLER_ID must be E.164 format")
    callback = public_base + "/voice/twiml"
    form = urllib.parse.urlencode({
        "To": phone,
        "From": caller_id,
        "Url": callback,
        "Method": "POST",
        "StatusCallback": public_base + "/voice/status",
        "StatusCallbackMethod": "POST",
        "Timeout": "25",
    }).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
        data=form,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Twilio call creation failed with HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Twilio call creation network error") from None
    return {"provider": "twilio", "call_sid": payload.get("sid"),
            "status": payload.get("status", "unknown"),
            "to": phone, "mode": "outbound_voice"}


import hashlib
import hmac


def validate_twilio_signature(request_url, form_fields, signature):
    """Validate Twilio's X-Twilio-Signature header using the account auth token."""
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not token or not signature or not request_url:
        return False
    material = request_url + "".join(
        str(key) + str(form_fields[key]) for key in sorted(form_fields)
    )
    digest = hmac.new(token.encode("utf-8"), material.encode("utf-8"),
                      hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def build_turn_twiml(speech_result, public_base_url):
    """Generate a bounded response for the next speech turn; stop requests end the call."""
    speech = str(speech_result or "").strip()
    normalized = speech.lower().strip(" .,!?")
    stop_phrases = ("stop", "unsubscribe", "do not call", "don't call",
                    "dont call", "remove me", "end call", "stop calling")
    if any(phrase in normalized for phrase in stop_phrases):
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Say voice="Polly.Joanna-Neural">Understood. I will end this call. Goodbye.</Say>'
                '<Hangup/></Response>')
    if not speech:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Say voice="Polly.Joanna-Neural">Sorry, I did not catch that. '
                'I will arrange for a team member to follow up. Goodbye.</Say><Hangup/></Response>')
    reply = generate_sales_reply(speech)
    action = _xml_text(str(public_base_url).rstrip("/") + "/voice/turn")
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Gather input="speech" action="' + action + '" method="POST" '
            'speechTimeout="auto" timeout="6">'
            '<Say voice="Polly.Joanna-Neural" language="en-US">' + _xml_text(reply) + '</Say>'
            '</Gather><Say voice="Polly.Joanna-Neural">I will arrange a follow-up from our team. Goodbye.</Say>'
            '<Hangup/></Response>')


def generate_sales_reply(prospect_speech):
    """Use Gemini for a constrained voice turn, with a safe human-handoff fallback."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Thanks for sharing that. I do not want to give you inaccurate information. I can arrange for a JBSN Creative team member to follow up with you."
    prompt = (
        "You are the disclosed AI voice assistant for JBSN Creative, which offers website, "
        "digital marketing, and AI implementation services. Speak in one or two short natural "
        "sentences suitable for a phone call. Ask one question at a time. Discover the prospect's "
        "business problem, explain only these service categories, and offer to arrange a human "
        "consultation. Do not invent prices, guarantees, client results, or contractual terms. "
        "Do not claim to be human. If asked to stop, unsubscribe, or not be called, apologize and "
        "end the call. Prospect said: " + str(prospect_speech)[:1200]
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 100}
    }).encode("utf-8")
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + os.environ.get(
        "JBSN_GEMINI_MODEL", "gemini-2.5-flash"
    ) + ":generateContent?key=" + urllib.parse.quote(api_key)
    request = urllib.request.Request(url, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text[:500] if text else (
            "I want to make sure you get accurate information. I can arrange a human follow-up.")
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError,
            TypeError, json.JSONDecodeError):
        return ("Thanks for your time. I cannot confirm the details right now, "
                "so I can arrange for a JBSN Creative team member to follow up.")
