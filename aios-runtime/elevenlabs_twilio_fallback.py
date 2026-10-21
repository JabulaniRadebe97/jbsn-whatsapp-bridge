"""ElevenLabs register-call fallback using the user's own Twilio REST account.

This bypasses ElevenLabs phone-number import, but does not bypass Twilio account
or trial restrictions. Disabled by default and guarded by consent/approval.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

E164_RE = re.compile(r"^\\+[1-9]\\d{7,14}$")


def _on(name):
    return os.environ.get(name, "false").strip().lower() in ("1", "true", "yes", "on")


def create_outbound_call(prospect, campaign_approved=False):
    if not _on("JBSN_ELEVENLABS_TWILIO_FALLBACK_ENABLED"):
        raise PermissionError("ElevenLabs Twilio fallback is disabled")
    if not campaign_approved or not _on("JBSN_ELEVENLABS_CAMPAIGN_APPROVED"):
        raise PermissionError("Founder-approved ElevenLabs campaign is required")
    if not isinstance(prospect, dict):
        raise ValueError("prospect must be an object")

    to_number = str(prospect.get("phone", "")).strip()
    if not E164_RE.fullmatch(to_number):
        raise ValueError("prospect.phone must be E.164 format")
    if prospect.get("do_not_call") is True or prospect.get("opted_out") is True:
        raise PermissionError("Prospect is opted out or on the do-not-call list")
    if prospect.get("contact_permission") is not True:
        raise PermissionError("Documented permission to call is required")
    if not str(prospect.get("permission_source", "")).strip():
        raise PermissionError("permission_source is required for audit")

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID", "").strip()
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
    if not all((api_key, agent_id, account_sid, auth_token, from_number)):
        raise RuntimeError(
            "Configure ElevenLabs API key/agent ID and Twilio account SID/auth token/from number"
        )
    if not E164_RE.fullmatch(from_number):
        raise RuntimeError("TWILIO_FROM_NUMBER must be E.164 format")

    registration = json.dumps({
        "agent_id": agent_id,
        "from_number": from_number,
        "to_number": to_number,
        "direction": "outbound",
    }).encode("utf-8")
    register_req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/twilio/register-call",
        data=registration,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(register_req, timeout=20) as response:
            twiml = response.read().decode("utf-8").strip()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"ElevenLabs register-call failed with HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("ElevenLabs register-call network error") from None

    if not twiml.startswith("<") or "<Response" not in twiml:
        raise RuntimeError("ElevenLabs register-call returned invalid TwiML")

    call_data = urllib.parse.urlencode({
        "To": to_number,
        "From": from_number,
        "Twiml": twiml,
    }).encode("utf-8")
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    call_req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json",
        data=call_data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(call_req, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Twilio call creation failed with HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Twilio call creation network error") from None

    return {
        "provider": "twilio+elevenlabs_register_call",
        "status": "accepted",
        "call_sid": result.get("sid"),
        "to": to_number,
        "from": from_number,
        "mode": "outbound_voice",
        "recording_enabled": False,
        "note": "Accepted by Twilio; this does not mean the call was answered.",
    }
