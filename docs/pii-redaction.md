# PII Redaction in Generative AI Platform

This document describes the Personally Identifiable Information (PII) redaction mechanisms implemented in the Secure Generative AI Platform to protect sensitive data during LLM processing.

## Overview

The platform implements **multi-layer PII redaction** to ensure that Personally Identifiable Information is not exposed to generative AI models or stored in logs:

1. **Input Redaction** — Remove PII before sending to Bedrock/Claude
2. **Compliance Audit** — Log PII detection for compliance (FISMA, FedRAMP)
3. **Output Validation** — Filter LLM responses for unintended PII leakage
4. **Secure Logging** — Store audit trails separately from application logs

---

## Architecture

```
┌──────────────────┐
│  User Input      │
│  (Plain Text)    │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────┐
│  AWS Comprehend PII Detector     │
│  (Detects: SSN, CC#, Phone, etc) │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│  Redaction Engine                │
│  - Replace with [PII_TYPE]       │
│  - Store mapping (secure)        │
│  - Log detection event           │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│  Bedrock / Claude                │
│  (Processes redacted text)       │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│  Output Filter                   │
│  - Scan response for patterns    │
│  - Verify no PII leakage         │
│  - Log decision                  │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────┐
│  Return to User  │
│  (Safe Output)   │
└──────────────────┘
```

---

## Supported PII Types

The platform detects and redacts the following PII categories:

### Personal Identifiers
- **SSN** — Social Security Numbers (XXX-XX-0000 format)
- **NAME** — Full names (detected via NLP)
- **EMAIL** — Email addresses (user@domain.com)
- **PHONE** — Phone numbers (+1-XXX-XXX-XXXX)

### Financial Identifiers
- **CREDIT_CARD** — Credit card numbers (PAN, 16+ digits)
- **BANK_ACCOUNT** — Bank account numbers (routing + account)
- **ROUTING_NUMBER** — Bank routing numbers
- **CRYPTO_ADDRESS** — Cryptocurrency wallet addresses (Bitcoin, Ethereum)

### Healthcare Identifiers
- **MEDICAL_RECORD_NUMBER** — MRN (patient medical records)
- **HEALTH_INSURANCE_ID** — Insurance policy numbers
- **DRUG_NAME** — Prescription medication names (privacy context)

### Government Identifiers
- **PASSPORT_NUMBER** — Passport IDs
- **DRIVER_LICENSE** — Driver's license numbers
- **VISA_NUMBER** — Visa/immigration document numbers
- **TAX_ID** — Tax identification numbers (EIN, ITIN)

### Authentication Identifiers
- **PASSWORD** — Literal password strings
- **API_KEY** — API keys and tokens
- **PRIVATE_KEY** — SSH/encryption keys
- **JWT_TOKEN** — JSON Web Tokens

### Location & Organization
- **IP_ADDRESS** — IPv4 and IPv6 addresses (context-dependent)
- **MAC_ADDRESS** — MAC addresses (sensitive in federal context)
- **ORGANIZATION_NAME** — Classified organization names

---

## Implementation Methods

### 1. AWS Comprehend Integration (Recommended)

**Pros:**
- Managed service (no infrastructure)
- FedRAMP High authorized
- Continuously improved PII detection
- Supports 100+ PII entity types
- Works in AWS GovCloud

**Cons:**
- Latency: 100-500ms per request
- Cost: $0.0001 per 100 chars (minimal)
- Must send data to Comprehend (within AWS region)

**Code Example:**
```python
import boto3
import json
from datetime import datetime

comprehend = boto3.client('comprehend', region_name='us-gov-west-1')

def detect_pii(text: str) -> dict:
    """
    Detect PII in text using AWS Comprehend.
    
    Args:
        text: Input text to scan
        
    Returns:
        dict with entities and redacted_text
    """
    # Detect PII
    response = comprehend.detect_pii_entities(
        Text=text,
        LanguageCode='en'
    )
    
    entities = response['Entities']
    redacted_text = text
    offset_adjust = 0
    
    # Sort by offset (reversed) to avoid offset shifting
    for entity in sorted(entities, key=lambda x: x['BeginOffset'], reverse=True):
        entity_type = entity['Type']
        begin = entity['BeginOffset']
        end = entity['EndOffset']
        confidence = entity['Score']
        
        # Only redact if confidence > 0.9
        if confidence > 0.9:
            # Replace with [PII_TYPE]
            replacement = f"[{entity_type}]"
            redacted_text = (
                redacted_text[:begin] + replacement + redacted_text[end:]
            )
            
            # Log for audit trail
            log_pii_detection(
                entity_type=entity_type,
                text_snippet=text[begin:end],
                confidence=confidence,
                timestamp=datetime.utcnow().isoformat()
            )
    
    return {
        'original_length': len(text),
        'redacted_text': redacted_text,
        'entities_found': len(entities),
        'entities': entities
    }

def log_pii_detection(entity_type: str, text_snippet: str, confidence: float, timestamp: str):
    """Log PII detection to CloudWatch (without storing actual PII)."""
    cloudwatch = boto3.client('logs')
    
    # Hash the snippet to avoid storing actual PII
    import hashlib
    snippet_hash = hashlib.sha256(text_snippet.encode()).hexdigest()[:16]
    
    log_message = {
        'pii_type': entity_type,
        'snippet_hash': snippet_hash,
        'confidence': confidence,
        'timestamp': timestamp,
        'source': 'comprehend_detection'
    }
    
    print(json.dumps(log_message))  # CloudWatch will capture this
```

