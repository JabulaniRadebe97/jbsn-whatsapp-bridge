"""Health/readiness payload tests for the safe AI OS runtime."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as runtime  # noqa: E402


class HealthReadinessTests(unittest.TestCase):
    def test_health_reports_worker_configuration_without_secrets(self):
        with patch.object(runtime, "WORKER_ENABLED", True), \
             patch.object(runtime, "WORKER_POLL_SECONDS", 5), \
             patch.object(runtime, "USE_POSTGRES", True), \
             patch.dict(os.environ, {}, clear=True):
            payload = runtime.health_payload("healthy", "postgresql")

        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["database"], "postgresql")
        self.assertTrue(payload["worker"]["enabled"])
        self.assertEqual(payload["worker"]["poll_seconds"], 5)
        self.assertEqual(payload["worker"]["registry"], ["plan", "business_plan"])
        self.assertIn("running", payload["worker"])
        self.assertIn("tasks_processed", payload["worker"])
        self.assertIn("last_error_type", payload["worker"])
        self.assertNotIn("token", payload)
        self.assertNotIn("DATABASE_URL", payload)
        self.assertNotIn("payload", payload["worker"])

    def test_degraded_health_still_reports_worker_as_configured(self):
        with patch.object(runtime, "WORKER_ENABLED", False), \
             patch.object(runtime, "WORKER_POLL_SECONDS", 5), \
             patch.object(runtime, "USE_POSTGRES", False), \
             patch.dict(os.environ, {}, clear=True):
            payload = runtime.health_payload("degraded", "unavailable")

        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["worker"]["enabled"])
        self.assertEqual(payload["worker"]["registry"], ["plan", "business_plan"])
        self.assertFalse(payload["worker"]["running"])
        self.assertEqual(payload["worker"]["tasks_processed"], 0)


if __name__ == "__main__":
    unittest.main()
