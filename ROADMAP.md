# Project Roadmap

> Secure Generative AI Platform on AWS

---

## Phase 1 -- Foundations (Weeks 1--3)

**Objectives**

- Define architecture
- Establish AWS accounts
- Create Terraform baseline
- Implement basic Bedrock integration

**Deliverables**

- Architecture diagram
- IAM role design
- Initial Bedrock API integration
- Secure S3 document ingestion

---

## Phase 2 -- RAG Implementation (Weeks 4--6)

**Objectives**

- Build embedding pipeline
- Implement vector database
- Construct retrieval workflow
- Implement prompt construction logic

**Deliverables**

- Functional RAG system
- Retrieval filtering
- Performance benchmarking
- Token cost baseline

---

## Phase 3 -- Security Hardening (Weeks 7--9)

**Objectives**

- Threat modelling
- Prompt injection simulation
- Implement input validation
- Configure WAF rules
- Enforce private VPC endpoints
- Enable GuardDuty + Config

**Deliverables**

- Threat model document
- Security control matrix
- Injection mitigation results
- IAM least-privilege validation

---

## Phase 4 -- DevSecOps Automation (Weeks 10--12)

**Objectives**

- CI/CD pipeline creation
- Automated Terraform validation
- Security scanning integration
- Blue/green deployment
- Canary release mechanism

**Deliverables**

- Fully automated pipeline
- Rollback demonstration
- Deployment documentation
- Operational runbook

---

## Phase 5 -- Observability & Incident Response (Weeks 13--14)

**Objectives**

- CloudWatch alarms
- X-Ray tracing
- Cost anomaly detection
- Automated alerting
- Incident simulation

**Deliverables**

- Monitoring dashboards
- Alert response workflow
- Abuse detection logic
- Runbook for incident handling

---

## Phase 6 -- Certification Integration (Weeks 15--16)

**Objectives**

- Map architecture decisions to certification domains
- Develop scenario-based exam questions
- Create failure case studies
- Build trade-off documentation

**Deliverables**

- Question bank (minimum 100 scenario questions)
- Architecture trade-off log
- Cost optimisation case study
- Multi-account DR strategy document

---

## Ongoing Enhancements

- Multi-region failover
- AI model performance optimisation
- Token usage predictive modelling
- Chaos engineering
- Governance automation

---

## Final Outcome

By completion, the project demonstrates:

- Enterprise-grade AI architecture
- Secure generative AI deployment
- Cloud-native DevSecOps maturity
- Professional-level AWS design competency
- Ability to construct advanced certification exam questions

---

# Project Deliverables

Deliverables are grouped into technical artefacts, security artefacts, DevOps artefacts, architecture artefacts, and certification assets.

---

## 1. Architecture Deliverables

> Demonstrates Solutions Architect -- Professional capability.

### 1.1 High-Level Architecture Diagram

Must include:

- Multi-account structure (Dev / Prod / Security)
- Bedrock integration
- RAG components
- Private VPC endpoints
- WAF + API Gateway
- Monitoring services
- CI/CD pipeline

**Format:** PNG + editable source (Draw.io / Lucidchart), version-controlled.

### 1.2 Detailed Network Architecture

- Subnet layout
- NAT usage justification
- Security groups
- NACL strategy
- Interface VPC endpoints
- Route tables

### 1.3 Disaster Recovery Plan

- RTO / RPO definitions
- Backup strategy
- Cross-region strategy
- Failover decision tree

---

## 2. Infrastructure as Code Deliverables

> Demonstrates DevOps Engineer -- Professional maturity.

### 2.1 Terraform Module Structure

```
modules/
├── network/
├── iam/
├── bedrock/
├── rag/
├── monitoring/
└── waf/
environments/
├── dev/
└── prod/
```

**Deliver:**

- Parameterised modules
- Remote state configuration
- Backend encryption
- Workspace separation

### 2.2 CI/CD Pipeline Definition

- CodePipeline or GitHub Actions
- Static analysis stage
- Security scanning stage
- Terraform plan/apply stage
- Canary deployment stage
- Rollback automation

### 2.3 Infrastructure Security Report

- IAM least privilege validation
- Access Analyzer results
- Config rule compliance
- SCP enforcement summary

---

## 3. Generative AI Deliverables

> Demonstrates Generative AI Developer -- Professional capability.

### 3.1 RAG Pipeline Implementation

- Embedding workflow
- Vector database integration
- Retrieval filtering logic
- Prompt construction module
- Injection sanitisation layer

