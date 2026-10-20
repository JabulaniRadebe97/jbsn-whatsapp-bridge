# JBSN AI OS — Release and Autonomy Gates

This workflow is a first release-quality gate for the AI OS runtime. It validates Python syntax, dependency manifest expectations and a small dashboard/brand contract on pull requests and pushes to the production branch.

## Release path

1. Implement work on an isolated branch.
2. Open a pull request into `jbsn-aios-runtime-bootstrap`.
3. Wait for the GitHub Actions quality-gate workflow.
4. Merge only after checks pass and the change is reviewed.
5. Render auto-deploys from the configured production branch.
6. Confirm the resulting Render deployment and perform authenticated API smoke tests before declaring the release verified.

## Autonomy boundary

This workflow does **not** execute AI-generated code, approve its own pull requests, change production secrets, or independently deploy arbitrary changes. Those capabilities require a separate isolated runner, strict command allowlists, test and security gates, immutable audit records, rollback verification, and an approval policy. Routine low-risk operations can be automated incrementally; payments, public outreach, sensitive data changes and high-risk production releases remain approval-gated.

## Current test coverage

The workflow performs compile checks and a dashboard contract check. It runs Python unit tests if runtime test files exist. This is a baseline quality gate, not comprehensive integration or security coverage. Add database, authentication, worker lifecycle, Gemini provider and HTTP endpoint tests before treating the runtime as production-ready.
