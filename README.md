# Secure Generative AI Platform on AWS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Terraform](https://img.shields.io/badge/Terraform-%3E%3D1.x-blueviolet)](https://www.terraform.io/)
[![AWS](https://img.shields.io/badge/AWS-Bedrock-orange)](https://aws.amazon.com/bedrock/)

> Production-Grade, Adversarially Resilient, DevSecOps-Enabled Architecture

## Overview

This project implements a secure, production-ready Generative AI platform on AWS using Amazon Bedrock, Retrieval-Augmented Generation (RAG), and a hardened cloud architecture.

The system is designed to demonstrate:

- Secure LLM integration
- RAG pipeline implementation
- Adversarial resilience (prompt injection, model abuse)
- IAM least-privilege enforcement
- DevSecOps automation
- Multi-account enterprise architecture
- Observability, governance, and cost controls

### Certification Alignment

| Certification                                             | Key Topics                                                                                       |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **AWS Certified Generative AI Developer -- Professional** | Bedrock integration, Guardrails, RAG architecture, Prompt security, Cost optimisation            |
| **AWS Certified DevOps Engineer -- Professional**         | CI/CD automation, Deployment strategies, Monitoring and rollback, Infrastructure as Code         |
| **AWS Certified Solutions Architect -- Professional**     | Multi-account design, Private networking, Encryption strategy, Disaster recovery, Cost modelling |

---

## Problem Statement

Organisations adopting generative AI require:

- Secure integration with proprietary data
- Protection against prompt injection and data leakage
- Controlled model access
- Auditable operations
- Automated deployment and rollback
- Cost and performance optimisation
- Regulatory compliance alignment

This platform addresses those requirements.

---

## High-Level Architecture

### Core Components

- **Amazon Bedrock** -- LLM inference
- **RAG Pipeline** -- S3, embeddings generation, vector database (OpenSearch Serverless / Aurora pgvector)
- **Lambda** -- Orchestration
- **API Gateway** -- Request routing
- **Cognito** -- Authentication
- **AWS WAF** -- Web application firewall
- **CodePipeline** -- CI/CD
- **Terraform** -- Infrastructure as Code
- **CloudWatch / CloudTrail / GuardDuty** -- Observability and threat detection
- **KMS** -- Encryption
- **Multi-account strategy** -- Environment isolation

### Architecture Domains

#### 1. Generative AI Layer

- Bedrock model selection strategy
- Prompt engineering patterns
- Guardrails configuration
- Token usage management
- Output moderation controls

#### 2. RAG Pipeline

- Secure document ingestion (S3)
- Embedding generation
- Vector storage
- Retrieval filtering
- Prompt construction
- Injection mitigation

#### 3. Security Architecture

- IAM least-privilege roles
- SCP enforcement (multi-account)
- Private VPC endpoints
- KMS CMK encryption
- TLS enforcement
- CloudTrail audit logging
- GuardDuty threat detection

#### 4. DevSecOps

- Terraform modules
- Automated security scanning
- ECR image scanning
- Canary deployments
- Blue/green deployment strategy
- Automatic rollback triggers

#### 5. Observability & Governance

- CloudWatch metrics and alarms
- X-Ray tracing
- Config rules
- IAM Access Analyzer
- Cost anomaly detection

---

## Threat Model

The system addresses the following threats using **STRIDE + MITRE ATT&CK** mapping:

- Prompt injection
- Data exfiltration
- Model abuse / excessive token consumption
- IAM misconfiguration
- Supply chain compromise
- Deployment misconfiguration
- Lateral movement risks

### Security Controls

| Threat               | Mitigation                               |
| -------------------- | ---------------------------------------- |
| Prompt Injection     | Input sanitisation + retrieval filtering |
| Data Leakage         | Private VPC endpoints + IAM boundaries   |
| Model Abuse          | Rate limiting + anomaly detection        |
| Data Tampering       | S3 versioning + checksum validation      |
| Privilege Escalation | Least privilege IAM + Access Analyzer    |
| Public Exposure      | Private API Gateway + WAF                |

---

## Repository Structure

```
.
├── architecture/    # Architecture diagrams and documentation
├── docs/            # Developer guides (local testing, etc.)
├── events/          # Sample event payloads for SAM local testing
├── genai/           # Generative AI layer (Bedrock, guardrails, prompts)
├── lambda/          # Lambda function handlers
├── layers/          # Lambda layer sources (prompt_builder)
├── rag/             # RAG pipeline implementation
├── security/        # Security configs, threat models, attack simulations
├── terraform/       # Infrastructure as Code modules
├── template.yaml    # SAM template (local testing only)
├── Makefile         # SAM build and invoke targets
├── ROADMAP.md       # Project roadmap
└── README.md
```

---

## Getting Started

### Prerequisites

- AWS Organisation (multi-account recommended)
- Terraform >= 1.x
- AWS CLI configured
- CodePipeline permissions
- Docker Desktop (for local Lambda testing)
- AWS SAM CLI >= 1.100.0 (for local Lambda testing)

### Deploy Infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### Local Testing with SAM CLI

Test Lambda functions locally without deploying to AWS. Requires Docker and SAM CLI.

```bash
# Build all functions and the Lambda layer
make sam-build

# Invoke a single function with a sample event
make sam-invoke-bedrock

# Start a local API Gateway on port 3000
make sam-api
```

Available invoke targets: `sam-invoke-bedrock`, `sam-invoke-ingestion`, `sam-invoke-embedding`, `sam-invoke-retrieval`, `sam-invoke-rag`.

See [docs/local-testing.md](docs/local-testing.md) for full documentation including API endpoints, environment configuration, debugging, and known limitations.

---

## Testing Scenarios

This platform includes simulation scripts for:

- Prompt injection attack
- Token abuse attack
- IAM misconfiguration scenario
- Region outage simulation
- Canary failure triggering rollback

---

## Cost Considerations

**Cost drivers:**

- Bedrock usage metered by tokens
- OpenSearch Serverless compute units
- Lambda invocation charges
- CloudWatch logging volume

**Cost controls implemented:**

- Token caps
- Log retention policies
- Alarm-based anomaly detection
- Budget alerts

---

## Future Enhancements

- Model signing & verification
- Differential privacy in embeddings
- Automated compliance reporting
- Multi-region active-active deployment
- Chaos engineering integration

---

## Contributing

Contributions are welcome. Please read the [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

## Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). Do not open a public issue.

## License

This project is licensed under the [MIT License](LICENSE).
