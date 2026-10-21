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


# Short-lived per-call state. It is intentionally bounded and contains only the fields
# needed to complete one booking; a process restart safely abandons an incomplete flow.
_BOOKING_SESSIONS = {}
_BOOKING_SESSION_LOCK = __import__("threading").Lock()
_BOOKING_SESSION_MAX = 500


def _booking_api(method, path, payload=None):
    """Call the authenticated internal booking API without exposing its token to callers."""
    token = os.environ.get("JBSN_API_TOKEN", "").strip()
    base = os.environ.get("JBSN_PUBLIC_BASE_URL", "").rstrip("/")
    if not token or not base:
        raise RuntimeError("booking API credentials or public base URL are not configured")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base + path, data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            raise ValueError("That slot was just booked. Please choose another time.") from None
        raise RuntimeError("booking API returned HTTP " + str(exc.code)) from None
    except urllib.error.URLError:
        raise RuntimeError("booking API connection failed") from None


def _booking_step(speech, call_sid):
    """Deterministic, explicit-consent booking flow for a Twilio speech turn."""
    text = str(speech or "").strip()
    normalized = text.lower()
    if not call_sid:
        return None
    with _BOOKING_SESSION_LOCK:
        session = _BOOKING_SESSIONS.get(call_sid)
        if session is None:
            if not any(word in normalized for word in ("book", "booking", "appointment", "schedule", "consultation")):
                return None
            if len(_BOOKING_SESSIONS) >= _BOOKING_SESSION_MAX:
                _BOOKING_SESSIONS.clear()
            _BOOKING_SESSIONS[call_sid] = {"step": "name"}
            return "I can help arrange a discovery appointment. What name should I put on the booking?"
        # Never retain a session after an explicit stop or refusal.
        if any(phrase in normalized for phrase in ("stop", "unsubscribe", "do not call", "don't call", "dont call", "remove me", "end call")):
            _BOOKING_SESSIONS.pop(call_sid, None)
            return "Understood. I will end this call. Goodbye."
        step = session["step"]
        if step == "name":
            if not text or len(text) > 120:
                return "Please say the name you would like on the appointment."
            session["name"] = text
            session["step"] = "email"
            return "Thank you. Please say your email address slowly."
        if step == "email":
            email = text.lower().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
                return "I could not validate that email. Please say the full email address again."
            session["email"] = email
            session["step"] = "date"
            return "What date would suit you? Please say the date as year, month, day, for example 2026-10-28."
        if step == "date":
            from datetime import date
            try:
                day = date.fromisoformat(text)
            except ValueError:
                return "Please say the date in year-month-day format, for example 2026-10-28."
            session["date"] = day.isoformat()
            session["step"] = "time"
            return "What time between 09:00 and 16:30 South African time? Please use 24-hour format, such as 14:30."
        if step == "time":
            from datetime import datetime
            if not re.fullmatch(r"(?:09|1[0-6]):(?:00|30)", text):
                return "Please choose a weekday time between 09:00 and 16:30, using 24-hour format."
            try:
                availability = _booking_api("GET", "/v1/booking/availability?date=" +
                    urllib.parse.quote(session["date"]) + "&timezone=Africa%2FJohannesburg&service=discovery")
            except Exception:
                _BOOKING_SESSIONS.pop(call_sid, None)
                return "I cannot access the booking calendar right now. I will need a team member to follow up."
            if availability.get("external_calendar_connected") is not False:
                _BOOKING_SESSIONS.pop(call_sid, None)
                return "I cannot verify the calendar status, so I will ask a team member to follow up."
            slot = next((s for s in availability.get("slots", [])
                         if s.get("start_at", "").startswith(session["date"] + "T" + text + ":")), None)
            if not slot:
                return "That time is not available. Please choose another time on that date, using 24-hour format."
            session["slot_id"] = slot["slot_id"]
            session["time"] = text
            session["step"] = "consent"
            return ("I have " + session["date"] + " at " + text +
                " South African time available. May JBSN Creative store your name and email and contact you about this appointment? Please say yes or no.")
        if step == "consent":
            if normalized not in ("yes", "yes please", "i agree", "i consent", "okay", "ok"):
                if normalized in ("no", "no thanks", "i do not consent", "i don't consent"):
                    _BOOKING_SESSIONS.pop(call_sid, None)
                    return "No problem. I will not create a booking or store your contact details. Goodbye."
                return "Please answer yes or no. Your explicit permission is required to create the booking."
            payload = {
                "name": session["name"], "email": session["email"], "service": "discovery",
                "timezone": "Africa/Johannesburg", "slot_id": session["slot_id"],
                "idempotency_key": "voice-" + re.sub(r"[^A-Za-z0-9]", "", call_sid)[:80],
                "contact_consent": True,
            }
            try:
                result = _booking_api("POST", "/v1/booking/appointments", payload)
            except Exception:
                _BOOKING_SESSIONS.pop(call_sid, None)
                return "I could not confirm that appointment, so I will not say it is booked. Please contact our team to arrange it."
            appointment = result.get("appointment", {})
            if not appointment:
                _BOOKING_SESSIONS.pop(call_sid, None)
                return "I could not verify the booking confirmation. Please contact our team."
            _BOOKING_SESSIONS.pop(call_sid, None)
            return ("Your appointment is confirmed for " + session["date"] + " at " +
                session["time"] + " South African time. This is recorded in the JBSN internal calendar only; no external calendar invitation was sent. Thank you.")
    return None


def build_turn_twiml(speech_result, public_base_url, call_sid=""):
    """Generate a bounded voice response; explicit booking intent uses the internal booking API."""
    speech = str(speech_result or "").strip()
    normalized = speech.lower().strip(" .,!?")
    stop_phrases = ("stop", "unsubscribe", "do not call", "don't call",
                    "dont call", "remove me", "end call", "stop calling")
    if any(phrase in normalized for phrase in stop_phrases):
        with _BOOKING_SESSION_LOCK:
            _BOOKING_SESSIONS.pop(call_sid, None)
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Say voice="Polly.Joanna-Neural">Understood. I will end this call. Goodbye.</Say>'
                '<Hangup/></Response>')
    if not speech:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Response><Say voice="Polly.Joanna-Neural">Sorry, I did not catch that. '
                'I will arrange for a team member to follow up. Goodbye.</Say><Hangup/></Response>')
    try:
        reply = _booking_step(speech, call_sid)
    except Exception:
        reply = "I cannot complete a booking right now. I will not claim it is booked; a team member can follow up."
    if reply is None:
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
