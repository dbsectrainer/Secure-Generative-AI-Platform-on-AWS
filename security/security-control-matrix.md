# Security Control Matrix

**Version:** 1.0  
**Date:** 2026-03-01  
**Reference:** [Threat Model](./threat-model.md)

This matrix maps each identified threat to its corresponding controls, AWS services, implementation layer, and residual risk rating.

---

## Control Matrix

| Threat ID | Threat Description                          | Control Type       | Control Description                                          | AWS Service / Implementation                                     | Residual Risk |
|-----------|---------------------------------------------|--------------------|--------------------------------------------------------------|------------------------------------------------------------------|---------------|
| S-01      | Stolen JWT impersonation                    | Preventive         | JWT expiry (1 h), refresh token rotation, Cognito advanced security | Amazon Cognito + API Gateway authoriser                     | Low           |
| S-02      | Confused deputy on Lambda IAM role          | Preventive         | `aws:SourceArn` / `aws:SourceAccount` condition on trust policies | IAM role trust policy conditions                            | Low           |
| S-03      | Bedrock response spoofing in transit        | Preventive         | TLS 1.2+ enforced on all VPC endpoint connections            | VPC interface endpoints + TLS policy                             | Very Low      |
| T-01      | Malicious document poisons RAG corpus       | Preventive/Detective | S3 object integrity checksums; document scanning before ingestion; restricted upload IAM policy | S3 + Lambda pre-ingestion validation + GuardDuty Malware Protection | Medium |
| T-02      | Vector embedding overwrite                  | Preventive         | OpenSearch data access policy scoped to ingestion Lambda only; no direct public access | OpenSearch Serverless data policy + VPC-only network policy | Low           |
| T-03      | Prompt injection                            | Preventive/Detective | Multi-layer: regex sanitisation (builder.py) + Bedrock Guardrails PROMPT_ATTACK + WAF injection rules | `sanitise_query()` + `aws_bedrock_guardrail` + AWS WAF      | Medium        |
| T-04      | Supply chain compromise (Lambda dependency) | Preventive/Detective | Dependency pinning, Dependabot alerts, CodeGuru Reviewer, ECR image scanning | GitHub Actions + CodeGuru + ECR                             | Low           |
| R-01      | Request repudiation (no audit trail)        | Detective          | CloudTrail with log file integrity validation + S3 log bucket | CloudTrail (management + data events)                            | Low           |
| R-02      | Bedrock call unaudited                      | Detective          | CloudTrail data events for Bedrock + CloudWatch Lambda logs  | CloudTrail + CloudWatch Logs                                     | Low           |
| I-01      | S3 public bucket misconfiguration           | Preventive/Detective | Block public access at account level; bucket policy denies non-VPC access; AWS Config rule `s3-bucket-public-read-prohibited` | S3 Block Public Access + AWS Config + Access Analyzer        | Very Low      |
| I-02      | PII / confidential content in model output  | Preventive         | Bedrock Guardrails PII anonymisation (EMAIL, NAME, PHONE, AWS keys) | `aws_bedrock_guardrail` sensitive_information_policy_config  | Low           |
| I-03      | System prompt extraction                    | Preventive         | Restricted system prompt with explicit injection-resistance language; Bedrock Guardrails | `RESTRICTED_SYSTEM_PROMPT` in `builder.py` + Bedrock Guardrails | Medium      |
| I-04      | PII leakage in CloudWatch logs              | Preventive         | Log sanitisation in Lambda handlers; CloudWatch log encryption with KMS CMK | KMS CMK log group encryption + structured logging            | Low           |
| I-05      | Over-privileged role leaks credentials      | Preventive/Detective | Least-privilege IAM; IMDSv2 enforcement; Access Analyzer continuous monitoring | IAM Access Analyzer + AWS Config `iam-no-inline-policy` rule | Low          |
| D-01      | Token flooding / cost exhaustion            | Preventive         | WAF rate limiting (1000 req/5 min/IP); Lambda reserved concurrency; Bedrock token cap; Budget alarm | AWS WAF rate rule + Lambda `reserved_concurrent_executions` + AWS Budgets | Medium |
| D-02      | Lambda concurrency flood                    | Preventive         | Reserved concurrency caps; SQS queue with dead-letter + backoff; CloudWatch alarm on throttles | Lambda concurrency + SQS DLQ + CloudWatch alarm              | Low           |
| D-03      | OpenSearch compute unit exhaustion          | Detective/Responsive | CloudWatch alarm on SearchableDocuments + query timeouts; auto-scaling OCU limits | OpenSearch Serverless + CloudWatch + alarm actions           | Low           |
| E-01      | Over-privileged Lambda enables lateral movement | Preventive    | Least-privilege IAM roles per Lambda function; IAM permission boundaries; SCP denying privilege escalation | IAM least-privilege + SCP `DenyIAMEscalation` + Access Analyzer | Low       |
| E-02      | Missing SCP allows admin role creation      | Preventive         | SCP `DenyIAMAdminActions` applied to all non-management accounts | AWS Organizations + SCP                                      | Low           |
| E-03      | Jailbreak bypasses guardrails               | Preventive/Detective | Bedrock Guardrails HIGH strength on all categories; GuardDuty anomaly detection; red team quarterly | Bedrock Guardrails + GuardDuty + WAF                         | Medium        |

