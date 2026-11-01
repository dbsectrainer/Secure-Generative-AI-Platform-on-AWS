# Secure Generative AI Platform on AWS

> Reference Generative AI platform on AWS using Bedrock, RAG, and a hardened DevSecOps architecture aligned to FedRAMP High. Locally executable with AWS SAM; cloud deployment is not exercised by this repository's verification.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/) [![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.5-blueviolet.svg)](https://www.terraform.io/) [![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange.svg)](https://aws.amazon.com/bedrock/) [![FedRAMP High](https://img.shields.io/badge/FedRAMP-High%20Alignment-red.svg)](FEDRAMP-ALIGNMENT.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Verification status (2026-10-31):** The SAM local API was executed end-to-end against deterministic local service doubles. 122 unit/regression tests pass, lint passes, SAM validates and builds, and Terraform formats/validates. Live AWS authorization, paid model access, and a deployed Terraform stack were **not** verified. See [docs/evidence/verification-report.md](docs/evidence/verification-report.md) for evidence and remaining gaps, including the Terraform modules that are not yet instantiated.

---

## Overview

1. Provides a secure Generative AI reference implementation on AWS using Amazon Bedrock for LLM inference and Retrieval-Augmented Generation (RAG) for grounding responses in proprietary document corpora.
2. Provides a hardened RAG pipeline that ingests documents via S3, generates embeddings, stores vectors in OpenSearch Serverless or Aurora pgvector, and retrieves context for prompt construction with injection-mitigation controls.
3. Enforces a defense-in-depth security architecture including IAM least-privilege, KMS CMK encryption, AWS WAF, private VPC endpoints, CloudTrail audit logging, and GuardDuty threat detection.
4. Implements adversarial resilience controls mapped to STRIDE and MITRE ATT&CK, including prompt injection sanitization, retrieval metadata filtering, and token-abuse design controls. PII redaction via Amazon Comprehend and Bedrock Guardrails are documented design targets; handler integration is not implemented.
5. Delivers a DevSecOps pipeline design with Terraform infrastructure-as-code, SAM-based local testing, automated security scanning targets, and deployment strategy documentation.
6. Maintains a self-assessed FedRAMP High alignment of 92% (318/345 High baseline controls) across 18 of 20 NIST 800-53 Rev 5 control families. This is a mapping exercise, not an authorization; see FEDRAMP-ALIGNMENT.md.

---

## Architecture

```
  Document Sources
  ┌──────────────┐
  │  S3 Ingestion│
  │  (Raw Docs)  │
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  Embedding   │  Lambda (RagEmbeddingFunction)
  │  Pipeline    │  boto3 + Bedrock Titan Embeddings
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────┐
  │  Vector Store            │
  │  OpenSearch Serverless   │
  │  (or Aurora pgvector)    │
  └──────┬───────────────────┘
         │
         ▼
  ┌──────────────┐        ┌──────────────────────┐
  │  RAG         │◄───────│  Bedrock Guardrails   │
  │  Orchestrator│        │  PII Redaction / WAF  │
  │  (Lambda)    │        └──────────────────────┘
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐        ┌──────────────────────┐
  │  Bedrock LLM │        │  Prompt Builder       │
  │  (Claude /   │◄───────│  Lambda Layer         │
  │   Titan)     │        └──────────────────────┘
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────┐
  │  API Gateway + Lambda    │
  │  (BedrockOrchestratorFn) │
  └──────┬───────────────────┘
         │
         ▼
  ┌──────────────┐
  │  AWS WAF     │
  │  Cognito     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │  Observability & Governance                  │
  │  CloudTrail │ CloudWatch │ GuardDuty │ Config │
  └──────────────────────────────────────────────┘
```

---

## Key Features

### Generative AI Layer (Bedrock)

The platform integrates Amazon Bedrock as the LLM inference engine with prompt engineering patterns and response-shaping utilities.

- Claude Messages API request shaping with a generic text-completion body for other model families; explicit model routing/fallback policy is not implemented
- Prompt engineering templates for RAG, citation, and summarization modes
- Bedrock Guardrail provisioning in Terraform; the Lambda handlers do not yet pass a `guardrailIdentifier`
- Token usage and cost estimation in the response; token caps, budget alarms, and anomaly detection are deployment targets, not handler-enforced
- Output moderation is a design target; no moderation call is made in the Lambda response path

### RAG Pipeline

The RAG pipeline supports ingestion and retrieval from document corpora and returns grounded model responses.

