import json
import os
import unittest
from unittest.mock import patch
import urllib.request

import elevenlabs_voice


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode()


class ElevenLabsVoiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "JBSN_ELEVENLABS_VOICE_ENABLED": "true",
            "JBSN_ELEVENLABS_CAMPAIGN_APPROVED": "true",
            "ELEVENLABS_API_KEY": "test-secret",
            "ELEVENLABS_AGENT_ID": "agent-test",
            "ELEVENLABS_AGENT_PHONE_NUMBER_ID": "phone-id-test",
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def prospect(self, **changes):
        data = {
            "phone": "+27123456789",
            "contact_permission": True,
            "permission_source": "recorded opt-in",
            "do_not_call": False,
            "opted_out": False,
        }
        data.update(changes)
        return data

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"JBSN_ELEVENLABS_VOICE_ENABLED": "false"}):
            with self.assertRaises(PermissionError):
                elevenlabs_voice.create_outbound_call(self.prospect(), campaign_approved=True)

    def test_requires_campaign_approval(self):
        with self.assertRaises(PermissionError):
            elevenlabs_voice.create_outbound_call(self.prospect(), campaign_approved=False)

    def test_rejects_missing_consent(self):
        with self.assertRaises(PermissionError):
            elevenlabs_voice.create_outbound_call(self.prospect(contact_permission=False), campaign_approved=True)

    def test_rejects_opt_out(self):
        with self.assertRaises(PermissionError):
            elevenlabs_voice.create_outbound_call(self.prospect(opted_out=True), campaign_approved=True)

    def test_rejects_invalid_phone(self):
        with self.assertRaises(ValueError):
            elevenlabs_voice.create_outbound_call(self.prospect(phone="12345"), campaign_approved=True)

    @patch("elevenlabs_voice.urllib.request.urlopen")
    def test_provider_request_uses_secret_header_and_disables_recording(self, urlopen):
        urlopen.return_value = FakeResponse({
            "success": True, "conversation_id": "conv-test", "callSid": "CA-test"
        })
        result = elevenlabs_voice.create_outbound_call(self.prospect(), campaign_approved=True)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.elevenlabs.io/v1/convai/twilio/outbound-call")
        self.assertEqual(request.get_header("Xi-api-key"), "test-secret")
        body = json.loads(request.data.decode())
        self.assertEqual(body["to_number"], "+27123456789")
        self.assertFalse(body["call_recording_enabled"])
        self.assertEqual(result["conversation_id"], "conv-test")
        self.assertEqual(result["provider"], "elevenlabs")

    @patch("elevenlabs_voice.urllib.request.urlopen")
    def test_does_not_claim_success_if_provider_did_not_confirm(self, urlopen):
        urlopen.return_value = FakeResponse({"success": False})
        with self.assertRaises(RuntimeError):
            elevenlabs_voice.create_outbound_call(self.prospect(), campaign_approved=True)


if __name__ == "__main__":
    unittest.main()