---

### 2. Regex-Based Detection (Lightweight Alternative)

**Pros:**
- No latency (instant)
- No API calls
- Works offline
- Low cost

**Cons:**
- Limited accuracy (high false negatives)
- Requires pattern maintenance
- Miss context-dependent PII

**Code Example:**
```python
import re

PII_PATTERNS = {
    'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
    'CREDIT_CARD': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
    'EMAIL': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'PHONE': r'\b(?:\+?1)?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
    'IP_ADDRESS': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
    'PASSPORT': r'\b[A-Z]{1,2}\d{6,9}\b',
}

def redact_pii_regex(text: str, confidence_threshold: float = 0.8) -> str:
    """Redact PII using regex patterns."""
    redacted = text
    found_entities = {}
    
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.finditer(pattern, text)
        for match in matches:
            original = match.group()
            redacted_version = f"[{pii_type}]"
            redacted = redacted.replace(original, redacted_version, 1)
            
            if pii_type not in found_entities:
                found_entities[pii_type] = 0
            found_entities[pii_type] += 1
    
    return redacted

# Hybrid approach: Use Comprehend + Regex fallback
def detect_and_redact_pii(text: str) -> str:
    """Use Comprehend with regex fallback."""
    try:
        # Try Comprehend first (more accurate)
        result = detect_pii(text)
        return result['redacted_text']
    except Exception as e:
        print(f"Comprehend failed: {e}, falling back to regex")
        # Fallback to regex
        return redact_pii_regex(text)
```

---

### 3. Integration with Bedrock / Claude

**Prompt Injection Protection:**
```python
def call_bedrock_with_pii_redaction(user_input: str, model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"):
    """Call Bedrock with PII redaction."""
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-gov-west-1')
    
    # Step 1: Detect and redact PII
    redaction_result = detect_pii(user_input)
    redacted_text = redaction_result['redacted_text']
    
    # Step 2: Create system prompt with privacy notice
    system_prompt = """You are a helpful assistant. The user's input may contain redacted 
    personal information marked as [PII_TYPE]. Never ask the user to provide unredacted 
    versions of personal information. Never attempt to infer or reconstruct original PII."""
    
    # Step 3: Call Bedrock
    response = bedrock.invoke_model(
        modelId=model_id,
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-06-01',
            'max_tokens': 4096,
            'system': system_prompt,
            'messages': [
                {
                    'role': 'user',
                    'content': redacted_text  # Use redacted version
                }
            ]
        })
    )
    
    # Step 4: Validate response for PII leakage
    response_body = json.loads(response['body'].read())
    response_text = response_body['content'][0]['text']
    
    # Scan response for PII patterns
    response_pii = detect_pii(response_text)
    if response_pii['entities_found'] > 0:
        # Log WARNING: Model may have leaked PII
        print(f"WARNING: Response contains {response_pii['entities_found']} PII entities")
        # Redact response too
        response_text = response_pii['redacted_text']
    
    return response_text

# Lambda handler for API Gateway
def lambda_handler(event, context):
    """AWS Lambda handler for Bedrock inference with PII protection."""
    
    try:
        body = json.loads(event['body'])
        user_input = body.get('prompt', '')
        
        if not user_input:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'prompt is required'})
            }
        
        # Call with PII redaction
        response_text = call_bedrock_with_pii_redaction(user_input)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'response': response_text,
                'pii_redacted': True
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

---

## Audit & Compliance Logging

All PII detection events must be logged for FedRAMP compliance:

```python
def log_pii_event_to_cloudwatch(event_type: str, metadata: dict):
    """Log PII detection to CloudWatch Logs (compliant with AU-2, AU-3)."""
    
    logs_client = boto3.client('logs')
    
    log_event = {
        'event_type': event_type,  # 'PII_DETECTED', 'PII_REDACTED', 'PII_LEAKAGE'
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': metadata.get('user_id', 'unknown'),
        'request_id': metadata.get('request_id'),
        'pii_types_detected': metadata.get('entities', []),
        'confidence_scores': metadata.get('confidence', []),
        'action_taken': metadata.get('action', 'redacted'),
        'environment': 'production',
    }
    
    # Send to CloudWatch (structured logging)
    print(json.dumps(log_event))  # CloudWatch agent captures this

