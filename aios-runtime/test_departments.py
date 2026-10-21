"""Tests for the JBSN departmental agent manifest."""
import unittest
import departments


class DepartmentManifestTests(unittest.TestCase):
    def test_all_core_departments_registered(self):
        manifest = departments.department_manifest()
        ids = {d["id"] for d in manifest["departments"]}
        self.assertTrue({
            "executive", "sales", "marketing", "creative", "client_success",
            "operations", "finance", "people", "engineering", "security",
            "analytics", "reputation",
        }.issubset(ids))
        self.assertEqual(manifest["departments_total"], len(manifest["departments"]))

    def test_manifest_does_not_claim_live_actions(self):
        manifest = departments.department_manifest()
        self.assertEqual(manifest["departments_with_live_external_actions"], 0)
        self.assertFalse(manifest["voice_outbound_enabled"])
        self.assertTrue(all(d["live_actions"] is False for d in manifest["departments"]))

    def test_voice_agent_is_registered_but_guarded(self):
        sales = next(d for d in departments.DEPARTMENTS if d["id"] == "sales")
        self.assertEqual(sales["mode"], "voice_ready_guarded")
        self.assertIn("outbound call initiation when enabled", sales["capabilities"])


if __name__ == "__main__":
    unittest.main()