- S3-triggered document ingestion with a 5 MB object-size guard; checksum validation is a design target, and S3 versioning is defined in Terraform
- Embedding generation via Bedrock Titan Embeddings (Lambda: RagEmbeddingFunction)
- Vector storage in OpenSearch Serverless (Aurora pgvector is roadmap-only)
- Metadata filters are passed to OpenSearch; they are not an authorization boundary and must not be treated as tenant isolation
- Prompt construction via a reusable Lambda layer (layers/prompt_builder)
- Prompt-injection input sanitization; retrieval output validation is a design target

### Adversarial Resilience and Security

The platform includes a threat model mapped to STRIDE and MITRE ATT&CK, with hands-on attack simulation scripts for red team exercises.

| Threat                 | Mitigation                                            |
| ---------------------- | ----------------------------------------------------- |
| Prompt Injection       | Input sanitization + retrieval filtering (Guardrails design) |
| Data Exfiltration      | Private VPC endpoints + IAM permission boundaries     |
| Token Abuse            | Rate limiting + CloudWatch alarms + budget alerts     |
| Data Tampering         | S3 versioning + checksum validation + Object Lock     |
| Privilege Escalation   | Least-privilege IAM + IAM Access Analyzer             |
| Public Exposure        | Private API Gateway + AWS WAF rules                   |
| Retrieval Manipulation | Output validation + metadata scoping                  |

Attack simulation scripts are located in security/attack-simulation/ and cover prompt injection, token flooding, data leakage, retrieval manipulation, and IAM misconfiguration scenarios.

### DevSecOps CI/CD

The platform uses Terraform for cloud infrastructure and AWS SAM for local Lambda development and testing.

- Terraform modules for core infrastructure (`network`, `s3`, `iam`, `bedrock`); RAG/OpenSearch/security/WAF modules are scaffolded but not yet instantiated
- GitHub Actions CI runs tests, Ruff, Terraform format/validate, SAM validate/build, and cfn-lint
- Deployment strategy documentation for canary/blue-green and rollback; automation is not implemented in this repository
- SAM CLI integration for local Lambda invocation and API Gateway simulation
- SAST, dependency scanning, image scanning, and SBOM generation are roadmap items, not currently wired into CI

### Security and Compliance

- Self-assessed FedRAMP High alignment — 92% (318/345 High baseline controls, 18/20 control families), not an authorization
- NIST SP 800-53 Rev 5 High Baseline
- NIST AI Risk Management Framework 1.0 (GOVERN, MAP, MEASURE, MANAGE functions)
- AWS GovCloud variable example provided; not deployed or verified
- MITRE ATT&CK and STRIDE threat model
- SOC 2 Type II mapping (see security/compliance-mapping.md)
- AWS Well-Architected Framework Security Pillar guidance
- Zero Trust network design guidance (VPC, private subnets, endpoints); the `network` module is defined but not deployed in this audit
- CloudTrail organization-wide audit logging with S3 Object Lock (WORM, 7-year retention) is a design target; it is not instantiated by the current Terraform roots
- KMS CMK for S3 documents is defined in the `s3` module; end-to-end encryption and TLS enforcement are not verified

---

## Quick Start

### Prerequisites

- Python 3.12+ for the test suite and tooling; Lambda runtime is Python 3.13
- AWS SAM CLI >= 1.100.0
- Docker Desktop (required for SAM container builds and local invocation)
- Terraform >= 1.5 (only for infrastructure commands)
- AWS CLI configured with appropriate credentials (only when calling real AWS services)
- GNU Make

> **Model access is account- and region-specific.** The default `BEDROCK_MODEL_ID` is `anthropic.claude-sonnet-5-5`. Before deploying, confirm model access in your account/region and, where required, configure a Bedrock inference profile (the local handlers currently send the model ID directly). An early live smoke test in the audit environment received `ValidationException` (on-demand throughput unsupported) and `AccessDeniedException` (model not available for the account); see the verification report.

### Local Development

Use the SAM CLI targets in the Makefile for local Lambda testing without deploying to AWS.

```bash
# Install development/test dependencies (optional; boto3 is already available
# in the Lambda runtime and most local Python environments)
python3 -m pip install -r requirements-dev.txt

# Run the full test suite and lint
make test
make lint

# Prepare the Lambda layer and build all functions
make sam-build

# Validate the SAM template
make sam-validate

# Invoke individual functions with sample events (calls real AWS services
# when the event reaches Bedrock/OpenSearch)
make sam-invoke-bedrock
make sam-invoke-ingestion
make sam-invoke-embedding
make sam-invoke-retrieval
make sam-invoke-rag

# Start a local API Gateway on port 3000 (uses env.json)
make sam-api
```

