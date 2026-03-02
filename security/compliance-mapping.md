# Compliance Mapping – Secure Generative AI Platform on AWS

**Version:** 1.0  
**Date:** 2026-03-01  
**Frameworks Covered:** NIST AI RMF 1.0, NIST SP 800-53 Rev 5, AWS Well-Architected Framework (Security Pillar), SOC 2 Type II

---

## 1. NIST AI Risk Management Framework (AI RMF 1.0)

### GOVERN Function

| AI RMF Practice                                                  | Implementation                                                                     | Evidence Location                                   |
|------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------------------------|
| GOVERN 1.1 – Policies for AI risk management                     | Threat model and security control matrix define risk governance posture            | `security/threat-model.md`, `security/security-control-matrix.md` |
| GOVERN 1.2 – AI risk tolerance defined                           | Residual risk statements with acceptance criteria per risk owner                   | `security/threat-model.md` §7                       |
| GOVERN 1.3 – Organisational teams assigned AI risk roles         | Security Lead, Platform Owner, AI Safety Lead, DevSecOps Lead identified           | `security/threat-model.md` §7                       |
| GOVERN 2.2 – Personnel trained on AI risk                        | Attack simulation scripts provide hands-on red team training                       | `security/attack-simulation/`                       |
| GOVERN 5.1 – Policies to address AI system lifecycle             | CI/CD pipeline with SAST, dependency scanning, canary deployments                  | `terraform/modules/`, ROADMAP.md                   |
| GOVERN 6.1 – Policies address third-party risks                  | Dependency pinning, Dependabot, ECR image scanning for Lambda runtimes             | GitHub Actions workflow                             |

### MAP Function

| AI RMF Practice                                                  | Implementation                                                                     | Evidence Location                                   |
|------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------------------------|
| MAP 1.1 – Context established for AI system                      | Architecture domains documented: GenAI layer, RAG pipeline, security architecture  | `architecture/`, `README.md`                       |
| MAP 1.5 – Organisational risk priorities documented              | STRIDE risk matrix with likelihood × impact ratings                                | `security/threat-model.md` §6                       |
| MAP 2.1 – Scientific findings about AI risks are reviewed        | MITRE ATLAS mapping for AI-specific attack techniques                              | `security/threat-model.md` §5                       |
| MAP 3.5 – Negative impacts identified and documented             | Information disclosure, prompt injection, model abuse threats modelled             | `security/threat-model.md` §4                       |
| MAP 5.1 – Likelihood and impact of AI risks are assessed         | Full risk matrix with Critical/High/Medium/Low ratings                             | `security/threat-model.md` §6                       |

### MEASURE Function

| AI RMF Practice                                                  | Implementation                                                                     | Evidence Location                                   |
|------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------------------------|
| MEASURE 1.1 – Metrics for AI risk identified                     | Token usage, error rates, injection detection count, GuardDuty findings count      | `genai/token-cost-baseline.md`, CloudWatch alarms  |
| MEASURE 2.2 – AI system evaluated for trustworthiness            | Bedrock Guardrails content evaluation, injection simulation test suite             | `security/attack-simulation/`, `genai/tests/`       |
| MEASURE 2.5 – Privacy risks evaluated                            | PII detection and anonymisation via Bedrock Guardrails                             | `terraform/modules/bedrock/main.tf`                |
| MEASURE 2.6 – AI bias/explainability evaluated                   | Citation mode prompt template provides source attribution                          | `genai/prompt_builder/templates.py`                |
| MEASURE 4.1 – Measurement of risk is used for decision-making    | Residual risk statement drives security review cadence                             | `security/threat-model.md` §7                       |

### MANAGE Function

