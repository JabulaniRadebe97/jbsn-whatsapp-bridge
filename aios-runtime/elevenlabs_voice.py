"""ElevenLabs outbound-call adapter for JBSN AI OS.

Disabled by default. Requires founder-authenticated API access, explicit campaign
approval, documented permission to call, and a configured outbound-capable
ElevenLabs phone number linked to Twilio or Exotel. Never logs credentials.
"""
import json
import os
import re
import urllib.error
import urllib.request

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def enabled():
    return os.environ.get("JBSN_ELEVENLABS_VOICE_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on"
    )


def create_outbound_call(prospect, campaign_approved=False):
    """Place one real provider call only when every gate is explicitly satisfied."""
    if not enabled():
        raise PermissionError("ElevenLabs outbound calling is disabled")
    if not campaign_approved or os.environ.get(
        "JBSN_ELEVENLABS_CAMPAIGN_APPROVED", "false"
    ).strip().lower() not in ("1", "true", "yes", "on"):
        raise PermissionError("Founder-approved ElevenLabs campaign is required")
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

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID", "").strip()
    phone_number_id = os.environ.get("ELEVENLABS_AGENT_PHONE_NUMBER_ID", "").strip()
    if not all((api_key, agent_id, phone_number_id)):
        raise RuntimeError(
            "Configure ElevenLabs API key, agent ID, and outbound-capable linked phone number ID"
        )

    body = json.dumps({
        "agent_id": agent_id,
        "agent_phone_number_id": phone_number_id,
        "to_number": phone,
        "call_recording_enabled": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
        data=body,
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not relay provider response bodies, which may contain account details.
        raise RuntimeError(f"ElevenLabs outbound call request failed with HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("ElevenLabs outbound call network error") from None

    if not isinstance(result, dict) or result.get("success") is not True:
        raise RuntimeError("ElevenLabs did not confirm call creation")
    return {
        "provider": "elevenlabs",
        "status": "accepted",
        "conversation_id": result.get("conversation_id"),
        "call_sid": result.get("callSid"),
        "to": phone,
        "mode": "outbound_voice",
        "recording_enabled": False,
    }
