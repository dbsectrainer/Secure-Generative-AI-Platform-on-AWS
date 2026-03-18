# ──────────────────────────────────────────────────────────────────────────────
# Makefile — AWS SAM CLI local testing helpers
# This is for LOCAL TESTING ONLY. Terraform is used for cloud deployment.
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: layer-prepare sam-build sam-validate \
        sam-invoke-bedrock sam-invoke-ingestion sam-invoke-embedding \
        sam-invoke-retrieval sam-invoke-rag \
        sam-api sam-generate-s3-event clean-sam

LAYER_DIR := layers/prompt_builder/python

# ── Layer preparation ─────────────────────────────────────────────────────────
# Copies prompt_builder sources into the Lambda layer structure required by SAM.

layer-prepare:
	@mkdir -p $(LAYER_DIR)
	@cp genai/prompt_builder/builder.py $(LAYER_DIR)/builder.py
	@cp genai/prompt_builder/templates.py $(LAYER_DIR)/templates.py
	@echo "✓ Lambda layer prepared at $(LAYER_DIR)"

# ── Build ─────────────────────────────────────────────────────────────────────

sam-build: layer-prepare
	sam build

sam-validate:
	sam validate --lint

# ── Individual function invocations ───────────────────────────────────────────

sam-invoke-bedrock: sam-build
	sam local invoke BedrockOrchestratorFunction \
		--event events/bedrock-invoke.json \
		--env-vars env.json

sam-invoke-ingestion: sam-build
	sam local invoke RagIngestionFunction \
		--event events/rag-ingestion-s3.json \
		--env-vars env.json

sam-invoke-embedding: sam-build
	sam local invoke RagEmbeddingFunction \
		--event events/rag-embedding.json \
		--env-vars env.json

sam-invoke-retrieval: sam-build
	sam local invoke RagRetrievalFunction \
		--event events/rag-retrieval.json \
		--env-vars env.json

sam-invoke-rag: sam-build
	sam local invoke RagOrchestratorFunction \
		--event events/rag-query.json \
		--env-vars env.json

# ── Local API Gateway ─────────────────────────────────────────────────────────

sam-api: sam-build
	sam local start-api \
		--env-vars env.json \
		--warm-containers EAGER \
		--port 3000

# ── Helpers ───────────────────────────────────────────────────────────────────

sam-generate-s3-event:
	sam local generate-event s3 put \
		--bucket local-test-document-bucket \
		--key raw/sample-document.txt \
		> events/rag-ingestion-s3-generated.json
	@echo "✓ Generated S3 event at events/rag-ingestion-s3-generated.json"

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean-sam:
	rm -rf .aws-sam/
	rm -rf $(LAYER_DIR)
	@echo "✓ SAM build artifacts cleaned"