def create_pii_audit_report():
    """Generate daily PII detection report for compliance."""
    
    logs_client = boto3.client('logs')
    
    query = """
    fields @timestamp, user_id, pii_types_detected
    | filter event_type = 'PII_DETECTED'
    | stats count() as detection_count by pii_types_detected
    """
    
    # Execute Insights query
    response = logs_client.start_query(
        logGroupName='/aws/lambda/secure-ai-platform',
        startTime=int((datetime.utcnow() - timedelta(days=1)).timestamp()),
        endTime=int(datetime.utcnow().timestamp()),
        queryString=query
    )
    
    # Return report for compliance dashboard
    return response
```

---

## Best Practices

### ✅ DO:
1. **Always redact before LLM** — Never send unredacted PII to generative AI models
2. **Log detection events** — Maintain audit trail for FedRAMP (AU-2, AU-3)
3. **Use AWS Comprehend** — Most accurate and FedRAMP-authorized
4. **Test with samples** — Include PII in test data to validate redaction
5. **Monitor responses** — Scan LLM outputs for unintended PII disclosure
6. **Rotate keys** — Store PII mappings encrypted with KMS
7. **Document procedures** — Include in System Security Plan (SA-5)

### ❌ DON'T:
1. **Send raw PII to LLMs** — Always redact first
2. **Store unredacted mappings** — Use KMS encryption + Secrets Manager
3. **Trust regex alone** — Use AWS Comprehend for higher accuracy
4. **Ignore false negatives** — Test edge cases (variations, international formats)
5. **Log PII itself** — Only log hashes or summaries
6. **Disable redaction** — Keep it on in all environments
7. **Assume models are safe** — Jailbreak tests may reveal PII

---

## Testing & Validation

```python
def test_pii_redaction():
    """Test PII redaction with sample data."""
    
    test_cases = [
        {
            'input': "My SSN is 123-45-6789 and my email is john@example.com",
            'expected': "My SSN is [SSN] and my email is [EMAIL]"
        },
        {
            'input': "Call me at +1-555-123-4567 or +1 (555) 123-4567",
            'expected': "Call me at [PHONE] or [PHONE]"
        },
        {
            'input': "My credit card is 4532-1234-5678-9010",
            'expected': "My credit card is [CREDIT_CARD]"
        },
    ]
    
    for test in test_cases:
        result = detect_and_redact_pii(test['input'])
        print(f"Input:    {test['input']}")
        print(f"Output:   {result}")
        print(f"Expected: {test['expected']}")
        print(f"Match:    {result == test['expected']}\n")
```

---

## Compliance Controls

This implementation addresses the following FedRAMP controls:

| Control | Description | Implementation |
|---------|-------------|---|
| **SC-28(1)** | Cryptographic Protection (data at rest) | PII mappings encrypted with KMS CMK |
| **SI-4** | Information System Monitoring | CloudWatch Logs track PII detection |
| **IA-5(1)** | Password-Based Authentication | Don't log user credentials |
| **AU-2, AU-3** | Audit Event Content | Log PII detection (not actual data) |
| **SC-4** | Information in Shared Resources | Redact before processing |
| **SC-8** | Transmission Confidentiality | Use TLS for API calls |
| **SI-7** | Software Integrity | Validate LLM responses |

---

## References

- [AWS Comprehend PII Detection](https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html)
- [NIST SP 800-188 — De-Identification of Personal Information](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf)
- [FedRAMP Security Controls — SC-28(1)](https://csrc.nist.gov/projects/risk-management/sp800-53-control-catalog)
- [AWS GovCloud Security Services](https://aws.amazon.com/govcloud-us/compliance/)

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-06  
**Maintained by:** BE EASY ENTERPRISES Federal Compliance Team
