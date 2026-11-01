# Verification Evidence

This directory contains artifacts produced by the 2026-10-31 repository audit.

- [`verification-report.md`](verification-report.md) — methodology, findings, fixes, results, limitations, verdict
- [`api-console.html`](api-console.html) — static report generated from live SAM local API responses
- [`screenshots/`](screenshots/) — desktop/mobile screenshots of the report and key workflow/error cards
- [`test-results/`](test-results/) — unit tests, HTTP E2E results, browser checks, service-double logs
- [`build-results/`](build-results/) — SAM build, SAM/cfn validation, Terraform validation, lint, dependency install, tooling facts

## What these artifacts prove — and what they do not

The HTTP results were produced by `sam local start-api` with deterministic
local doubles for Bedrock, OpenSearch, and Lambda Invoke
(`scripts/local_aws_doubles.py`). They prove the application's request/response,
validation, layer packaging, and orchestration wiring. They do **not** prove
live AWS authorization, model availability, OpenSearch index semantics, or a
successful Terraform deployment.

Screenshots render actual captured API responses. This repository has no
end-user web frontend, so the screenshots are not product-UI screenshots.

See [`verification-report.md`](verification-report.md) §7 for
remaining limitations.
