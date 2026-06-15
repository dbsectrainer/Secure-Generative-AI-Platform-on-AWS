# Secure Generative AI Platform on AWS

> Production-ready Generative AI platform on AWS using Bedrock, RAG, and a hardened DevSecOps architecture aligned to FedRAMP High.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/) [![Terraform](https://img.shields.io/badge/terraform-%3E%3D1.x-blueviolet.svg)](https://www.terraform.io/) [![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange.svg)](https://aws.amazon.com/bedrock/) [![FedRAMP High](https://img.shields.io/badge/FedRAMP-High%20Alignment-red.svg)](FEDRAMP-ALIGNMENT.md) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

1. Implements a secure, production-ready Generative AI platform on AWS using Amazon Bedrock for LLM inference and Retrieval-Augmented Generation (RAG) for grounding responses in proprietary document corpora.
2. Provides a hardened RAG pipeline that ingests documents via S3, generates embeddings, stores vectors in OpenSearch Serverless or Aurora pgvector, and retrieves context for prompt construction with injection-mitigation controls.
3. Enforces a defense-in-depth security architecture including IAM least-privilege, KMS CMK encryption, AWS WAF, private VPC endpoints, CloudTrail audit logging, and GuardDuty threat detection.
4. Implements adversarial resilience controls mapped to STRIDE and MITRE ATT&CK, including prompt injection mitigation, token abuse rate limiting, retrieval filtering, and PII redaction via AWS Comprehend and Bedrock Guardrails.
5. Delivers a complete DevSecOps pipeline with Terraform infrastructure-as-code, SAM-based local testing, automated security scanning, canary and blue/green deployment strategies, and automated rollback triggers.
6. Maintains FedRAMP High alignment with 92% coverage (318/345 High baseline controls) across 18 of 20 NIST 800-53 Rev 5 control families, with full documentation in FEDRAMP-ALIGNMENT.md.

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

The platform integrates Amazon Bedrock as the LLM inference engine with model selection strategy, prompt engineering patterns, and production-grade output controls.

- Model selection routing (Claude, Titan) with fallback logic
- Prompt engineering templates for RAG, citation, and summarization modes
- Bedrock Guardrails for content filtering, topic blocking, and PII anonymization
- Token usage management with cap enforcement and cost anomaly detection
- Output moderation controls integrated into the Lambda response path

### RAG Pipeline

The RAG pipeline supports secure ingestion and retrieval from proprietary document corpora without exposing raw data to the LLM layer directly.

- S3-triggered document ingestion with checksum validation and S3 versioning
- Embedding generation via Bedrock Titan Embeddings (Lambda: RagEmbeddingFunction)
- Vector storage in OpenSearch Serverless or Aurora pgvector
- Retrieval filtering with metadata-based access scoping to prevent cross-tenant data leakage
- Prompt construction via a reusable Lambda layer (layers/prompt_builder)
- Injection mitigation via input sanitization and retrieval output validation

### Adversarial Resilience and Security

The platform includes a threat model mapped to STRIDE and MITRE ATT&CK, with hands-on attack simulation scripts for red team exercises.

| Threat | Mitigation |
| --- | --- |
| Prompt Injection | Input sanitization + retrieval filtering + Guardrails |
| Data Exfiltration | Private VPC endpoints + IAM permission boundaries |
| Token Abuse | Rate limiting + CloudWatch alarms + budget alerts |
| Data Tampering | S3 versioning + checksum validation + Object Lock |
| Privilege Escalation | Least-privilege IAM + IAM Access Analyzer |
| Public Exposure | Private API Gateway + AWS WAF rules |
| Retrieval Manipulation | Output validation + metadata scoping |

Attack simulation scripts are located in security/attack-simulation/ and cover prompt injection, token flooding, data leakage, retrieval manipulation, and IAM misconfiguration scenarios.

### DevSecOps CI/CD

The platform uses Terraform for cloud infrastructure and AWS SAM for local Lambda development and testing.

- Terraform modules for all AWS resources (bedrock, VPC, OpenSearch, security, monitoring)
- Automated SAST and dependency scanning in the CI/CD pipeline
- ECR container image scanning before Lambda layer promotion
- Canary and blue/green deployment strategies with automatic rollback triggers
- SAM CLI integration for local Lambda invocation and API Gateway simulation
- SBOM generation and supply chain controls via Dependabot and image scanning

### Security and Compliance

- FedRAMP High alignment — 92% coverage (318/345 High baseline controls, 18/20 control families)
- NIST SP 800-53 Rev 5 High Baseline
- NIST AI Risk Management Framework 1.0 (GOVERN, MAP, MEASURE, MANAGE functions)
- AWS GovCloud ready — us-gov-west-1 and us-gov-east-1 region configurations
- MITRE ATT&CK and STRIDE threat model
- SOC 2 Type II mapping (see security/compliance-mapping.md)
- AWS Well-Architected Framework Security Pillar
- Zero Trust network architecture with private endpoints and segmented multi-account strategy
- CloudTrail organization-wide audit logging with S3 Object Lock (WORM, 7-year retention)
- KMS CMK encryption for all data at rest and in transit (TLS 1.2+)

---

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.x
- AWS SAM CLI >= 1.100.0
- Docker Desktop (required for SAM local testing)
- Python 3.12+
- AWS Organization with multi-account setup recommended (Dev / Staging / Prod)

### Local Development

Use the SAM CLI targets in the Makefile for local Lambda testing without deploying to AWS.

```bash
# Prepare the Lambda layer and build all functions
make sam-build

# Invoke the Bedrock orchestrator with a sample event
make sam-invoke-bedrock

# Invoke the RAG ingestion function with a sample S3 event
make sam-invoke-ingestion

# Invoke the embedding pipeline
make sam-invoke-embedding

# Invoke the retrieval function
make sam-invoke-retrieval

# Invoke the full RAG orchestrator
make sam-invoke-rag

# Start a local API Gateway on port 3000
make sam-api
```

Copy env.local.json.example to env.json and populate with local test values before running. See docs/local-testing.md for full configuration details, debugging tips, and known limitations.

### Terraform Cloud Deployment

```bash
# Initialize providers and modules
terraform init

# Review the execution plan
terraform plan

# Apply infrastructure
terraform apply
```

For AWS GovCloud deployment, use the provided variable file:

```bash
terraform apply -var-file="terraform/govcloud.tfvars.example"
```

See FEDRAMP-ALIGNMENT.md for control family mappings and docs/pii-redaction.md for PII detection configuration.

---

## Production Ready Status

**Hardened generative AI platform with FedRAMP High alignment path verified.**

- Lambda handlers implemented and unit-tested: BedrockOrchestratorFunction, RagIngestionFunction, RagEmbeddingFunction, RagRetrievalFunction, RagOrchestratorFunction
- Prompt builder Lambda layer implemented with reusable templates (layers/prompt_builder)
- RAG pipeline end-to-end: S3 ingestion through embedding, vector storage, retrieval, and prompt construction
- Bedrock Guardrails integration for content filtering and PII anonymization
- IAM least-privilege role design documented in architecture/iam-role-design.md
- FedRAMP High control mapping documented across 18 control families (FEDRAMP-ALIGNMENT.md)
- NIST AI RMF 1.0 full function coverage mapped in security/compliance-mapping.md
- Attack simulation scripts for five adversarial scenarios in security/attack-simulation/
- AWS GovCloud deployment configuration provided (terraform/govcloud.tfvars.example)
- Injection mitigation results documented in security/injection-mitigation-results.md
- SAM local testing fully configured with Makefile targets and sample events
- SBOM and dependency scanning via Dependabot enabled

### Verification

```bash
# Build and validate the SAM template
make sam-build
sam validate --lint

# Run unit tests for the Bedrock integration handler
cd lambda/bedrock_integration && python -m pytest tests/ -v

# Run RAG pipeline unit tests
cd rag/embedding && python -m pytest tests/ -v
cd rag/ingestion && python -m pytest tests/ -v
cd rag/retrieval && python -m pytest tests/ -v
cd rag/orchestrator && python -m pytest tests/ -v

# Run GenAI prompt builder tests
cd genai && python -m pytest tests/ -v

# Validate Terraform configuration
terraform init && terraform validate
```

---

## Project Structure

```
.
├── architecture/               # Architecture diagrams and design documents
│   ├── high-level-architecture.md
│   ├── iam-role-design.md
│   └── network-architecture.md
├── docs/                       # Developer guides
│   ├── local-testing.md
│   └── pii-redaction.md
├── events/                     # Sample event payloads for SAM local testing
├── genai/                      # Generative AI layer (Bedrock, guardrails, prompts)
│   ├── prompt_builder/
│   └── tests/
├── lambda/                     # Lambda function handlers
│   └── bedrock_integration/
├── layers/                     # Lambda layer sources
│   └── prompt_builder/
├── rag/                        # RAG pipeline implementation
│   ├── embedding/
│   ├── ingestion/
│   ├── orchestrator/
│   └── retrieval/
├── security/                   # Security configs, threat models, attack simulations
│   ├── attack-simulation/
│   ├── compliance-mapping.md
│   ├── iam-least-privilege-validation.md
│   └── injection-mitigation-results.md
├── terraform/                  # Infrastructure as Code modules
│   └── govcloud.tfvars.example
├── FEDRAMP-ALIGNMENT.md        # FedRAMP High control family mappings
├── Makefile                    # SAM build and invoke targets
├── ROADMAP.md                  # Project roadmap
├── samconfig.toml              # SAM deployment configuration
├── template.yaml               # SAM template (local testing)
└── README.md
```

---

## BE EASY ENTERPRISES Federal Portfolio

| Showcase Project | Repository | Description |
| --- | --- | --- |
| **Secure RAG Pipeline** | **[Secure-Generative-AI-Platform-on-AWS](https://github.com/dbsectrainer/Secure-Generative-AI-Platform-on-AWS)** | **This repo** |
| **DevSecOps CI/CD** | [dod-cybersec-ops-framework](https://github.com/dbsectrainer/dod-cybersec-ops-framework) | DoD 8570 / NIST RMF aligned pipeline |
| **Zero Trust Architecture** | [AEGIS](https://github.com/dbsectrainer/AEGIS) | FedRAMP High + NIST 800-207 Zero Trust |
| **FedRAMP Control Automation** | [nist_800_53_scanner](https://github.com/dbsectrainer/nist_800_53_scanner) | NIST 800-53 Rev 5 compliance scanner |
| **Federal AI Governance** | [ai-safety-governance](https://github.com/dbsectrainer/ai-safety-governance) | EO 14110 / OMB M-24-10 aligned |
| **CMMC 2.0 Dashboard** | [integrated-cyber-risk-compliance](https://github.com/dbsectrainer/integrated-cyber-risk-compliance) | CMMC 2.0 readiness assessment |
| **FedRAMP 30-Day Guide** | [cloud-security-best-practices](https://github.com/dbsectrainer/cloud-security-best-practices) | Day-by-day FedRAMP implementation roadmap |
| **Agentic AI Workflow** | [federal-doc-triage-agent](https://github.com/dbsectrainer/federal-doc-triage-agent) | Production-ready LangGraph + Bedrock triage agent |

---

## Author

**Donnivis Baker** — [github.com/dbsectrainer](https://github.com/dbsectrainer)
**BE EASY ENTERPRISES** — Federal IT Modernization & Cybersecurity

For questions, partnerships, or federal engagement inquiries, open an issue or reach out directly.

**Document Version:** 1.0 | **Last Updated:** 2026-06-15 | **FedRAMP High:** 92% Control Coverage (318/345)