| AI RMF Practice                                                  | Implementation                                                                     | Evidence Location                                   |
|------------------------------------------------------------------|------------------------------------------------------------------------------------|-----------------------------------------------------|
| MANAGE 1.1 – Risks are prioritised and addressed                 | Critical risks (T-03, E-01, D-01, I-01) have immediate mitigations applied        | `security/security-control-matrix.md`              |
| MANAGE 2.2 – Incident response processes defined                 | SNS alerting, Lambda DLQ, GuardDuty findings triggers automated response           | `terraform/modules/security/`                      |
| MANAGE 3.1 – AI risk responses include monitoring                | CloudWatch alarms, GuardDuty, Access Analyzer continuous monitoring                | `terraform/modules/security/`                      |
| MANAGE 4.1 – Residual risks documented and accepted              | Residual risk statement with owners and review dates                               | `security/threat-model.md` §7                       |

---

## 2. NIST SP 800-53 Rev 5 Control Mapping

### Access Control (AC)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| AC-2           | Account Management                                   | IAM users managed via AWS SSO; service accounts are IAM roles only    |
| AC-3           | Access Enforcement                                   | IAM least-privilege policies per Lambda function                       |
| AC-4           | Information Flow Enforcement                         | VPC security groups restrict Lambda → VPC endpoint → AWS service flows |
| AC-6           | Least Privilege                                      | Lambda roles scoped to specific S3 buckets, Bedrock models, OpenSearch |
| AC-17          | Remote Access                                        | No SSH; all access via VPC endpoints or AWS Console with MFA           |

### Audit and Accountability (AU)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| AU-2           | Event Logging                                        | CloudTrail: management events + Bedrock data events + S3 data events   |
| AU-3           | Content of Audit Records                             | CloudTrail records: who, what, when, from where, outcome               |
| AU-9           | Protection of Audit Information                      | CloudTrail log file integrity validation; separate S3 log bucket        |
| AU-11          | Audit Record Retention                               | CloudTrail S3 bucket with 90-day retention; CloudWatch 30-day retention |

### Configuration Management (CM)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| CM-2           | Baseline Configuration                               | Terraform IaC defines all infrastructure; state stored in encrypted S3 |
| CM-6           | Configuration Settings                               | AWS Config rules enforce: S3 no-public-read, IAM password policy, etc. |
| CM-7           | Least Functionality                                  | Lambda functions have only required permissions; no admin access        |
| CM-8           | Component Inventory                                  | Terraform state + AWS Config resource inventory                        |

### Identification and Authentication (IA)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| IA-2           | Identification and Authentication (Org Users)        | AWS SSO + MFA enforced via SCP for console access                      |
| IA-3           | Device Identification                                | Lambda IAM roles with resource-based conditions (aws:SourceArn)        |
| IA-5           | Authenticator Management                             | Cognito manages JWT issuance and rotation; no long-lived credentials   |

### System and Communications Protection (SC)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| SC-5           | Denial of Service Protection                         | WAF rate limiting; Lambda reserved concurrency; API Gateway throttling |
| SC-7           | Boundary Protection                                  | VPC with private subnets; security groups; NACLs; WAF on API Gateway  |
| SC-8           | Transmission Confidentiality and Integrity           | TLS 1.2+ on all connections; VPC endpoints eliminate internet transit  |
| SC-12          | Cryptographic Key Establishment and Management       | AWS KMS CMK per service; automatic key rotation enabled                |
| SC-28          | Protection of Information at Rest                    | S3 SSE-KMS; OpenSearch at-rest encryption; CloudWatch KMS encryption   |

### System and Information Integrity (SI)

| Control        | Description                                          | Implementation                                                         |
|----------------|------------------------------------------------------|------------------------------------------------------------------------|
| SI-3           | Malware Protection                                   | GuardDuty Malware Protection for S3; ECR image scanning                |
| SI-4           | System Monitoring                                    | GuardDuty; CloudWatch anomaly alarms; CloudTrail                       |
| SI-10          | Information Input Validation                         | `sanitise_query()` regex + Bedrock Guardrails PROMPT_ATTACK filter     |
| SI-12          | Information Management and Retention                 | S3 versioning + lifecycle policies; CloudWatch log retention policies  |

---

