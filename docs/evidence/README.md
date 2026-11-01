# Verification Evidence

This directory contains artifacts produced by the 2026-10-31 repository audit.

- [`verification-report.md`](verification-report.md) — methodology, findings, fixes, results, limitations, verdict
- [`api-console.html`](api-console.html) — static report generated from live SAM local API responses
- [`screenshots/`](screenshots/) — desktop/mobile screenshots of the report, RAG workflow, validation error, and local UI
- [`test-results/`](test-results/) — unit tests, coverage, authenticated HTTP/UI E2E, browser checks, LocalStack assertions, service-double logs
- [`build-results/`](build-results/) — SAM build, SAM/cfn validation, Terraform validation/tests, mypy, lint, SBOM, dependency install, tooling facts

## What these artifacts prove — and what they do not

The HTTP results were produced by `sam local start-api` with deterministic
local doubles for Bedrock, OpenSearch, Lambda Invoke, and a local RS256/JWKS
token issuer (`scripts/local_aws_doubles.py`). Terraform S3/IAM/KMS resources were applied
to LocalStack Community and verified with boto3. Moto covers the S3 ingestion
path. The full Terraform roots are plan-tested with mocked providers.

These tests do **not** prove live AWS authorization, model availability,
OpenSearch Serverless/WAF/GuardDuty/Config semantics, API authentication, or a
successful production deployment.

Screenshots render actual captured API responses. This repository has no
end-user web frontend, so the screenshots are not product-UI screenshots.

See [`verification-report.md`](verification-report.md) §7 for
remaining limitations.
