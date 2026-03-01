# High-Level Architecture

## Overview

The Secure Generative AI Platform on AWS is deployed across a multi-account AWS Organisation structure with three accounts: **Dev**, **Prod**, and **Security**. All workloads are isolated within private VPCs and communicate with AWS services exclusively through Interface VPC Endpoints.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AWS Organisation                                    │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐  │
│  │  Dev Account │    │ Prod Account │    │      Security Account        │  │
│  │              │    │              │    │  CloudTrail (org)             │  │
│  │  VPC (Dev)   │    │  VPC (Prod)  │    │  GuardDuty (org delegated)   │  │
│  │  Bedrock     │    │  Bedrock     │    │  Security Hub (aggregator)   │  │
│  │  Lambda      │    │  Lambda      │    │  Config (aggregator)         │  │
│  │  S3          │    │  S3          │    │  IAM Access Analyzer         │  │
│  └──────────────┘    └──────────────┘    └──────────────────────────────┘  │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Management / Root Account                           │ │
│  │     AWS Organizations SCPs   |   AWS SSO / IAM Identity Center        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Multi-Account Strategy

| Account | Purpose | Key Services |
|---------|---------|--------------|
| **Management** | Organisation root, SCPs, consolidated billing, AWS SSO | AWS Organizations, IAM Identity Center |
| **Dev** | Development and testing workloads | VPC, Bedrock, Lambda, S3, API Gateway, CodePipeline |
| **Prod** | Production workloads with stricter controls | VPC, Bedrock, Lambda, S3, API Gateway, WAF, CloudFront |
| **Security** | Centralised security monitoring | CloudTrail (org-wide), GuardDuty, Security Hub, Config, IAM Access Analyzer |

## Core Component Interactions

```
Users / Clients
      │
      ▼
┌───────────────┐
│  AWS WAF      │  ← DDoS protection, rate limiting, prompt-injection rules
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  API Gateway  │  ← Private REST API (VPC endpoint), Cognito authoriser
│  (Private)    │
└───────┬───────┘
        │
        ▼
┌───────────────┐          ┌──────────────────────┐
│  Lambda       │─────────▶│  Amazon Bedrock       │
│  Orchestrator │          │  (via VPC endpoint)   │
└───────┬───────┘          └──────────────────────┘
        │                         ▲
        │                         │  RAG context
        ▼                         │
┌───────────────┐          ┌──────────────────────┐
│  OpenSearch   │◀─────────│  Embedding Lambda     │
│  Serverless   │          │  (Bedrock Titan)      │
│  (Vector DB)  │          └──────────────────────┘
└───────────────┘                 ▲
                                  │  Source documents
                           ┌──────────────────────┐
                           │  S3 Document Store    │
                           │  (KMS CMK encrypted,  │
                           │   versioning enabled) │
                           └──────────────────────┘
```

## Security Boundary

All compute (Lambda) and data services (S3, OpenSearch) operate within a private VPC. External AWS service calls (Bedrock, S3, KMS, CloudWatch) are routed through Interface VPC Endpoints, ensuring no traffic traverses the public internet.

```
┌──────────────────────────────────────────────────────────────────┐
│  VPC (10.0.0.0/16)                                               │
│                                                                  │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐   │
│  │  Private Subnets        │  │  Interface VPC Endpoints     │   │
│  │  (Lambda, OpenSearch)   │  │  ● com.amazonaws.*.bedrock   │   │
│  │                         │  │  ● com.amazonaws.*.s3        │   │
│  │  ┌──────────────────┐   │  │  ● com.amazonaws.*.kms       │   │
│  │  │  Lambda          │───┼──│  ● com.amazonaws.*.logs      │   │
│  │  │  Orchestrator    │   │  │  ● com.amazonaws.*.execute-  │   │
│  │  └──────────────────┘   │  │    api                       │   │
│  └─────────────────────────┘  └─────────────────────────────┘   │
│                                                                  │
│  No IGW attached to private subnets. NAT Gateway in public       │
│  subnets for outbound-only egress (third-party integrations).    │
└──────────────────────────────────────────────────────────────────┘
```

## CI/CD Pipeline

```
Developer Push
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  CodeCommit │───▶│ CodeBuild    │───▶│ CodeBuild    │───▶│CodeDeploy  │
│  / GitHub   │    │ (Lint +      │    │ (terraform   │    │(Lambda     │
│             │    │  tfsec +     │    │  plan/apply) │    │ canary)    │
│             │    │  Checkov)    │    │              │    │            │
└─────────────┘    └──────────────┘    └──────────────┘    └────────────┘
                          │                    │
                   Security gate         Manual approval
                   (blocks on HIGH)      (Prod only)
```

## Monitoring & Observability

- **CloudTrail** – All API calls logged to centralised Security account S3 bucket (org-wide trail)
- **CloudWatch** – Lambda duration, error rate, Bedrock token usage, cost anomaly alarms
- **AWS X-Ray** – Distributed tracing across Lambda and API Gateway
- **GuardDuty** – Threat detection for VPC flow logs, CloudTrail events, S3 access patterns
- **Config** – Continuous compliance checking against required-tags, encrypted-volumes, restricted-ssh rules
- **Security Hub** – Aggregated findings from GuardDuty, Config, Inspector, Macie
