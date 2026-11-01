# Local RAG Console

A dependency-free HTML/CSS/JS console for the local SAM API.

```bash
# terminal 1: local Bedrock/OpenSearch/Lambda + auth token/JWKS doubles
make mock-aws

# terminal 2: SAM API with auth enabled
make sam-api-mock

# terminal 3: same-origin UI + API/token proxy
make frontend
# open http://127.0.0.1:8080
```

The **Get local test token** button fetches a short-lived RS256 token from the
local doubles; the API validates it through the shared auth layer. For a
deployed environment, paste a Cognito access or ID token and point the proxy at
the deployed API base URL.

```bash
python3 scripts/serve_frontend.py \
  --api-base-url https://<api-id>.execute-api.<region>.amazonaws.com/prod \
  --token-url https://<your-token-endpoint>
```

## Scope

This is a **local development console**, not a production-hosted frontend. It has
no Cognito Hosted UI, S3/CloudFront deployment, or production CORS policy. Those
require a live deployment and are intentionally outside the verified scope.
