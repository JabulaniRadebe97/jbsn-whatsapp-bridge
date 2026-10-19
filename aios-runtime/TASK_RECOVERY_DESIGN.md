# JBSN AI OS Task Recovery Design

Status: proposal only. This document does not authorize a merge or deployment.

## Problem

The worker commits a task as `running` before executing its plan. If the process exits between that commit and the terminal update, the task can remain `running` indefinitely. Reclaiming every running task at startup would be unsafe because another worker may still be processing it.

## Proposed semantics

1. Add a nullable `lease_expires_at` and a unique `claim_token` to each task. Migrate existing databases idempotently; existing running tasks without lease metadata must not be reclaimed automatically.
2. Claiming a queued task atomically sets `status=running`, increments `attempts`, sets a lease deadline using server time, assigns a fresh claim token, and writes `task.started` in the same transaction.
3. Recovery may requeue only `running` tasks with a non-null lease deadline that has expired. The recovery update must be conditional on the observed expired deadline/token and must write `task.recovered` in the same transaction.
4. A worker may write `succeeded` or `failed` only when task ID, `status=running`, and claim token still match. A stale worker whose lease was superseded must not overwrite a newer attempt.
5. Lease expiry is a recovery eligibility threshold, not proof that the old process has stopped. Conditional completion fencing is therefore mandatory.
6. Approval-gated tasks (`awaiting_approval`) and cancelled tasks are never eligible for recovery. Amber/red work still needs the existing approval flow before it can be claimed.
7. Use a configurable, validated lease duration with a conservative default. Do not add an unbounded retry loop; cap attempts or move repeatedly failing tasks to a review-required state in a separately specified policy.

## Required tests

- SQLite: expired lease is recovered; live lease is untouched; task without lease is untouched; event and status changes are atomic.
- PostgreSQL: two recovery workers cannot both recover the same task; two claimers cannot claim the same queued task.
- Fencing: after recovery and a new claim, an old claim token cannot write a terminal result.
- Approval: awaiting-approval and cancelled tasks remain untouched.
- Migration: fresh schema and pre-existing schema both initialize safely on SQLite and PostgreSQL.
- Failure handling: a recovery transaction rollback leaves task state and events consistent.
- API behavior: return safe, deterministic responses for no eligible recovery work and invalid lease configuration.

## Rollout constraints

- Test against an isolated PostgreSQL instance in CI.
- Do not point tests at the production database.
- Do not merge or deploy until the implementation, migration behavior, recovery races, and operational recovery procedure are reviewed.
- Recovery must remain separate from arbitrary code execution or external side effects; the current worker remains plan-only.
