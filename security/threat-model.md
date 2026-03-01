# Formal Threat Model – Secure Generative AI Platform on AWS

**Methodology:** STRIDE + MITRE ATT&CK for Enterprise / ATLAS  
**Version:** 1.0  
**Date:** 2026-03-01  
**Status:** Approved

---

## 1. Scope

This threat model covers the Secure Generative AI Platform deployed on AWS, including:

- Amazon Bedrock (LLM inference endpoint)
- RAG pipeline (ingestion → embedding → vector store → retrieval → orchestration)
- API Gateway (public-facing entry point)
- Lambda functions (orchestration, embedding, ingestion, retrieval)
- OpenSearch Serverless (vector database)
- S3 (document store)
- IAM roles, KMS, VPC endpoints, WAF, GuardDuty, and AWS Config

---

## 2. Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Internet / Client                                                          │
│  (Untrusted)                                                                │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ HTTPS (TLS 1.2+)
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AWS Perimeter (WAF + API Gateway + Cognito)  [TRUST BOUNDARY 1]           │
│  • AWS WAF: rate limiting, injection blocking, geo-blocking                 │
│  • API Gateway: throttling, mTLS, usage plans                               │
│  • Cognito: authentication, JWT validation                                  │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ Authenticated, WAF-filtered requests
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Application Layer – Private VPC  [TRUST BOUNDARY 2]                       │
│  • Lambda orchestrator (private subnet, SG-restricted)                      │
│  • Prompt sanitisation layer                                                │
│  • RAG pipeline components                                                  │
│  (No direct internet access; AWS services via VPC endpoints)                │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ VPC interface/gateway endpoints only
                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AWS Service Layer  [TRUST BOUNDARY 3]                                      │
│  • Bedrock (inference, guardrails)                                          │
│  • OpenSearch Serverless (vector store)                                     │
│  • S3 (document bucket)                                                     │
│  • KMS (key management)                                                     │
│  • CloudWatch / CloudTrail / GuardDuty                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow Diagram

```
User Request
     │
     ▼
[API Gateway + WAF]
     │  JWT validated / WAF rules applied
     ▼
[Lambda Orchestrator] ──── sanitise_query() ──▶ [Bedrock Guardrails]
     │                                                    │
     │  Sanitised query                                   │ Blocked if injection
     ▼                                                    ▼
[Retrieval Lambda] ────▶ [OpenSearch Serverless]   [Response blocked]
     │  k-NN search + metadata filter
     │  Retrieved chunks
     ▼
[Prompt Builder]
     │  Context-bounded prompt
     ▼
[Bedrock Claude] ──▶ [Response] ──▶ [Guardrail output filter]
     │                                          │
     ▼                                          ▼
[Structured Response]                   [Blocked / Anonymised]
     │
     ▼
[API Gateway Response] ──▶ User

Parallel flows:
  └─ S3 (document ingest) ──▶ [Ingestion Lambda] ──▶ [Embedding Lambda] ──▶ OpenSearch
  └─ All actions ──▶ CloudTrail / CloudWatch / GuardDuty (audit & detection)
```

---

## 4. STRIDE Threat Analysis

### 4.1 Spoofing

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| S-01  | API Gateway            | Attacker impersonates a valid user (stolen JWT)            | Medium     | High   | High   |
| S-02  | Lambda IAM Role        | Confused deputy attack – Lambda role assumed by attacker   | Low        | High   | Medium |
| S-03  | Bedrock endpoint       | Attacker spoofs Bedrock response in transit                | Very Low   | High   | Low    |

### 4.2 Tampering

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| T-01  | S3 document store      | Malicious document injected to poison retrieval corpus     | Medium     | High   | High   |
| T-02  | OpenSearch index       | Vector embeddings overwritten to manipulate retrieval      | Low        | High   | Medium |
| T-03  | Prompt payload         | Prompt injection to override system instructions           | High       | High   | Critical |
| T-04  | Lambda code            | Supply chain compromise (malicious dependency)             | Low        | Critical | High  |

### 4.3 Repudiation

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| R-01  | API calls              | User denies making a request (no audit trail)              | Medium     | Medium | Medium |
| R-02  | Model responses        | Inability to audit what was sent to/from Bedrock           | Low        | High   | Medium |

### 4.4 Information Disclosure

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| I-01  | S3 documents           | Public bucket misconfiguration exposes documents           | Medium     | Critical | Critical |
| I-02  | Model output           | Model reveals PII or confidential content in response      | Medium     | High   | High   |
| I-03  | System prompt          | Prompt extraction attack reveals internal instructions     | Medium     | High   | High   |
| I-04  | CloudWatch logs        | Excessive logging exposes user queries / PII               | Medium     | Medium | Medium |
| I-05  | IAM credentials        | Over-privileged role leaks access keys via metadata service | Low       | Critical | High  |

