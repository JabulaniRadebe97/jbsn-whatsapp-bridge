"""Unit tests for safe, deterministic JBSN AI OS runtime contracts."""
import importlib.util
import os
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("jbsn_aios_runtime_main", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class PlanContractTests(unittest.TestCase):
    def test_plan_returns_plan_only_and_explicit_execution_boundary(self):
        result = runtime.plan({"objective": "Prepare a launch checklist"})
        self.assertEqual(result["mode"], "plan_only")
        self.assertEqual(result["objective"], "Prepare a launch checklist")
        self.assertIn("does not generate or deploy code autonomously", result["notice"])
        self.assertGreaterEqual(len(result["steps"]), 5)

    def test_plan_rejects_missing_objective(self):
        with self.assertRaisesRegex(ValueError, "objective is required"):
            runtime.plan({"objective": "  "})

    def test_worker_registry_is_allowlisted(self):
        self.assertEqual(set(runtime.health_payload("healthy", "sqlite")["worker"]["registry"]),
                         {"plan", "business_plan"})

    def test_worker_health_does_not_claim_code_deployment(self):
        payload = runtime.health_payload("healthy", "sqlite")
        self.assertEqual(payload["mode"], "safe-bootstrap")
        self.assertIn("enabled", payload["worker"])
        self.assertNotIn("autonomous_deploy", payload["worker"])

    def test_poll_interval_bounds(self):
        for value in (1, 5, 60):
            self.assertEqual(runtime.configured_worker_poll_seconds(value), value)
        for value in (0, 61, "bad"):
            with self.assertRaises(ValueError):
                runtime.configured_worker_poll_seconds(value)

    def test_lease_duration_bounds(self):
        for value in (30, 300, 86400):
            self.assertEqual(runtime.configured_lease_seconds(value), value)
        for value in (29, 86401, "bad"):
            with self.assertRaises(ValueError):
                runtime.configured_lease_seconds(value)


if __name__ == "__main__":
    unittest.main()
