"""Tests for fail-closed voice-sales safeguards."""
import os
import unittest
from unittest.mock import patch
import voice_agent


class VoiceAgentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.prospect = {
            "phone": "+27123456789",
            "contact_permission": True,
            "permission_source": "website form 2026-10-21",
        }

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"JBSN_VOICE_ENABLED": "false"}, clear=False):
            with self.assertRaisesRegex(PermissionError, "disabled"):
                voice_agent.validate_call_request(self.prospect, campaign_approved=True)

    def test_campaign_must_be_approved(self):
        env = {"JBSN_VOICE_ENABLED": "true", "JBSN_VOICE_CAMPAIGN_APPROVED": "true"}
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(PermissionError, "Founder-approved"):
                voice_agent.validate_call_request(self.prospect, campaign_approved=False)

    def test_permission_source_is_required(self):
        env = {"JBSN_VOICE_ENABLED": "true", "JBSN_VOICE_CAMPAIGN_APPROVED": "true"}
        prospect = dict(self.prospect, permission_source="")
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(PermissionError, "permission_source"):
                voice_agent.validate_call_request(prospect, campaign_approved=True)

    def test_opted_out_prospect_is_rejected(self):
        env = {"JBSN_VOICE_ENABLED": "true", "JBSN_VOICE_CAMPAIGN_APPROVED": "true"}
        prospect = dict(self.prospect, opted_out=True)
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(PermissionError, "opted out"):
                voice_agent.validate_call_request(prospect, campaign_approved=True)

    def test_valid_request_returns_normalized_phone(self):
        env = {"JBSN_VOICE_ENABLED": "true", "JBSN_VOICE_CAMPAIGN_APPROVED": "true"}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(voice_agent.validate_call_request(self.prospect, campaign_approved=True),
                             "+27123456789")

    def test_twiml_discloses_ai(self):
        xml = voice_agent.build_disclosure_twiml("JBSN Creative")
        self.assertIn("AI voice assistant", xml)
        self.assertIn("Gather", xml)
        self.assertIn("stop at any time", xml)

    def test_turn_stops_on_phrase_request(self):
        xml = voice_agent.build_turn_twiml(
            "Please stop calling me", "https://example.test")
        self.assertIn("<Hangup/>", xml)
        self.assertIn("end this call", xml)

    def test_invalid_twilio_signature_is_rejected(self):
        with patch.dict(os.environ, {"TWILIO_AUTH_TOKEN": "test-token"}, clear=False):
            self.assertFalse(voice_agent.validate_twilio_signature(
                "https://example.test/voice/turn", {"SpeechResult": "hello"}, "bad-signature"))

    def test_invalid_number_rejected(self):
        env = {"JBSN_VOICE_ENABLED": "true", "JBSN_VOICE_CAMPAIGN_APPROVED": "true"}
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaisesRegex(ValueError, "E.164"):
                voice_agent.validate_call_request(dict(self.prospect, phone="12345"),
                                                  campaign_approved=True)


if __name__ == "__main__":
    unittest.main()
