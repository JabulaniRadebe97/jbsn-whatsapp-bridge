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
