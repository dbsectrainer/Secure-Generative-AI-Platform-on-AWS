# Local Testing with AWS SAM CLI

Test Lambda functions and API endpoints locally using Docker containers that replicate the AWS Lambda runtime. **SAM is used for local testing only** — Terraform remains the deployment IaC.

> **Two local modes:**
>
> 1. **Real AWS mode** (`make sam-api`, `make sam-invoke-*`): requires AWS credentials, may incur Bedrock/OpenSearch charges, and is not used by the committed verification evidence.
> 2. **Local-doubles mode** (`make mock-aws` + `make sam-api-mock`): deterministic Bedrock/OpenSearch/Lambda responses, placeholder credentials, no network access to AWS. This is the mode used by `make e2e` and the screenshots. It verifies application wiring, not live AWS authorization.

## Prerequisites

| Tool           | Install                                                       | Purpose                                        |
| -------------- | ------------------------------------------------------------- | ---------------------------------------------- |
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) | Container runtime for Lambda emulation         |
| AWS SAM CLI    | `brew install aws-sam-cli`                                    | Local invoke and API Gateway emulation         |
| AWS CLI        | `brew install awscli`                                         | Credential configuration (real AWS mode only)  |
| GNU Make       | Pre-installed on macOS                                        | Build orchestration                            |
| Python 3.12+   | `brew install python@3.13`                                    | Tests/tooling; Lambda runtime is Python 3.13   |

**AWS credentials** are only required for real AWS mode. The local-doubles mode applies placeholder credentials to the SAM process so requests cannot be signed against AWS.

## Quick Start

```bash
# 1. Build all functions and the Lambda layer
make sam-build

# 2. Invoke a single function with a sample event (real AWS mode)
make sam-invoke-bedrock

# 3. Start a local API Gateway on port 3000 (real AWS mode)
make sam-api
```

### Verified mode: local service doubles

```bash
# Terminal 1 — deterministic Bedrock/OpenSearch/Lambda endpoints on :9000
make mock-aws

# Terminal 2 — SAM API using env.mock.json and placeholder credentials
make sam-api-mock

# Terminal 3 — run the 11-case HTTP verification matrix
make e2e
make screenshots
```

`env.mock.json` points each handler at `http://host.docker.internal:9000` through
`BEDROCK_ENDPOINT_URL` / `LAMBDA_ENDPOINT_URL` and `OPENSEARCH_ENDPOINT`.
The endpoint overrides are optional in production and are deliberately not named
`AWS_ENDPOINT_URL_*`, which SAM reserves and filters.

## Testing Individual Functions

Each function has a dedicated Makefile target and event file:

| Target                      | Function            | Event File                     | Description                   |
| --------------------------- | ------------------- | ------------------------------ | ----------------------------- |
| `make sam-invoke-bedrock`   | BedrockOrchestrator | `events/bedrock-invoke.json`   | Direct model invocation       |
| `make sam-invoke-ingestion` | RagIngestion        | `events/rag-ingestion-s3.json` | S3 document upload simulation |
| `make sam-invoke-embedding` | RagEmbedding        | `events/rag-embedding.json`    | Embedding generation          |
| `make sam-invoke-retrieval` | RagRetrieval        | `events/rag-retrieval.json`    | Vector search                 |
| `make sam-invoke-rag`       | RagOrchestrator     | `events/rag-query.json`        | Full RAG pipeline             |

### Custom Events

Invoke with a custom event file:

```bash
sam local invoke BedrockOrchestratorFunction \
  --event path/to/your-event.json \
  --env-vars env.json
```

Generate a realistic S3 event:

```bash
make sam-generate-s3-event
# Creates events/rag-ingestion-s3-generated.json
```

## Local API Gateway

Start the API with `make sam-api`, then test with curl:

```bash
# Direct Bedrock invocation
curl -s -X POST http://localhost:3000/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are AWS security best practices?"}'

# RAG query (full pipeline)
curl -s -X POST http://localhost:3000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize the security controls", "top_k": 3}'

# Embedding generation
curl -s -X POST http://localhost:3000/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Sample text to embed", "metadata": {"document_key": "test.txt", "chunk_index": 0}}'

# Retrieval search
curl -s -X POST http://localhost:3000/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "data retention policy", "top_k": 5}'
```

All endpoints return `Content-Type: application/json`. Validation failures return a JSON object such as `{"error":"..."}` with HTTP 400. The handlers accept both API Gateway proxy events (the HTTP path) and direct Lambda payloads (`sam local invoke`).

For a no-AWS verification run, use `make sam-api-mock` instead of `make sam-api` and run `make e2e`. See [docs/evidence/verification-report.md](evidence/verification-report.md).

### API Endpoints

| Method | Path        | Function            | Description                  |
| ------ | ----------- | ------------------- | ---------------------------- |
| POST   | `/invoke`   | BedrockOrchestrator | Direct model invocation      |
| POST   | `/embed`    | RagEmbedding        | Generate embeddings for text |
| POST   | `/retrieve` | RagRetrieval        | Search for relevant chunks   |
| POST   | `/query`    | RagOrchestrator     | Full RAG pipeline            |

> **Note:** The ingestion function is triggered by S3 events, not HTTP. Test it with `make sam-invoke-ingestion`.

## Environment Configuration

### Default Configuration (`env.json`)

