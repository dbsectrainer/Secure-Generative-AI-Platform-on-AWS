# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- AWS SAM CLI local testing: SAM template, Makefile, sample events, environment config, and documentation for testing all 5 Lambda functions locally without deploying
- Deterministic local AWS service doubles for Bedrock, OpenSearch, and Lambda Invoke
- End-to-end HTTP verification script, Playwright evidence capture, and `docs/evidence/`
- GitHub Actions CI for Python tests/lint, Terraform validation, SAM validation, and SAM build
- Root `pyproject.toml`, `requirements-dev.txt`, and consolidated Makefile quality targets
- Optional `BEDROCK_ENDPOINT_URL` / `LAMBDA_ENDPOINT_URL` test overrides
- Phase 3 security hardening: threat model, attack simulations, WAF/GuardDuty/Config modules, extended injection patterns
- Phase 2 RAG pipeline implementation
- Initial project structure with architecture, genai, lambda, rag, security, and terraform modules
- Terraform infrastructure baseline
- Amazon Bedrock integration
- Secure S3 document ingestion
- IAM least-privilege role design
- Project README, ROADMAP, and documentation

### Fixed

- API Gateway proxy requests were rejected as 400 because handlers read fields from the top-level proxy event instead of its JSON `body`
- API Gateway responses returned Python dicts, producing invalid JSON (`{'error': ...}`) to HTTP clients
- Prompt-builder Lambda layer was double-nested as `python/python/`, causing `RuntimeError: No module named 'builder'` on `/query`
- `top_k: null` / non-integer values raised an unhandled `TypeError` and returned 500 instead of 400
- Bedrock/OpenSearch error details were echoed to API callers; responses now return generic upstream errors while details stay in logs
- Terraform files were not consistently formatted
- Ruff lint findings in handlers, tests, and attack-simulation scripts

### Changed

- SAM local API uses an in-workspace layer cache for reliable startup
- README, local-testing guide, PII guide, FedRAMP mapping, and security validation documents now distinguish verified behavior from intended/design-only controls
