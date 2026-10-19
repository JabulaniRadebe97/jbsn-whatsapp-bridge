"""Executable recovery contract; intentionally skipped until lease implementation lands.

These are safety requirements, not passing coverage. Remove skip only when the
runtime implements leases, claim fencing and schema migrations.
"""
import unittest


@unittest.skip("Recovery lease implementation pending; this is a contract checklist")
class TaskRecoveryContractTests(unittest.TestCase):
    def test_expired_running_lease_can_be_requeued(self):
        self.fail("Use an isolated SQLite database and assert one recovery event")

    def test_unexpired_running_lease_is_not_reclaimed(self):
        self.fail("A live lease must remain running")

    def test_legacy_running_task_without_lease_is_not_reclaimed(self):
        self.fail("Legacy records require manual review, not automatic replay")

    def test_stale_claim_token_cannot_complete_newer_attempt(self):
        self.fail("Completion must use conditional status and token fencing")

    def test_two_recovery_workers_cannot_both_recover_one_task(self):
        self.fail("Test concurrent PostgreSQL transactions in isolated CI database")

    def test_awaiting_approval_and_cancelled_tasks_never_recovered(self):
        self.fail("Approval and cancellation gates must remain enforced")

    def test_schema_migration_preserves_existing_records(self):
        self.fail("Test both SQLite and PostgreSQL pre-migration databases")


if __name__ == "__main__":
    unittest.main()