Copy `env.local.json.example` to `env.local.json` and populate local test values before invoking against real endpoints. See [docs/local-testing.md](docs/local-testing.md) for configuration, debugging, and known limitations.

#### Verified path: run the API without live AWS

The repository includes deterministic local service doubles for Bedrock, OpenSearch, and Lambda Invoke. This is the mode used for the committed end-to-end evidence.

```bash
# Terminal 1 — local AWS service doubles on port 9000
make mock-aws

# Terminal 2 — SAM API wired to the doubles with placeholder credentials
make sam-api-mock

# Terminal 3 — execute the verification matrix and capture screenshots
make e2e
make screenshots
```

The test-double targets never sign requests with your real AWS credentials. They verify application request/response and orchestration behavior only; they do not prove live AWS permissions, model availability, or OpenSearch semantics.

### Terraform Cloud Deployment

Terraform environments are under `terraform/environments/<env>`. The S3 backend is declared without inline bucket/key values, so it must be initialized with backend configuration:

```bash
cd terraform/environments/dev

# Static validation (no backend or AWS credentials required)
terraform init -backend=false
terraform validate

# For an actual plan, supply the state backend explicitly:
terraform init \
  -backend-config="bucket=<tfstate-bucket>" \
  -backend-config="key=dev/terraform.tfstate" \
  -backend-config="region=eu-west-1" \
  -backend-config="dynamodb_table=<tfstate-lock-table>" \
  -backend-config="encrypt=true"
terraform plan

# Review the plan before applying. Applying creates billable AWS resources.
terraform apply
```

For AWS GovCloud, use the provided variable file after reviewing it:

```bash
terraform apply -var-file="terraform/govcloud.tfvars.example"
```

> **Important:** the dev/prod roots currently instantiate the `network`, `s3`, `iam`, and `bedrock` modules. The `rag`, `opensearch`, `security`, and `waf` modules exist but are **not yet wired into either environment**, and the `rag` module does not attach the prompt-builder Lambda layer. A Terraform apply therefore does not currently produce the full RAG API / WAF / OpenSearch stack described in the architecture. This is tracked as a remaining limitation in the verification report.

See FEDRAMP-ALIGNMENT.md for control family mappings and docs/pii-redaction.md for PII detection design guidance.

---

## Verification Status

**Locally verified reference implementation; not a deployed or independently audited production system.**

| Area | Status |
| ---- | ------ |
| Lambda handlers (5) and API Gateway proxy contract | Verified with unit tests and the running SAM local API |
| Prompt-builder Lambda layer | Verified after fixing a double-nested `python/python/` packaging defect |
| RAG orchestration (`/query`) | Verified end-to-end against local Bedrock/OpenSearch/Lambda doubles |
| Validation and error states | Verified: empty/malformed/non-object JSON, invalid `top_k`, downstream failures |
| Prompt-injection sanitization | Unit-tested and exercised through `/query` |
| SAM build, SAM validate, cfn-lint | Passing locally |
| Terraform format and validate | Passing for `dev` and `prod` roots |
| Full Terraform deployment of RAG/OpenSearch/WAF | **Not wired / not verified** — modules exist but are not instantiated |
| Live AWS Bedrock/OpenSearch authorization and semantics | **Not verified** — local doubles used; no live deployment |
| Bedrock Guardrails / Comprehend PII redaction in handlers | **Not implemented in application code** — design guidance only |
| GitHub Actions CI | Workflow added; not executed on GitHub in this audit |

Verified facts to date:

- `122` unit and regression tests pass in a single root-level pytest run.
- `11/11` live-HTTP verification cases pass against SAM local API with local service doubles.
- SAM build produces `PromptBuilderLayer/python/builder.py` (not `python/python/`).
- `sam validate --lint` and `cfn-lint template.yaml` pass.
- `ruff check .` passes.
- Terraform `fmt -check -recursive` and `validate` pass for both environments.
- The RAG pipeline response includes output, token usage, retrieval count, stage latencies, and cost estimate.

### Validation Commands

```bash
# All unit/regression tests
make test

# Lint and static validation
make lint
make sam-validate
make terraform-validate

# Build the SAM artifacts (Docker required)
make sam-build

# End-to-end HTTP verification against local service doubles
make mock-aws        # terminal 1
make sam-api-mock    # terminal 2
make e2e             # terminal 3
make screenshots     # optional: regenerate image evidence
```

### Visual Evidence

The screenshots below are rendered from the actual responses captured during the SAM local run. This repository has no end-user web frontend; the artifact is an API verification console, not a product UI.

