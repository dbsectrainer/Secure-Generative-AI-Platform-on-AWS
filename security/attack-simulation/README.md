# Attack Simulation Scripts

**Version:** 1.0  
**Date:** 2026-03-01  
**Purpose:** Red team / security validation exercises for the Secure GenAI Platform

> **⚠️ WARNING:** These scripts are designed for use against your own AWS infrastructure in a controlled test environment **only**. Never run these against production environments or systems you do not own. Ensure you have explicit written authorisation before executing any simulation.

---

## Overview

This directory contains five attack simulation scripts that validate the security controls implemented in the Secure Generative AI Platform. Each script:

1. Simulates a specific attack category
2. Measures the platform's response **before** mitigations (dry-run mode)
3. Measures the platform's response **after** mitigations (live mode)
4. Produces detection evidence (logs, metrics, findings)
5. Reports mitigation effectiveness

---

## Scripts

| Script                         | Attack Category                  | Primary Control Tested                              |
|--------------------------------|----------------------------------|-----------------------------------------------------|
| `01_prompt_injection.py`       | Prompt injection                 | `sanitise_query()` + Bedrock Guardrails             |
| `02_token_flooding.py`         | Model abuse / token flooding     | WAF rate limiting + Lambda concurrency + Budgets    |
| `03_data_leakage.py`           | Data leakage attempt             | S3 bucket policies + VPC endpoints + Guardrails PII |
| `04_retrieval_manipulation.py` | Retrieval manipulation           | OpenSearch access policy + embedding validation     |
| `05_iam_misconfiguration.py`   | IAM misconfiguration test        | IAM least-privilege + Access Analyzer + Config      |

---

## Prerequisites

```bash
pip install boto3 requests
```

Configure AWS credentials with **read-only** permissions to the target account before running.

Set the following environment variables:

```bash
export AWS_REGION=eu-west-1
export TARGET_API_URL=https://<api-id>.execute-api.<region>.amazonaws.com/prod
export TEST_JWT_TOKEN=<cognito-jwt-for-test-user>
export DOCUMENT_BUCKET=<s3-bucket-name>
export OPENSEARCH_ENDPOINT=<opensearch-serverless-endpoint>
export LAMBDA_ORCHESTRATOR_ARN=<lambda-arn>
export ACCOUNT_ID=<aws-account-id>
```

---

## Running the Scripts

### Individual script

```bash
python security/attack-simulation/01_prompt_injection.py
```

### All scripts in sequence

```bash
for script in security/attack-simulation/0*.py; do
    echo "=== Running $script ==="
    python "$script"
    echo ""
done
```

### Dry-run mode (no live AWS calls)

Each script supports `--dry-run` flag to simulate without making AWS API calls:

```bash
python security/attack-simulation/01_prompt_injection.py --dry-run
```

---

## Output Format

Each script outputs a structured report:

```
==========================================
ATTACK SIMULATION: <Category>
==========================================
[BEFORE] Unmitigated result: <result>
[AFTER]  Mitigated result:   <result>
[DETECTION] Log evidence:    <log entry>
[METRIC]    Detection count: <n>
[RESULT]    Mitigation effective: YES/NO
==========================================
```

---

## Interpreting Results

- **PASS:** The control blocked or detected the attack as expected.
- **FAIL:** The attack succeeded; the control requires review.
- **PARTIAL:** The attack was partially mitigated; additional hardening recommended.

---

## Related Documentation

- [Threat Model](../threat-model.md)
- [Security Control Matrix](../security-control-matrix.md)
- [Injection Mitigation Results](../injection-mitigation-results.md)
- [IAM Least-Privilege Validation](../iam-least-privilege-validation.md)
