# Local Testing with AWS SAM CLI

Test Lambda functions and API endpoints locally using Docker containers that replicate the AWS Lambda runtime. **SAM is used for local testing only** — Terraform remains the deployment IaC.

## Prerequisites

| Tool           | Install                                                       | Purpose                                        |
| -------------- | ------------------------------------------------------------- | ---------------------------------------------- |
| Docker Desktop | [docker.com](https://www.docker.com/products/docker-desktop/) | Container runtime for Lambda emulation         |
| AWS SAM CLI    | `brew install aws-sam-cli`                                    | Local invoke and API Gateway emulation         |
| AWS CLI        | `brew install awscli`                                         | Credential configuration                       |
| GNU Make       | Pre-installed on macOS                                        | Build orchestration                            |
| Python 3.12    | `brew install python@3.12`                                    | Required if building without `--use-container` |

**AWS credentials** are required even locally because the Lambda functions call real AWS services (Bedrock, OpenSearch). Run `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` environment variables.

## Quick Start

```bash
# 1. Build all functions and the Lambda layer
make sam-build

# 2. Invoke a single function with a sample event
make sam-invoke-bedrock

# 3. Start a local API Gateway on port 3000
make sam-api
```

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

The ingestion function calls the embedding function, and the orchestrator calls the retrieval function via `boto3.client("lambda").invoke()`. These cross-function calls **do not work in fully local mode** because SAM runs each function in an isolated Docker container.

**Workarounds:**

- Test each function individually with its event file (recommended)
- Point `EMBEDDING_LAMBDA_ARN` / `RETRIEVAL_LAMBDA_ARN` in `env.local.json` at deployed Lambda functions to test the full chain

### Bedrock and OpenSearch

Both require real AWS credentials — there are no local emulators. The default `env.json` uses `https://localhost:9200` for OpenSearch (will fail unless you run a local OpenSearch container).

### S3 Triggers

`sam local start-api` does not simulate S3 events. Use `sam local invoke` with the S3 event JSON file instead.

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

Remove SAM build artifacts:

```bash
make clean-sam
```

This removes `.aws-sam/` and `layers/prompt_builder/python/` (generated files).

## Project Structure

```
template.yaml               # SAM template (local testing only)
samconfig.toml               # SAM CLI defaults
env.json                     # Default environment variables
env.local.json.example       # Template for personal overrides
Makefile                     # Build and invoke targets
events/                      # Sample event payloads
  bedrock-invoke.json
  rag-ingestion-s3.json
  rag-embedding.json
  rag-retrieval.json
  rag-query.json
layers/prompt_builder/       # Lambda layer source
  requirements.txt
  python/                    # Generated by 'make layer-prepare'
    builder.py
    templates.py
```
