# ──────────────────────────────────────────────────────────────────────────────
# Makefile — AWS SAM CLI local testing helpers
# This is for LOCAL TESTING ONLY. Terraform is used for cloud deployment.
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: layer-prepare sam-build sam-validate test lint validate \
        sam-invoke-bedrock sam-invoke-ingestion sam-invoke-embedding \
        sam-invoke-retrieval sam-invoke-rag \
        sam-api sam-api-mock mock-aws e2e screenshots \
        coverage typecheck sbom localstack-infra-test frontend ui-e2e \
        terraform-validate sam-generate-s3-event clean-sam

LAYER_DIR := layers/prompt_builder

# ── Layer preparation ─────────────────────────────────────────────────────────
# Copies prompt_builder sources to the layer root. SAM's Python builder wraps
# this directory as python/ inside the layer artifact. Copying into a nested
# python/ directory here would produce python/python/ and break imports.

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

# ── Quality gates ─────────────────────────────────────────────────────────────

test:
	python3 -m pytest -q

coverage:
	python3 -m pytest --cov \
		--cov-report=term-missing \
		--cov-report=xml:docs/evidence/test-results/coverage.xml \
		--cov-report=html:docs/evidence/test-results/htmlcov

typecheck:
	mypy

sbom:
	cyclonedx-py requirements requirements-dev.lock \
		--of json \
		-o docs/evidence/build-results/sbom.cdx.json \
		--validate

localstack-infra-test:
	scripts/run_localstack_infra_test.sh

frontend:
	python3 scripts/serve_frontend.py --port 8080

ui-e2e:
	python3 scripts/ui_e2e_verify.py

lint:
	ruff check .

terraform-validate:
	cd terraform/environments/dev && terraform init -backend=false -input=false && terraform validate && terraform test -no-color
	cd terraform/environments/prod && terraform init -backend=false -input=false && terraform validate && terraform test -no-color
	cd terraform/modules/rag && terraform init -backend=false -input=false && terraform test -no-color
	cd terraform/modules/auth && terraform init -backend=false -input=false && terraform test -no-color

validate: lint test typecheck sam-validate terraform-validate

# ── Individual function invocations ───────────────────────────────────────────

sam-invoke-bedrock: sam-build
	sam local invoke BedrockOrchestratorFunction \
		--event events/bedrock-invoke.json \
		--env-vars env.json \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg"

sam-invoke-ingestion: sam-build
	sam local invoke RagIngestionFunction \
		--event events/rag-ingestion-s3.json \
		--env-vars env.json \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg"

sam-invoke-embedding: sam-build
	sam local invoke RagEmbeddingFunction \
		--event events/rag-embedding.json \
		--env-vars env.json \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg"

sam-invoke-retrieval: sam-build
	sam local invoke RagRetrievalFunction \
		--event events/rag-retrieval.json \
		--env-vars env.json \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg"

sam-invoke-rag: sam-build
	sam local invoke RagOrchestratorFunction \
		--event events/rag-query.json \
		--env-vars env.json \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg"

# ── Local API Gateway ─────────────────────────────────────────────────────────

sam-api: sam-build
	sam local start-api \
		--env-vars env.json \
		--warm-containers EAGER \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg" \
		--port 3000

# End-to-end verification without live AWS. Requires a running instance of
# `make mock-aws` in another terminal. Applies placeholder credentials only to
# the SAM process so no real AWS request can be signed.
sam-api-mock: sam-build
	AWS_ACCESS_KEY_ID=local-double \
	AWS_SECRET_ACCESS_KEY=local-double \
	AWS_SESSION_TOKEN=local-double \
	AWS_DEFAULT_REGION=eu-west-1 \
	AWS_EC2_METADATA_DISABLED=true \
	sam local start-api \
		--env-vars env.mock.json \
		--warm-containers EAGER \
		--layer-cache-basedir "$(CURDIR)/.aws-sam/layers-pkg" \
		--port 3000

mock-aws:
	python3 scripts/local_aws_doubles.py --port 9000

e2e:
	python3 scripts/e2e_api_verify.py \
		--base-url http://127.0.0.1:3000 \
		--output-dir docs/evidence

screenshots:
	python3 scripts/capture_evidence.py

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
	rm -f $(LAYER_DIR)/builder.py $(LAYER_DIR)/templates.py
	rm -rf $(LAYER_DIR)/python
	@echo "✓ SAM build artifacts cleaned"