## 3. Encryption Controls

### Encryption at Rest

| Data Store                   | Encryption Method           | Key Management                        |
|------------------------------|-----------------------------|---------------------------------------|
| S3 document bucket           | SSE-KMS (aws:kms)           | Customer-managed KMS CMK; key rotation enabled |
| OpenSearch Serverless        | KMS encryption policy       | Customer-managed KMS CMK              |
| CloudWatch Log Groups        | KMS log group encryption    | Customer-managed KMS CMK              |
| DynamoDB (session state)     | SSE-KMS                     | Customer-managed KMS CMK              |
| Terraform remote state (S3)  | SSE-KMS                     | Customer-managed KMS CMK              |

### Encryption in Transit

| Connection                           | Protocol                    | Enforcement Method                    |
|--------------------------------------|-----------------------------|---------------------------------------|
| Client → API Gateway                 | TLS 1.2+ (minimum)          | API Gateway TLS policy                |
| Lambda → AWS services                | TLS 1.2+ via VPC endpoints  | VPC interface endpoint private DNS    |
| Lambda → OpenSearch Serverless       | TLS 1.2+ via VPC endpoint   | OpenSearch VPC-only network policy    |
| Lambda → Bedrock                     | TLS 1.2+ via VPC endpoint   | Bedrock interface VPC endpoint        |
| Lambda → S3                          | TLS via S3 gateway endpoint | S3 bucket policy `aws:SecureTransport`|

---

## 4. Data Protection Controls

| Control Area         | Implementation                                                                   | Scope                                      |
|----------------------|----------------------------------------------------------------------------------|--------------------------------------------|
| Data Classification  | Documents tagged on ingestion (Confidential/Internal/Public)                     | S3 object metadata                         |
| PII Handling         | Bedrock Guardrails anonymise EMAIL, NAME, PHONE; block AWS_ACCESS_KEY            | Model input and output                     |
| Data Minimisation    | Retrieval scoped to query-relevant chunks only (metadata filter)                 | OpenSearch k-NN retrieval                  |
| Data Residency       | Single-region deployment by default; no cross-region replication of user data    | `var.region` enforced in all modules       |
| Data Retention       | CloudWatch: 30 days; CloudTrail S3: 90 days; document S3: versioned + lifecycle  | Per-service retention policies             |
| Right to Erasure     | S3 versioning + object expiry; OpenSearch document deletion API                  | Manual process + lifecycle                 |

---

## 5. AWS Well-Architected Framework – Security Pillar Alignment

| Security Pillar Best Practice                         | Status      | Implementation                                             |
|-------------------------------------------------------|-------------|-------------------------------------------------------------|
| SEC 1 – Operate your workload using security design principles | ✅ | Defence-in-depth, least privilege, encryption everywhere |
| SEC 2 – Manage identities for people and machines     | ✅          | Cognito + IAM roles; no IAM users for services             |
| SEC 3 – Manage permissions for people and machines    | ✅          | Least-privilege per Lambda; Access Analyzer; SCPs           |
| SEC 4 – Detect and investigate security events        | ✅          | GuardDuty + CloudTrail + CloudWatch + Access Analyzer       |
| SEC 5 – Protect network resources                     | ✅          | VPC private subnets + SGs + NACLs + VPC endpoints + WAF    |
| SEC 6 – Protect compute resources                     | ✅          | Lambda in VPC; IMDSv2; no public IPs; reserved concurrency  |
| SEC 7 – Classify your data                            | ⚠️ Partial  | S3 tagging in place; formal data catalogue pending          |
| SEC 8 – Protect your data at rest                     | ✅          | KMS CMK encryption for all data stores                     |
| SEC 9 – Protect your data in transit                  | ✅          | TLS 1.2+ + VPC endpoints; S3 SecureTransport policy        |
| SEC 10 – Anticipate, respond and recover from incidents | ✅        | SNS alerting; GuardDuty findings; Lambda DLQ; IaC rollback  |
