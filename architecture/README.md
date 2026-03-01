# Architecture

This directory contains all architecture artefacts for the Secure Generative AI Platform on AWS.

## Contents

| File | Description |
|------|-------------|
| [high-level-architecture.md](high-level-architecture.md) | High-level diagram description covering multi-account structure, Bedrock integration, RAG components, private VPC endpoints, WAF + API Gateway, monitoring services, and CI/CD pipeline |
| [network-architecture.md](network-architecture.md) | Detailed network architecture: subnet layout, NAT usage justification, security groups, NACL strategy, interface VPC endpoints, and route tables |
| [iam-role-design.md](iam-role-design.md) | IAM role design: role boundaries, explicit deny strategy, privilege escalation prevention, and SCP enforcement outline |

## Architecture Domains

1. **Generative AI Layer** – Bedrock model selection, prompt engineering, guardrails, token management
2. **RAG Pipeline** – Secure document ingestion, embedding generation, vector storage, retrieval filtering
3. **Security Architecture** – IAM least-privilege, SCP enforcement, private VPC endpoints, KMS CMK encryption
4. **DevSecOps** – Terraform modules, automated security scanning, CI/CD pipeline
5. **Observability & Governance** – CloudWatch metrics, X-Ray tracing, Config rules, IAM Access Analyzer
