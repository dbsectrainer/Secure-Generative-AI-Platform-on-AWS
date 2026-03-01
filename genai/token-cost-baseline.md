# Token Cost Baseline

## Overview

This document establishes the baseline token usage and cost estimates for the
RAG pipeline. All costs are based on Amazon Bedrock pricing for
**Claude 3 Sonnet** and **Titan Text Embeddings v2** in `eu-west-1`.

> **Note:** Pricing changes frequently. Always verify current rates at
> [https://aws.amazon.com/bedrock/pricing/](https://aws.amazon.com/bedrock/pricing/).

---

## Model Pricing Reference

| Model | Input Price | Output Price |
|-------|------------|--------------|
| Claude 3 Sonnet | $0.003 / 1K tokens | $0.015 / 1K tokens |
| Claude 3 Haiku | $0.00025 / 1K tokens | $0.00125 / 1K tokens |
| Titan Text Embeddings v2 | $0.00002 / 1K tokens | — |

---

## Per-Stage Token Usage

### Stage 1: Document Embedding (Titan Text Embeddings v2)

Each text chunk sent for embedding incurs embedding model token usage.

| Parameter | Value |
|-----------|-------|
| Chunk size | 1,000 chars (~250 tokens) |
| Model | `amazon.titan-embed-text-v2:0` |
| Price per chunk | ~$0.000005 |
| Embedding dimensions | 1,024 |

**For a 10-page document (≈25,000 chars):**
- Chunks generated: ~27 (with 200-char overlap)
- Embedding tokens: ~6,750
- Embedding cost: ~$0.000135

---

### Stage 2: Query Embedding (Retrieval)

Each user query generates one embedding before k-NN search.

| Parameter | Value |
|-----------|-------|
| Avg. query length | 50–200 chars (~13–50 tokens) |
| Cost per query embedding | ~$0.0000006 |

---

### Stage 3: Bedrock Inference (Claude 3 Sonnet)

The RAG orchestrator assembles a grounded prompt and calls the inference model.

#### Prompt token breakdown

| Component | Chars | Est. Tokens |
|-----------|-------|-------------|
| System prompt | ~800 | ~200 |
| Retrieved context (5 × 1,000-char chunks) | ~5,000 | ~1,250 |
| User query | ~200 | ~50 |
| **Total input tokens** | | **~1,500** |
| Model response | — | ~300 |
| **Total tokens/request** | | **~1,800** |

#### Cost per request

| Scenario | Input Tokens | Output Tokens | Total Cost (Sonnet) |
|----------|-------------|---------------|---------------------|
| Minimal (1 chunk, short answer) | 400 | 100 | $0.0000026 |
| Standard (5 chunks, medium answer) | 1,500 | 300 | $0.0000090 |
| Rich (10 chunks, long answer) | 2,800 | 600 | $0.0000174 |
| Max budget | 5,500 | 2,048 | $0.0000472 |

---

## Monthly Cost Projections

Assumes **standard scenario** ($0.000009/request):

| Daily Requests | Monthly Cost |
|---------------|--------------|
| 100 | $0.027 |
| 1,000 | $0.27 |
| 10,000 | $2.70 |
| 100,000 | $27.00 |
| 1,000,000 | $270.00 |

---

## Token Tracking Implementation

Per-request token usage is logged by the orchestrator Lambda:

```json
{
  "input_tokens": 1487,
  "output_tokens": 312,
  "prompt_token_estimate": 1350,
  "estimated_cost_usd": 0.000009126
}
```

### CloudWatch Metric Filter (recommended)

Add a metric filter to aggregate daily token usage:

```json
{
  "filterPattern": "{ $.input_tokens > 0 }",
  "metricTransformations": [
    {
      "metricName": "DailyInputTokens",
      "metricNamespace": "RAGPipeline",
      "metricValue": "$.input_tokens"
    },
    {
      "metricName": "DailyOutputTokens",
      "metricNamespace": "RAGPipeline",
      "metricValue": "$.output_tokens"
    }
  ]
}
```

---

## Cost Controls

| Control | Implementation |
|---------|---------------|
| Max response tokens | `MAX_TOKENS=2048` env var (orchestrator Lambda) |
| Input query cap | 8,000 characters (hard validation) |
| Context cap | 16,000 characters per request |
| Budget alerts | AWS Cost Anomaly Detection + CloudWatch alarms |
| Log retention | Configurable (`log_retention_days` Terraform variable) |