---

## AWS Security Services Summary

| AWS Service              | Controls Addressed                                         | Configuration Reference                              |
|--------------------------|------------------------------------------------------------|------------------------------------------------------|
| Amazon Cognito           | S-01 (authentication)                                      | API Gateway authoriser, advanced security mode       |
| AWS WAF                  | T-03, D-01, E-03 (injection blocking, rate limiting)       | `terraform/modules/waf/`                             |
| AWS IAM                  | S-02, I-05, E-01, E-02 (least-privilege, boundaries)       | `terraform/modules/iam/`                             |
| Amazon Bedrock Guardrails| T-03, I-02, I-03, E-03 (content filtering, PII)           | `terraform/modules/bedrock/`                         |
| AWS KMS                  | I-04, I-05 (encryption at rest for logs, S3, OpenSearch)   | CMK per service with key policy                      |
| Amazon GuardDuty         | T-01, I-05, E-01 (threat detection, anomaly)               | `terraform/modules/security/`                        |
| AWS Config               | I-01, I-05, E-01 (compliance rules, continuous assessment) | `terraform/modules/security/`                        |
| IAM Access Analyzer      | I-01, I-05, E-01 (public access, external access findings) | `terraform/modules/security/`                        |
| AWS CloudTrail           | R-01, R-02 (audit logging, integrity)                      | Management + data events, log file validation        |
| VPC Interface Endpoints  | S-03, T-02, I-01 (private traffic, no internet routing)    | `terraform/modules/network/`                         |
| S3 Block Public Access   | I-01 (prevents public bucket exposure)                     | Account-level block public access                    |
| AWS Budgets / Alarms     | D-01 (cost anomaly, token flood detection)                 | Budget alert + CloudWatch alarms                     |
| AWS Organizations / SCP  | E-02 (privilege escalation prevention)                     | `terraform/modules/iam/`                             |

---

## Defence-in-Depth Layers

```
Layer 1 – Perimeter:    WAF (rate limit, injection rules) + Cognito AuthN/AuthZ
Layer 2 – Transport:    TLS 1.2+ enforced on all endpoints and VPC endpoint connections
Layer 3 – Application:  sanitise_query() regex patterns + Bedrock Guardrails
Layer 4 – Data:         KMS encryption at rest (S3, OpenSearch, CloudWatch, DynamoDB)
Layer 5 – Identity:     Least-privilege IAM + permission boundaries + SCPs
Layer 6 – Detection:    GuardDuty + CloudTrail + CloudWatch alarms + Access Analyzer
Layer 7 – Response:     SNS alerting + Lambda reserved concurrency + DLQ backoff
```