### 3.2 Prompt Engineering Documentation

- Prompt templates
- Guardrail configuration
- Token limits
- Cost-per-request estimation
- Latency benchmarking

### 3.3 Attack Simulation Scripts

Implement and document:

1. Prompt injection
2. Model abuse (token flooding)
3. Data leakage attempt
4. Retrieval manipulation
5. IAM misconfiguration test

**Deliver:** Before/after metrics, detection logs, mitigation effectiveness.

---

## 4. Security Deliverables

> These differentiate the project from a standard AI demo.

### 4.1 Formal Threat Model

**Methodology:** STRIDE + MITRE ATT&CK mapping

**Include:**

- Trust boundaries
- Data flow diagrams
- Risk matrix
- Residual risk statement

### 4.2 Security Control Matrix

| Threat                               | Control | AWS Service | Residual Risk |
| ------------------------------------ | ------- | ----------- | ------------- |
| _To be populated per implementation_ |         |             |               |

### 4.3 Compliance Mapping

Map architecture to:

- NIST AI Risk Management Framework
- Data protection controls
- Encryption at rest and in transit

### 4.4 IAM Policy Review

- Document role boundaries
- Explicit deny strategy
- Privilege escalation prevention

---

## 5. Observability & Operations Deliverables

### 5.1 Monitoring Dashboard

- CloudWatch dashboard export
- Token usage metrics
- Latency metrics
- Error rates
- Cost metrics

### 5.2 Incident Response Runbook

- Alert classification
- Escalation path
- Isolation procedure
- Recovery process
- Post-incident review template

### 5.3 Abuse Detection Logic

- Rate anomaly detection
- Prompt entropy analysis
- Cost anomaly alarm
- IAM anomaly detection

---

## 6. Cost & Performance Deliverables

### 6.1 Cost Model

- Monthly cost projection
- Token usage estimation
- Scaling scenario modelling
- OpenSearch capacity justification

### 6.2 Performance Benchmark Report

- Baseline latency
- Load testing results
- Canary deployment impact
- Scaling thresholds

---

## 7. Documentation Deliverables

### 7.1 README.md

- Project summary
- Architecture overview
- Deployment instructions
- Security posture summary

### 7.2 ROADMAP.md

- Phased execution plan
- Milestones
- Certification alignment

### 7.3 Trade-Off Log

Professional-level documentation of:

- Why Bedrock over SageMaker endpoints
- Why OpenSearch over Aurora pgvector
- Why private endpoints over public
- Cost vs latency trade-offs

> This is essential for Professional exams.

---

## 8. Certification & Exam Creation Deliverables

> This is what elevates the project.

### 8.1 Domain Mapping Matrix

| Feature                              | GenAI Pro | DevOps Pro | SA Pro |
| ------------------------------------ | --------- | ---------- | ------ |
| _To be populated per implementation_ |           |            |        |

### 8.2 Scenario-Based Question Bank

**Minimum:**

- 30 GenAI Professional-style questions
- 30 DevOps Professional-style questions
- 40 Solutions Architect Professional-style questions

Each question must include:

- Scenario
- 4--5 options
- Correct answer
- Justification
- Why other answers are wrong

### 8.3 Failure Scenario Case Studies

- Region outage
- IAM compromise
- Model abuse attack
- Prompt injection incident
- Deployment regression

Each mapped to exam domain.

---

## 9. Demonstration Deliverables

### 9.1 15-Minute Technical Walkthrough Video

Demonstrate:

- Architecture
- Deployment
- Attack simulation
- Monitoring alert trigger
- Rollback

### 9.2 Executive Summary Deck (10--15 slides)

**Audience:** Hiring managers, architecture review board, certification study groups.

---

## 10. Optional Senior-Level Enhancements

- Multi-region active-active
- Model signing
- Differential privacy experiment
- Chaos engineering injection
- SCP guardrail enforcement
- Security Hub aggregation

---

## Minimum Viable Deliverables (If Time-Constrained)

If constrained, the absolute minimum acceptable set:

1. Working RAG platform on Bedrock
2. Secure IAM architecture
3. Private networking configuration
4. CI/CD pipeline with rollback
5. Prompt injection simulation + mitigation
6. Threat model document
7. Architecture diagram
8. 30 Professional-level exam questions

---

## Final Standard

If executed properly, this project will demonstrate:

- Enterprise AI system design
- Advanced AWS architecture
- DevSecOps automation
- Adversarial AI security capability
- Professional certification readiness
- Ability to author high-quality exam material