Contains safe defaults for local testing (localhost endpoints, DEBUG logging). Committed to the repo.

### Personal Overrides (`env.local.json`)

For testing against real AWS resources, copy `env.local.json.example` to `env.local.json` and fill in real values:

```bash
cp env.local.json.example env.local.json
# Edit env.local.json with your real endpoints
```

Then invoke with the override:

```bash
sam local invoke BedrockOrchestratorFunction \
  --event events/bedrock-invoke.json \
  --env-vars env.local.json
```

`env.local.json` is gitignored and should never be committed.

### Local-Doubles Overrides (`env.mock.json`)

`env.mock.json` is tracked because it contains only endpoint URLs and no credentials. It is used by `make sam-api-mock`:

| Variable | Purpose | Production default |
| -------- | ------- | ------------------ |
| `BEDROCK_ENDPOINT_URL` | Redirect Bedrock Runtime calls to the local double | unset (regional AWS endpoint) |
| `LAMBDA_ENDPOINT_URL` | Redirect Lambda Invoke calls to the local double | unset (regional AWS endpoint) |
| `OPENSEARCH_ENDPOINT` | Point indexing/search at the local double | required endpoint |

These overrides are read by the handlers at module load and are intended for local testing. Placeholder credentials are applied by the Makefile to the SAM process only; never put real credentials in `env.mock.json`.

### AWS Credentials per Function

| Function            | Required AWS Access                              |
| ------------------- | ------------------------------------------------ |
| BedrockOrchestrator | `bedrock:InvokeModel`                            |
| RagIngestion        | `s3:GetObject`, `lambda:InvokeFunction`          |
| RagEmbedding        | `bedrock:InvokeModel`, OpenSearch network access |
| RagRetrieval        | `bedrock:InvokeModel`, OpenSearch network access |
| RagOrchestrator     | `bedrock:InvokeModel`, `lambda:InvokeFunction`   |

## Known Limitations

### Lambda-to-Lambda Invocations

The ingestion function calls the embedding function, and the orchestrator calls the retrieval function via `boto3.client("lambda").invoke()`. Against real AWS these work normally. In fully local mode, SAM runs each function in an isolated Docker container, so the call targets the AWS Lambda API.

**Workarounds:**

- Test each function individually with its event file (real AWS mode)
- Point `EMBEDDING_LAMBDA_ARN` / `RETRIEVAL_LAMBDA_ARN` at deployed Lambda functions
- Use `make mock-aws` + `make sam-api-mock`: `LAMBDA_ENDPOINT_URL` redirects the invoke call to the local double, allowing the full `/query` pipeline to be exercised without AWS

### Bedrock and OpenSearch

Real AWS mode requires credentials and model access; there are no local emulators for production services. The default `env.json` uses `https://localhost:9200` for OpenSearch and will fail unless you provide a reachable endpoint.

For verification without AWS, use the deterministic doubles in `scripts/local_aws_doubles.py`. They implement only the narrow request/response surfaces the handlers use (Bedrock invoke, OpenSearch `_doc`/`_search`, Lambda invoke) and accept SigV4 headers without validating them.

### S3 Triggers

`sam local start-api` does not simulate S3 events. Use `sam local invoke` with the S3 event JSON file instead.

### Layer Packaging

`make sam-build` copies `genai/prompt_builder/{builder,templates}.py` to the layer root before building. SAM's Python builder packages that root as `python/`. Do not create `layers/prompt_builder/python/` manually: it produces `python/python/...` and an `ImportModuleError` at runtime.

## Debugging

### Verbose Output

```bash
sam local invoke BedrockOrchestratorFunction \
  --event events/bedrock-invoke.json \
  --env-vars env.json \
  --debug
```

### Step Debugger

Attach a debugger on port 5858:

```bash
sam local invoke BedrockOrchestratorFunction \
  --event events/bedrock-invoke.json \
  --env-vars env.json \
  -d 5858
```

### Container Logs

SAM outputs Lambda container logs to stdout. Set `LOG_LEVEL=DEBUG` in `env.json` for detailed function logging.

## Cleanup

Remove SAM build artifacts and generated layer files:

```bash
make clean-sam
```

This removes `.aws-sam/`, the generated `layers/prompt_builder/{builder,templates}.py`, and any legacy `layers/prompt_builder/python/` directory. It does not delete the tracked `layers/prompt_builder/requirements.txt`.

## Project Structure

```
template.yaml                    # SAM template (local testing only)
samconfig.toml                   # SAM CLI defaults
env.json                         # Default environment variables (safe local defaults)
env.local.json.example           # Template for personal real-AWS overrides
env.mock.json                    # Local-doubles endpoint overrides (placeholder creds live only in Makefile)
Makefile                         # Build, test, local API, and evidence targets
scripts/
  local_aws_doubles.py           # Deterministic Bedrock/OpenSearch/Lambda test harness
  e2e_api_verify.py              # 11-case HTTP verification matrix
  capture_evidence.py            # Playwright screenshots of real captured responses
events/                          # Sample event payloads
  bedrock-invoke.json
  rag-ingestion-s3.json
  rag-embedding.json
  rag-retrieval.json
  rag-query.json
layers/prompt_builder/           # Layer root consumed by SAM's Python builder
  requirements.txt
  builder.py                     # Generated by 'make layer-prepare'
  templates.py                   # Generated by 'make layer-prepare'
```
