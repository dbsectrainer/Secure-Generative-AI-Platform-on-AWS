# Performance Benchmarks – RAG Pipeline

## Overview

This document establishes baseline latency measurements for each stage of the
RAG pipeline. Benchmarks are collected from the orchestrator Lambda's
`latency_ms` response field and CloudWatch X-Ray traces.

All measurements assume **eu-west-1** with a warm Lambda container and
OpenSearch Serverless collection in `ACTIVE` state.

---

## Pipeline Stage Latency Baselines

### Cold Start vs Warm Invocation

| Metric               | Cold Start   | Warm     |
| -------------------- | ------------ | -------- |
| Lambda init time     | 800–1,500 ms | 0 ms     |
| Total pipeline (p50) | 4,500 ms     | 2,500 ms |
| Total pipeline (p95) | 8,000 ms     | 4,500 ms |

---

### Stage 1: Document Ingestion (S3 trigger → chunk → fan-out)

Per-document latency (synchronous portion before async fan-out):

| Document Size      | Chunks | Latency (p50) | Latency (p95) |
| ------------------ | ------ | ------------- | ------------- |
| 5 KB (1 page)      | ~7     | 150 ms        | 350 ms        |
| 50 KB (10 pages)   | ~60    | 200 ms        | 500 ms        |
| 500 KB (100 pages) | ~560   | 500 ms        | 1,200 ms      |

---

### Stage 2: Embedding Generation (per chunk, Titan v2)

| Metric                       | Value      |
| ---------------------------- | ---------- |
| Bedrock API latency (p50)    | 80 ms      |
| Bedrock API latency (p95)    | 200 ms     |
| OpenSearch index write (p50) | 30 ms      |
| OpenSearch index write (p95) | 100 ms     |
| **Total per chunk (p50)**    | **110 ms** |
| **Total per chunk (p95)**    | **300 ms** |

For a 10-page document (27 chunks), async fan-out completes within ~5–8 seconds.

---

### Stage 3: Retrieval (query embed + k-NN search)

| Metric                               | Value      |
| ------------------------------------ | ---------- |
| Query embedding generation (p50)     | 85 ms      |
| Query embedding generation (p95)     | 210 ms     |
| OpenSearch k-NN search, top-5 (p50)  | 40 ms      |
| OpenSearch k-NN search, top-5 (p95)  | 120 ms     |
| OpenSearch k-NN search, top-10 (p50) | 55 ms      |
| OpenSearch k-NN search, top-10 (p95) | 160 ms     |
| **Total retrieval (p50)**            | **125 ms** |
| **Total retrieval (p95)**            | **330 ms** |

Metadata filtering (additional `filter` clause) adds ~10–30 ms at p95.

---

### Stage 4: Prompt Construction

Prompt construction is CPU-bound (no I/O). Measured from `PromptBuilder.build()`.

| Scenario               | Latency (p50) | Latency (p95) |
| ---------------------- | ------------- | ------------- |
| 1 chunk, short query   | < 1 ms        | < 2 ms        |
| 5 chunks, medium query | < 2 ms        | < 5 ms        |
| 10 chunks, long query  | < 5 ms        | < 10 ms       |

---

### Stage 5: Bedrock Inference (Claude Sonnet 5.5)

> **Re-baseline needed:** the latency figures below were measured on the
> previous default model (Claude 3 Sonnet) and have not been re-measured on
> Sonnet 5.5. Treat them as placeholders until a load test is run.

| Response Length         | Latency (p50) | Latency (p95) |
| ----------------------- | ------------- | ------------- |
| Short (< 100 tokens)    | 800 ms        | 1,500 ms      |
| Medium (100–500 tokens) | 2,000 ms      | 3,500 ms      |
| Long (500–2,048 tokens) | 4,000 ms      | 7,000 ms      |

---

## End-to-End RAG Query Latency (warm Lambda)

Measured from `lambda_handler` entry to response return.

| Scenario                    | Retrieval | Prompt Build | Bedrock  | **Total (p50)** | **Total (p95)** |
| --------------------------- | --------- | ------------ | -------- | --------------- | --------------- |
| Minimal (1 chunk, short)    | 125 ms    | <1 ms        | 800 ms   | **930 ms**      | **2,000 ms**    |
| Standard (5 chunks, medium) | 125 ms    | 2 ms         | 2,000 ms | **2,130 ms**    | **4,000 ms**    |
| Rich (10 chunks, long)      | 180 ms    | 5 ms         | 4,000 ms | **4,190 ms**    | **7,500 ms**    |

---

## Latency Logging

The orchestrator Lambda returns latency breakdowns in every response:

```json
{
  "latency_ms": {
    "retrieval": 127.4,
    "prompt_construction": 1.8,
    "bedrock_inference": 2034.6,
    "total": 2163.8
  }
}
```

These values are emitted as structured CloudWatch log entries for aggregation
into dashboards and p95 alarms.

---

## CloudWatch Alarm Thresholds (Recommended)

| Alarm                     | Threshold      | Evaluation Periods |
| ------------------------- | -------------- | ------------------ |
| Orchestrator p95 duration | 10,000 ms      | 3 of 5 minutes     |
| Embedding Lambda errors   | > 5 per minute | 2 consecutive      |
| Retrieval Lambda errors   | > 5 per minute | 2 consecutive      |

These defaults are configurable via the `duration_alarm_threshold_ms` and
`error_alarm_threshold` variables in `terraform/modules/rag/variables.tf`.

---

## Optimisation Recommendations

| Opportunity                                     | Expected Improvement              |
| ----------------------------------------------- | --------------------------------- |
| Switch to Claude Haiku 5.5                        | 3–4× faster inference, lower cost |
| Reduce `top_k` from 5 to 3                      | ~20 ms saved in retrieval         |
| Reduce `MAX_TOKENS` from 2048 to 512            | 2–3× faster short-answer queries  |
| Provision Lambda at 1 GB memory                 | ~15% faster cold starts           |
| Pre-warm Lambda with scheduled EventBridge rule | Eliminates cold starts            |
| Use OpenSearch `_msearch` for batch queries     | Useful for bulk processing        |