| Desktop summary | Mobile summary |
| --- | --- |
| ![API verification desktop](docs/evidence/screenshots/api-verification-desktop.png) | ![API verification mobile](docs/evidence/screenshots/api-verification-mobile.png) |

| Full RAG workflow (`/query`) | Validation error (`/invoke`) |
| --- | --- |
| ![RAG workflow evidence](docs/evidence/screenshots/query-workflow.png) | ![Validation error evidence](docs/evidence/screenshots/error-validation.png) |

See [docs/evidence/verification-report.md](docs/evidence/verification-report.md) for the full methodology, commands, raw results, and limitations.

---

## Project Structure

```
.
├── .github/workflows/ci.yml     # Python tests/lint, Terraform, SAM validation + build
├── architecture/               # Architecture diagrams and design documents
│   ├── high-level-architecture.md
│   ├── iam-role-design.md
│   └── network-architecture.md
├── docs/                       # Developer guides and audit evidence
│   ├── evidence/               # Screenshots, test results, build results, report
│   ├── local-testing.md
│   └── pii-redaction.md
├── events/                     # Sample event payloads for SAM local testing
├── genai/                      # Generative AI layer (prompt builder, templates, docs)
│   ├── prompt_builder/
│   └── tests/
├── lambda/                     # Lambda function handlers
│   └── bedrock_integration/
├── layers/                     # Lambda layer source (builder.py generated by make)
│   └── prompt_builder/
├── rag/                        # RAG pipeline implementation
│   ├── embedding/
│   ├── ingestion/
│   ├── orchestrator/
│   └── retrieval/
├── scripts/                    # Local AWS doubles and reproducible evidence tooling
│   ├── capture_evidence.py
│   ├── e2e_api_verify.py
│   └── local_aws_doubles.py
├── security/                   # Security configs, threat models, attack simulations
│   ├── attack-simulation/
│   ├── compliance-mapping.md
│   ├── iam-least-privilege-validation.md
│   └── injection-mitigation-results.md
├── terraform/                  # Infrastructure as Code modules and environments
│   ├── environments/{dev,prod}/
│   └── modules/
├── FEDRAMP-ALIGNMENT.md        # FedRAMP High self-assessment mapping
├── Makefile                    # Build, test, local API, and evidence targets
├── pyproject.toml              # Pytest and Ruff configuration
├── requirements-dev.txt        # Test/lint/evidence tooling
├── samconfig.toml              # SAM local configuration
├── template.yaml               # SAM template (local testing only)
└── README.md
```

---

## BE EASY ENTERPRISES Federal Portfolio

| Showcase Project               | Repository                                                                                                       | Description                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| **Secure RAG Pipeline**        | **[Secure-Generative-AI-Platform-on-AWS](https://github.com/dbsectrainer/Secure-Generative-AI-Platform-on-AWS)** | **This repo**                                     |
| **DevSecOps CI/CD**            | [dod-cybersec-ops-framework](https://github.com/dbsectrainer/dod-cybersec-ops-framework)                         | DoD 8570 / NIST RMF aligned pipeline              |
| **Zero Trust Architecture**    | [AEGIS](https://github.com/dbsectrainer/AEGIS)                                                                   | FedRAMP High + NIST 800-207 Zero Trust            |
| **FedRAMP Control Automation** | [nist_800_53_scanner](https://github.com/dbsectrainer/nist_800_53_scanner)                                       | NIST 800-53 Rev 5 compliance scanner              |
| **Federal AI Governance**      | [ai-safety-governance](https://github.com/dbsectrainer/ai-safety-governance)                                     | EO 14110 / OMB M-24-10 aligned                    |
| **CMMC 2.0 Dashboard**         | [integrated-cyber-risk-compliance](https://github.com/dbsectrainer/integrated-cyber-risk-compliance)             | CMMC 2.0 readiness assessment                     |
| **FedRAMP 30-Day Guide**       | [cloud-security-best-practices](https://github.com/dbsectrainer/cloud-security-best-practices)                   | Day-by-day FedRAMP implementation roadmap         |
| **Agentic AI Workflow**        | [federal-doc-triage-agent](https://github.com/dbsectrainer/federal-doc-triage-agent)                             | Production-ready LangGraph + Bedrock triage agent |

---

## Author

**Donnivis Baker** — [github.com/dbsectrainer](https://github.com/dbsectrainer)
**BE EASY ENTERPRISES** — Federal IT Modernization & Cybersecurity

For questions, partnerships, or federal engagement inquiries, open an issue or reach out directly.

**Document Version:** 1.1 | **Last Updated:** 2026-10-31 | **FedRAMP High:** Self-assessed 92% control coverage (318/345; not an authorization)