### 4.5 Denial of Service

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| D-01  | Bedrock endpoint       | Token flooding exhausts model quota / incurs costs         | High       | High   | Critical |
| D-02  | Lambda orchestrator    | Concurrent invocation flood overwhelms concurrency limits  | Medium     | High   | High   |
| D-03  | OpenSearch Serverless  | Expensive vector search queries exhaust compute units      | Medium     | Medium | Medium |

### 4.6 Elevation of Privilege

| ID    | Asset                  | Threat                                                     | Likelihood | Impact | Risk   |
|-------|------------------------|------------------------------------------------------------|------------|--------|--------|
| E-01  | IAM roles              | Over-privileged Lambda role enables lateral movement       | Medium     | Critical | Critical |
| E-02  | SCP boundaries         | Missing SCP allows creation of admin roles in child account | Low       | Critical | High  |
| E-03  | Bedrock guardrails     | Jailbreak bypasses content moderation to elevate AI scope  | Medium     | High   | High   |

---

## 5. MITRE ATT&CK / ATLAS Mapping

| STRIDE ID | MITRE Technique         | Technique ID         | Description                                         |
|-----------|-------------------------|----------------------|-----------------------------------------------------|
| T-03      | Prompt Injection         | AML.T0051            | Adversarial inputs manipulate LLM behaviour         |
| T-03      | Indirect Prompt Injection | AML.T0051.000       | Injected via retrieved document corpus              |
| I-02      | Data Exfiltration        | T1567                | Model reveals sensitive data in outputs             |
| D-01      | Resource Hijacking       | T1496                | Token flooding for cost exhaustion / DoS            |
| E-01      | Valid Accounts           | T1078                | Abuse of over-privileged IAM role                   |
| E-01      | Cloud Admin Access       | T1098.003            | Privilege escalation via IAM policy manipulation    |
| T-01      | Supply Chain Compromise  | T1195                | Malicious document poisons retrieval corpus         |
| T-04      | Software Supply Chain    | T1195.001            | Malicious Lambda dependency                         |
| I-01      | Data from Cloud Storage  | T1530                | S3 public exposure / bucket policy misconfiguration |
| I-03      | Exfiltration via API     | T1041                | System prompt leak through model output             |

---

## 6. Risk Matrix

```
                     IMPACT
              Low    Medium    High    Critical
          ┌────────┬─────────┬───────┬──────────┐
Very High │        │         │       │          │
          ├────────┼─────────┼───────┼──────────┤
High      │        │  R-01   │ S-01  │  D-01    │  <- T-03, E-01
          ├────────┼─────────┼───────┼──────────┤
LIKELIHOOD│        │  D-03   │ I-02  │  T-01    │
Medium    │        │  R-02   │ I-03  │  I-01    │
          │        │         │ D-02  │          │
          ├────────┼─────────┼───────┼──────────┤
Low       │        │         │ S-02  │  T-04    │
          │        │         │ T-02  │  E-02    │
          │        │         │ I-05  │          │
          ├────────┼─────────┼───────┼──────────┤
Very Low  │        │         │ S-03  │          │
          └────────┴─────────┴───────┴──────────┘

CRITICAL RISKS (immediate action required): T-03, E-01, D-01, I-01
HIGH RISKS (priority mitigations applied):  S-01, I-02, I-03, T-04, E-02, E-03, D-02
```

---

## 7. Residual Risk Statement

The following residual risks remain after all controls are implemented:

| Risk ID | Residual Risk                                              | Accepted By      | Review Date |
|---------|------------------------------------------------------------|------------------|-------------|
| T-03-R  | Novel prompt injection variants not yet in pattern library | Security Lead    | 2026-06-01  |
| D-01-R  | Token quota exhaustion despite rate limiting (burst)       | Platform Owner   | 2026-06-01  |
| E-03-R  | Advanced jailbreak techniques bypassing guardrails         | AI Safety Lead   | 2026-06-01  |
| T-04-R  | Zero-day vulnerability in third-party Lambda dependencies  | DevSecOps Lead   | 2026-06-01  |
| I-01-R  | S3 misconfiguration risk during IaC deployment             | Cloud Architect  | 2026-06-01  |

Residual risks are accepted with the following compensating controls active:
- Continuous GuardDuty monitoring for anomalous API call patterns
- CloudTrail audit logging with 90-day retention and integrity validation
- Monthly Access Analyzer scans for public resource exposure
- Quarterly red team exercises including prompt injection simulation
- Dependency scanning in CI/CD pipeline (Dependabot + SAST)

---

## 8. Out of Scope

- Physical data centre security (AWS shared responsibility model)
- Client-side browser/application security
- Third-party SaaS integrations not part of this architecture
