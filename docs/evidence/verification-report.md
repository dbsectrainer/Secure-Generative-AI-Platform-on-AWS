# Verification Report — Secure Generative AI Platform on AWS

**Audit date:** 2026-10-31 (America/New_York) / 2026-11-01 UTC
**Repository:** `Secure-Generative-AI-Platform-on-AWS`
**Audit type:** read-only review + local execution, remediation, regression tests, HTTP E2E, browser evidence
**Final verdict:** **PARTIAL PASS** — the local application is executable and verified; live AWS deployment and the full Terraform stack are not.

---

## 1. Scope and Methodology

### In scope

- Repository structure, Python handlers, prompt builder, tests, SAM template, Makefile, environment files
- Terraform module definitions and both environment roots (static validation only)
- Documentation accuracy for implemented versus intended behavior
- Build, lint, static validation, unit/regression tests
- End-to-end HTTP behavior through `sam local start-api`
- Browser-rendered evidence, console errors, and failed browser requests

### Out of scope / not performed

- `terraform apply`, AWS resource creation, production deployment
- Live Bedrock model access, live OpenSearch Serverless queries, IAM authorization checks
- FedRAMP authorization or independent security assessment
- Live penetration/load testing and container-image scanning
- CI execution on GitHub (the workflow was added but cannot run from this local session)

### Safety note

The first local API attempt was made before custom endpoint overrides were wired through SAM. Because SAM reserves `AWS_*` variables, several read-only Bedrock `InvokeModel` requests reached live AWS using the workstation's credentials: two inference attempts failed with `ValidationException` / `AccessDeniedException`, and the embedding calls completed. No AWS resources or data were modified. The application now supports explicit, non-reserved endpoint overrides, and all committed E2E evidence was produced with placeholder credentials and the local doubles. See §7.1.

### Environment

| Component | Version / configuration |
| --- | --- |
| OS | macOS (arm64) |
| Python (tooling/tests) | 3.12.7; Python 3.13.18 verified in a separate clean venv |
| Lambda runtime | python3.13 (SAM-managed container) |
| AWS SAM CLI | 1.155.2 |
| Docker | 29.9.2 |
| Terraform | 1.17.1 (darwin_arm64) |
| Node.js | 26.13.0 |
| Playwright | Chromium 1187, headless |
| LocalStack | Community 3.8.1 (Docker) |
| Moto | 5.2.x (in-process AWS emulation) |
| AWS CLI | 2.39.1 |

Tool versions are preserved in [`build-results/tool-versions.txt`](build-results/tool-versions.txt).

---

## 2. Initial Condition and Issues Discovered

Baseline tests passed (`97` tests), which initially masked the HTTP integration failures: the tests invoked handlers with **direct Lambda payloads**, while the documented `curl`/`sam local start-api` path supplies **API Gateway proxy events**.

| ID | Severity | Issue | Root cause | Reproduction / evidence |
| --- | --- | --- | --- | --- |
| F-01 | **Critical** | Every documented HTTP endpoint rejected valid JSON (`/invoke`, `/embed`, `/retrieve`, `/query` → 400). | Handlers read fields from the top-level proxy event instead of parsing `event["body"]`. | `POST /invoke` with `{"prompt":"..."}` returned `400 {"error":"Request must include a non-empty 'prompt' field."}` under SAM local. |
| F-02 | **Critical** | HTTP error responses were not valid JSON. | Handlers returned a Python `dict` in the Lambda proxy `body`; SAM serialized it as `{'error': '...'}` (single quotes). | `curl` showed `{'error': ...}` with `Content-Type: application/json`; `json.loads` failed. |
| F-03 | **Critical** | `/query` returned 502 at cold start: `Runtime.ImportModuleError: No module named 'builder'`. | Layer source already contained `python/`, and SAM's Python builder wrapped it again → `PromptBuilderLayer/python/python/builder.py`. | SAM log and `find .aws-sam/build/PromptBuilderLayer` showed the double nesting. |
| F-04 | **High** | Terraform does not deploy the RAG/API/WAF/OpenSearch stack described in the README. | Dev/prod roots instantiate only `network`, `s3`, `iam`, `bedrock`; `rag`, `opensearch`, `security`, `waf` modules are never called. | [`build-results/terraform-wiring.txt`](build-results/terraform-wiring.txt). |
| F-05 | **High** | The Terraform RAG module cannot run the orchestrator as packaged. | It does not attach the prompt-builder Lambda layer, and the environment does not pass an ingestion Lambda ARN for S3 notifications. | [`build-results/terraform-wiring.txt`](build-results/terraform-wiring.txt). |
| F-06 | **High** | README deployment commands were not reproducible (`terraform init` from repository root). | There is no root Terraform configuration; both roots use an S3 backend that requires `-backend-config`. | Root has no `*.tf`; `terraform init` from root fails; fixed in README. |
| F-07 | **Medium** | `top_k: null`/non-integer values produced HTTP 500. | `int(event.get(...))` raised uncaught `TypeError`; only `ValueError` was caught. | Regression test and E2E case `retrieve_invalid_top_k`. |
| F-08 | **Medium** | Upstream OpenSearch/Bedrock details were returned to API callers. | `str(exc)` included endpoint URLs and provider response bodies in `502` responses. | Code review; fixed and covered by tests (`"OS down" not in error`). |
| F-09 | **Medium** | Lint and formatting gates failed. | 16 Ruff findings; 7 Terraform files unformatted; no root pytest/Ruff config. | `ruff check .` and `terraform fmt -check -recursive` baseline. |
| F-10 | **Medium** | No CI workflow existed. | `.github` contained issue/PR templates only. | File listing; fixed with `.github/workflows/ci.yml`. |
| F-11 | **Medium** | Documentation claimed implemented PII redaction, Guardrails integration, and full production readiness without supporting handler code or deployed infrastructure. | Design documents were written as if production controls were active. | No `comprehend`/`guardrailIdentifier` references in `lambda/`, `rag/`, or `genai/`; Terraform roots incomplete. [`build-results/pii-guardrail-implementation.txt`](build-results/pii-guardrail-implementation.txt). |
| F-12 | **Low** | Unused imports/variables and f-strings without placeholders in tests and attack simulations. | Opportunistic code drift. | `ruff check .` before remediation. |
| F-13 | **Low** | SAM local startup failed in the constrained audit environment (`~/.aws-sam/layers-pkg` permission denied). | Environment sandbox restriction, not an application bug. | `sam local start-api` error; fixed with `--layer-cache-basedir` in Makefile. |
| F-14 | **Low** | No dependency lockfile/SBOM; `requirements.txt` uses open lower bounds. | Repository design. | `requirements*.txt` review. Not remediated in this audit. |

---

> **Remediation status:** F-01 through F-10 and F-12/F-13 are resolved. F-04/F-05
> (Terraform wiring/layer/IAM) are resolved in §3.7. F-11 is partially resolved:
> Guardrails pass-through and Terraform PII policy are implemented, but Comprehend
> is not used and no live Guardrail call was tested. F-14 is addressed by the
> locked dev dependency set and SBOM; current test count is 126 with 88% coverage.

## 3. Fixes Implemented

### 3.1 API Gateway proxy contract (F-01, F-02)

Added a small normalization/response layer to all four HTTP handlers:

- `_is_api_gateway_event()` / `_parse_event()` unwrap and validate the proxy `body` (JSON object required; malformed JSON → 400).
- `_build_response()` emits a JSON string body plus `Content-Type` header for proxy events, while preserving the existing dict contract for direct Lambda invocation and Lambda-to-Lambda calls.

Files:
- `lambda/bedrock_integration/handler.py`
- `rag/embedding/handler.py`
- `rag/retrieval/handler.py`
- `rag/orchestrator/handler.py`

Regression coverage: `TestApiGatewayProxy` in each handler test module.

### 3.2 Lambda layer packaging (F-03)

- `make layer-prepare` now copies `builder.py`/`templates.py` to `layers/prompt_builder/` (root), not a nested `python/`.
- SAM's Python builder creates `PromptBuilderLayer/python/<module>.py`.
- `make clean-sam` removes generated files; `.gitignore` excludes them.
- Added an explanatory template comment to prevent regression.

Files: `Makefile`, `template.yaml`, `.gitignore`.

Proof: [`build-results/layer-artifact.txt`](build-results/layer-artifact.txt):
```
.aws-sam/build/PromptBuilderLayer/python/builder.py
.aws-sam/build/PromptBuilderLayer/python/templates.py
```

### 3.3 Validation and error handling (F-07, F-08)

- Added `_parse_top_k()` to retrieval and orchestrator handlers; rejects `None`, booleans, floats, lists, objects, and non-numeric strings with HTTP 400.
- Replaced caller-visible OpenSearch exception text with generic 502 messages; details remain in CloudWatch-style logs.
- Removed provider error strings from Bedrock `ValidationException` responses.
- Orchestrator dependency failures return a generic stage error.

Files: `rag/retrieval/handler.py`, `rag/orchestrator/handler.py`, `rag/embedding/handler.py`, `lambda/bedrock_integration/handler.py`.

### 3.4 Local verification capability

- Added optional `BEDROCK_ENDPOINT_URL` / `LAMBDA_ENDPOINT_URL` overrides (unset in production).
- Added deterministic local AWS doubles: `scripts/local_aws_doubles.py`.
- Added `env.mock.json`, `make mock-aws`, `make sam-api-mock`, `make e2e`, `make screenshots`.
- Added `scripts/e2e_api_verify.py` and `scripts/capture_evidence.py`.

These are test capabilities, not substitutes for live integration verification.

### 3.5 Quality gates and automation (F-09, F-10)

- Root `pyproject.toml` for pytest/Ruff/coverage/mypy; `requirements-dev.txt` and `requirements-dev.lock`.
- Consolidated Makefile targets: `test`, `lint`, `terraform-validate`, `validate`.
- Fixed all 16 Ruff findings; formatted 7 Terraform files.
- Added `.github/workflows/ci.yml` for Python 3.12/3.13 tests, Ruff, mypy, coverage, pip-audit, SBOM, Terraform format/validate/test, SAM validate/build, cfn-lint, and LocalStack.

### 3.6 Documentation accuracy (F-06, F-11)

Updated:
- `README.md` — verified status, exact commands, mock workflow, screenshots, Terraform caveats, known gaps.
- `docs/local-testing.md` — verified local-doubles mode, layer packaging, endpoint overrides, limitations.
- `docs/pii-redaction.md` — Guardrails pass-through status; Comprehend design-only.
- `FEDRAMP-ALIGNMENT.md` — self-assessment disclaimer and deployment caveat.
- `CHANGELOG.md` — added/fixed/changed entries.
- This report and evidence artifacts.

---

### 3.7 Full Terraform wiring and missing IAM/layer resources (F-04, F-05)

The dev and prod roots now instantiate `network`, `s3`, `iam`, `bedrock`,
`opensearch`, `rag`, `security`, `waf`, and a new `api` module. Additional fixes:

- Added embedding, retrieval, and RAG-orchestrator IAM roles with scoped Bedrock,
  OpenSearch Serverless, Lambda invoke, logs, X-Ray, VPC, and deny-escalation
  policies.
- Added `lambda:InvokeFunction` to the ingestion/orchestrator policies.
- Added a prompt-builder Lambda layer built from the canonical `genai/prompt_builder`
  source and attached it to the RAG orchestrator.
- Added an S3 `ObjectCreated` notification and Lambda permission in the RAG module.
- Fixed OpenSearch Serverless network policy to use the module-created VPC endpoint,
  and added optional KMS CMK encryption.
- Added an API Gateway module with `/invoke`, `/embed`, `/retrieve`, and `/query`
  routes, Lambda permissions, stage, X-Ray tracing, and REGIONAL WAF association.
- Added Guardrail version resources and passed guardrail ID/version into both
  inference handlers.
- Added Terraform mock-provider wiring tests for dev and prod. Both full-stack
  plans pass.
- Added a LocalStack Community S3/IAM/KMS apply/verify/destroy test (13/13
  assertions). Services unavailable in LocalStack Community are plan-tested only.

### 3.8 Bedrock Guardrails and PII controls (F-11)

- The Bedrock and RAG handlers now pass `guardrailIdentifier` and
  `guardrailVersion` to `InvokeModel` when configured.
- The Terraform guardrail anonymizes EMAIL/NAME/PHONE and blocks AWS access/secret
  keys; IAM grants `bedrock:ApplyGuardrail`.
- Amazon Comprehend is not used; Guardrails is the deployed PII control path.
- New regression tests assert that guardrail parameters reach the Bedrock client.

### 3.9 Additional local AWS verification and quality tooling

- Added Moto-backed ingestion tests using real boto3 S3 calls against in-memory
  AWS emulation.
- Added `mypy` (16 application files, zero issues), branch coverage (88%),
  `pip-audit`, CycloneDX SBOM generation, and a locked development dependency set.
- Added LocalStack/Terraform/mock tests to the CI workflow.

## 4. Verification Results

### 4.1 Unit and regression tests

Command: `python3 -m pytest -vv`
Result: **126 passed**, exit 0.

A clean virtual environment was populated from the locked
`requirements-dev.lock`; the same 126 tests passed on Python 3.12 and Python
3.13, confirming the locked development dependency set is sufficient.

Logs:
- [`test-results/unit-tests.log`](test-results/unit-tests.log)
- [`test-results/venv-tests.log`](test-results/venv-tests.log)
- [`build-results/venv-install.log`](build-results/venv-install.log)

Coverage includes:
- Existing handler, chunking, embedding, retrieval, orchestrator, prompt builder tests
- New API Gateway proxy success/error tests
- Moto-backed S3 ingestion integration tests
- Malformed/non-object/empty body tests
- Invalid `top_k` parameterized tests
- Upstream-detail non-disclosure assertions
- Guardrail parameter pass-through tests

### 4.2 Lint

Command: `ruff check .`
Result: **All checks passed**, exit 0.

The lint gate uses an explicit rule selection (`E4`, `E7`, `E9`, `F`) so it is
stable across Ruff releases. Verified with Ruff 0.13.0 (host toolchain) and
Ruff 0.17.3 (clean venv).

Logs: [`build-results/ruff.log`](build-results/ruff.log), [`build-results/venv-ruff.log`](build-results/venv-ruff.log).

### 4.3 SAM and CloudFormation validation

| Command | Result | Log |
| --- | --- | --- |
| `sam validate --lint` | Valid SAM template, exit 0 | [`build-results/sam-validate.log`](build-results/sam-validate.log) |
| `cfn-lint template.yaml` | No findings, exit 0 | [`build-results/cfn-lint.log`](build-results/cfn-lint.log) |

### 4.4 SAM build

Command: `make sam-build` (Docker container build, arm64)
Result: **Build Succeeded**, exit 0. Layer artifact is correctly nested.

Log: [`build-results/sam-build.log`](build-results/sam-build.log)
Layer proof: [`build-results/layer-artifact.txt`](build-results/layer-artifact.txt)

### 4.5 Terraform static validation

| Command | Result |
| --- | --- |
| `terraform fmt -check -recursive` | exit 0, no output |
| `terraform init -backend=false && terraform validate` (dev) | Success, configuration valid |
| `terraform init -backend=false && terraform validate` (prod) | Success, configuration valid |
| `terraform test` (dev, full-stack mock plan) | 1/1 passed |
| `terraform test` (prod, full-stack mock plan) | 1/1 passed |

Logs:
- [`build-results/terraform-fmt.log`](build-results/terraform-fmt.log)
- [`build-results/terraform-validate-dev.log`](build-results/terraform-validate-dev.log)
- [`build-results/terraform-validate-prod.log`](build-results/terraform-validate-prod.log)
- [`build-results/make-validate.log`](build-results/make-validate.log) (consolidated `make validate`, exit 0)

**Limitation:** validation does not prove a plan/apply succeeds; the S3 backend was not initialized and no AWS resources were created.

### 4.6 Direct Lambda invocation (`sam local invoke`)

Four functions were invoked directly with the sample events and `env.mock.json`:

| Function | Result |
| --- | --- |
| `BedrockOrchestratorFunction` | 200, output + usage |
| `RagEmbeddingFunction` | 200, indexed + 1024 dimensions |
| `RagRetrievalFunction` | 200, 3 ranked results |
| `RagOrchestratorFunction` | 200, grounded output + usage + retrieval + latencies (layer mounted) |

Log: [`test-results/sam-local-invoke.log`](test-results/sam-local-invoke.log)

This is a separate execution path from the API Gateway proxy and confirms the
direct-invocation contract and layer mount.

### 4.7 End-to-end HTTP verification

Runtime:
```bash
make mock-aws        # terminal 1
make sam-api-mock    # terminal 2
make e2e             # terminal 3
```

Result: **11/11 cases passed** against `http://127.0.0.1:3000`.

| Case | Endpoint | Expected | Observed |
| --- | --- | --- | --- |
| invoke_success | POST /invoke | 200 | 200 |
| embed_success | POST /embed | 200 | 200 |
| retrieve_success | POST /retrieve | 200 | 200 |
| query_success | POST /query | 200 | 200 |
| invoke_empty_prompt | POST /invoke | 400 | 400 |
| invoke_malformed_json | POST /invoke | 400 | 400 |
| invoke_non_object_json | POST /invoke | 400 | 400 |
| embed_empty_text | POST /embed | 400 | 400 |
| retrieve_invalid_top_k | POST /retrieve | 400 | 400 |
| query_invalid_top_k | POST /query | 400 | 400 |
| query_injection_input | POST /query | 200 | 200 |

Full results: [`test-results/api-e2e-results.json`](test-results/api-e2e-results.json)
Run log: [`test-results/api-e2e-run.log`](test-results/api-e2e-run.log)

Key observations from the successful `/query` response:
- `output` grounded in three retrieved chunks
- `usage.input_tokens` / `output_tokens` / `prompt_token_estimate` / `estimated_cost_usd` present
- `retrieval.chunks_used` = 3
- stage latencies (`retrieval`, `prompt_construction`, `bedrock_inference`, `total`) present
- The orchestrator imported `builder` from the Lambda layer (previously the 502 failure point)

> **Test-double disclosure:** Bedrock, OpenSearch, and Lambda Invoke were served by `scripts/local_aws_doubles.py`. Results verify application request/response and orchestration wiring, **not** live AWS authorization, model availability, or OpenSearch index semantics. Service-double request log: [`test-results/local-aws-doubles.log`](test-results/local-aws-doubles.log). SAM startup/runtime log: [`build-results/sam-local-api.log`](build-results/sam-local-api.log).

### 4.8 Browser automation and console checks

Playwright rendered the generated API verification console at desktop (1440×1000) and mobile (390×844) viewports, captured workflow/error sections, and called the running API through the browser context.

- Browser API checks: **5/5 succeeded** ([`test-results/browser-api-checks.json`](test-results/browser-api-checks.json))
- Browser console entries: **0**
- Page errors / failed requests: **0**
- Log: [`test-results/browser-console.log`](test-results/browser-console.log)
- Capture log: [`test-results/browser-capture.log`](test-results/browser-capture.log)

**Limitation:** this repository has no end-user web frontend. "Browser verification" means rendering the verification console generated from live API responses and exercising the API through Playwright's request context. It is not UI E2E testing of a product interface.

### 4.9 Screenshots

All screenshots are rendered from the final run's captured responses.

| Screenshot | Demonstrates |
| --- | --- |
| [`screenshots/api-verification-desktop.png`](screenshots/api-verification-desktop.png) | Desktop summary: PASS badge, 11/11 cases, disclosure, first case |
| [`screenshots/api-verification-mobile.png`](screenshots/api-verification-mobile.png) | Responsive mobile layout at 390×844 |
| [`screenshots/query-workflow.png`](screenshots/query-workflow.png) | Full RAG `/query` response after layer fix: output, usage, retrieval, latencies |
| [`screenshots/error-validation.png`](screenshots/error-validation.png) | Malformed JSON returns JSON 400 instead of a crash |
| [`screenshots/api-verification-full.png`](screenshots/api-verification-full.png) | Full desktop report, all 11 cases |
| [`screenshots/api-verification-mobile-full.png`](screenshots/api-verification-mobile-full.png) | Full mobile report |

HTML source: [`api-console.html`](api-console.html).

### 4.10 Dependency installation

Clean Python 3.12 and 3.13 virtual environments were populated from
`requirements-dev.lock` (exit 0). In both environments: 126 tests passed,
Ruff passed, and mypy passed. A pip dry-run against the host environment also
resolved all declared requirements. No production secrets are required by the
development dependency set.

Logs:
- [`build-results/venv-install.log`](build-results/venv-install.log)
- [`build-results/dependency-resolution.log`](build-results/dependency-resolution.log)
- [`test-results/venv-tests.log`](test-results/venv-tests.log)
- [`build-results/venv-ruff.log`](build-results/venv-ruff.log)
- [`build-results/venv313-install.log`](build-results/venv313-install.log)
- [`test-results/venv313-tests.log`](test-results/venv313-tests.log)
- [`build-results/venv313-ruff.log`](build-results/venv313-ruff.log)

The host's unrelated global Anaconda packages are inconsistent with each other
(`pip check` reports conflicts in tools such as audiocraft, checkov, and
mlflow). That is an environment-wide issue, not a repository dependency
failure; the isolated venv is the relevant result.

### 4.11 Security scans

| Check | Result |
| --- | --- |
| Repository secret-pattern scan (`AKIA…`, private keys, GitHub tokens) | No matches |
| Bandit, non-test application code | 0 high, 2 medium, 0 low |
| `pip-audit -r requirements-dev.lock` | No known vulnerabilities |
| Container image scan | Not run |

The two Bandit medium findings are `B310` (`urllib.request.urlopen`) in the
embedding and retrieval handlers. The URL comes from the operator-controlled
`OPENSEARCH_ENDPOINT` environment variable and is not derived from request
input; the process already trusts that variable. This is documented as an
accepted residual risk rather than a user-reachable SSRF vector.

Logs:
- [`build-results/bandit-app.log`](build-results/bandit-app.log)
- [`build-results/bandit.log`](build-results/bandit.log) (includes test-file assert noise)
- [`build-results/pip-audit.log`](build-results/pip-audit.log)

The lockfile pins the tested development set; the SBOM is generated from that
lockfile (`build-results/sbom.cdx.json`). Audit results remain point-in-time.

---

### 4.12 Terraform mock-provider full-stack tests

Command: `terraform test` in `terraform/environments/dev` and
`terraform/environments/prod`.

Both root runs pass. The tests mock the `aws` and `archive` providers, plan the
entire root, and assert:

- four API routes are rendered;
- RAG ingestion/orchestrator Lambda names use the environment prefix;
- the Bedrock orchestrator Lambda is wired.

A module-level RAG test additionally passes and asserts the prompt-builder layer
attachment, Guardrail environment variables, and S3 `ObjectCreated` trigger.

This verifies composition and resource wiring without credentials. Provider API
semantics for unsupported services remain plan-only.

Logs:
- [`build-results/terraform-test-dev.log`](build-results/terraform-test-dev.log)
- [`build-results/terraform-test-prod.log`](build-results/terraform-test-prod.log)
- [`build-results/terraform-test-rag.log`](build-results/terraform-test-rag.log)
- Terraform test sources: [`terraform/environments/dev/tests/wiring.tftest.hcl`](../../terraform/environments/dev/tests/wiring.tftest.hcl), [`terraform/environments/prod/tests/wiring.tftest.hcl`](../../terraform/environments/prod/tests/wiring.tftest.hcl)

### 4.13 LocalStack infrastructure apply/verify/destroy

Command: `make localstack-infra-test` (LocalStack Community 3.8.1, Docker).

The script applied the S3/IAM/KMS modules, ran 13 boto3 assertions, and
destroyed all 29 resources. Results:

| Assertion | Result |
| --- | --- |
| S3 bucket exists | PASS |
| Versioning enabled | PASS |
| SSE-KMS with module-created key | PASS |
| All four public-access-block flags | PASS |
| TLS/checksum bucket-policy statements | PASS |
| Object write/read round-trip | PASS |
| KMS key enabled | PASS |
| KMS key rotation enabled | PASS |
| Four IAM roles with two attached policies each | PASS (4/4) |
| Object versions cleaned before destroy | PASS |

Logs:
- [`test-results/localstack-run.log`](test-results/localstack-run.log)
- [`test-results/localstack-terraform.log`](test-results/localstack-terraform.log)
- [`test-results/localstack-assertions.log`](test-results/localstack-assertions.log)
- [`test-results/localstack-assertions.json`](test-results/localstack-assertions.json)
- [`test-results/localstack-destroy.log`](test-results/localstack-destroy.log)

**Coverage limitation:** LocalStack Community does not provide Bedrock,
OpenSearch Serverless, WAF, GuardDuty, Config, or API Gateway in this test.
Those resources are covered by Terraform `validate` plus mock-provider plans.

### 4.14 Coverage, type checking, and SBOM

| Check | Command | Result |
| --- | --- | --- |
| Coverage | `python3 -m pytest --cov ...` | **88%** application coverage (branch), 126 tests |
| Type check | `mypy` | **Success**, 16 source files |
| SBOM | `cyclonedx-py requirements requirements-dev.lock ...` | CycloneDX 1.6, 82 components |
| Lockfile | `requirements-dev.lock` | Installed and tested on Python 3.12 and 3.13 |

Logs:
- [`test-results/coverage.log`](test-results/coverage.log)
- [`test-results/coverage.xml`](test-results/coverage.xml)
- [`build-results/mypy.log`](build-results/mypy.log)
- [`build-results/sbom.cdx.json`](build-results/sbom.cdx.json)
- [`build-results/sbom.log`](build-results/sbom.log)

## 5. Production Build and Startup

- `make sam-build` succeeded with Docker/Python 3.13 and produced `.aws-sam/build`.
- `sam local start-api --env-vars env.mock.json --warm-containers EAGER` started all five function containers and mounted all four HTTP routes.
- All four routes returned valid JSON under the expected status codes.
- Non-container build (`sam build --no-use-container`) was separately verified for the CI path; layer output remained `python/builder.py`.

Verified locally:
- Terraform mock-provider full-stack plans for dev and prod
- LocalStack S3/IAM/KMS apply/destroy with 13 boto3 assertions

Not verified:
- Live AWS `sam deploy` or Terraform `apply`
- Production API Gateway/WAF/OpenSearch/GuardDuty/Config deployment
- Lambda cold-start/scale/concurrency behavior under real traffic
- Real Bedrock/OpenSearch integration or Guardrail enforcement

---

## 6. Documentation Changes

| File | Change |
| --- | --- |
| `README.md` | Verified status, accurate prerequisites, mock workflow, corrected Terraform commands, screenshots, limitations |
| `docs/local-testing.md` | Two local modes, layer layout, endpoint overrides, known limitations, project structure |
| `docs/pii-redaction.md` | Guardrails implementation path; Comprehend marked design-only |
| `FEDRAMP-ALIGNMENT.md` | Self-assessment (not authorization) disclaimer and partial-deployment caveat |
| `security/attack-simulation/README.md` | Simulations marked as not executed; deployed controls not assumed |
| `security/injection-mitigation-results.md` | Historical results; Guardrail pass-through now wired |
| `security/iam-least-privilege-validation.md` | Historical results; security module now wired and plan-tested |
| `security/threat-model.md` | Status changed to design baseline |
| `CHANGELOG.md` | Added/fixed/changed entries for this audit |
| `docs/evidence/verification-report.md` | This report |
| `docs/evidence/**` | Raw test results, build logs, screenshots, API console, LocalStack assertions, coverage, SBOM |
| `docs/evidence/README.md` | Evidence index and test-double/emulator disclosure |
| `terraform/modules/api/*` | New API Gateway module |
| `terraform/environments/localstack/*` | LocalStack S3/IAM/KMS apply/verify root |
| `terraform/environments/{dev,prod}/tests/*.tftest.hcl` | Mock-provider full-stack wiring tests |
| `requirements-dev.lock`, `pyproject.toml` | Locked deps, coverage/mypy config |
| `.github/workflows/ci.yml` | Tests, mypy, coverage, pip-audit, SBOM, Terraform tests, SAM build, LocalStack |

---

## 7. Remaining Issues and Limitations

### 7.1 Live AWS integration and model access

- No live-deployment verification was performed.
- The configured inference model is `anthropic.claude-sonnet-5-5`. In the test workstation's account, early read-only smoke attempts returned `ValidationException` ("on-demand throughput isn't supported; use an inference profile") and `AccessDeniedException` ("not available for this account") for inference; embedding calls completed. Model access, region availability, and inference-profile requirements must be validated per deployment account before relying on the default.
- Terraform IAM grants `bedrock:InvokeModel` on foundation-model ARNs only; an inference-profile ARN or additional permissions may be required.
- IAM, KMS, OpenSearch Serverless, WAF, and GuardDuty behavior were not exercised.

### 7.2 Residual Terraform/deployment limitations

- The full stack is **wired** in both roots and passes mock-provider plans, but it
  has not been applied to a live AWS account.
- LocalStack Community covers only the S3/IAM/KMS modules. Bedrock, OpenSearch
  Serverless, WAF, GuardDuty, Config, and API Gateway are plan-validated, not
  apply-tested.
- API Gateway routes use `authorization = "NONE"`. Cognito/JWT authorization is
  not implemented; do not expose the API without adding it.
- No remote S3 backend was configured or tested. `terraform init -backend=false`
  validates configuration but does not prove state migration/locking.
- Provider-specific API semantics (Guardrail version publishing, OpenSearch
  Serverless VPC policy ordering, WAF association) remain unverified live.

### 7.3 Application and security limitations

- Bedrock Guardrail pass-through is implemented, including the Terraform PII
  policy, but no live Guardrail call was tested. Amazon Comprehend is not used.
- Prompt-injection mitigation is regex sanitization plus restricted system
  prompts plus Guardrails when configured; it is defense-in-depth, not a
  guarantee.
- The `/query` endpoint's Lambda-to-Lambda call is verified only through a local
  double. Real cross-function IAM/ARN wiring is unverified.
- API Gateway authentication/authorization (Cognito/JWT) is not implemented;
  CORS, usage plans, and request throttling are not configured in the API module.
- The local AWS doubles accept SigV4 without verification; they are not
  security or compatibility tests.
- `pip-audit` found no known vulnerabilities in the locked dev dependencies;
  container-image scanning and live dependency scanning were not run.

### 7.4 Testing limitations

- Coverage is measured at 88% for application modules; there is no coverage
  threshold gate, and some urllib/OpenSearch HTTP paths remain uncovered by unit
  tests (they are exercised by the E2E doubles).
- mypy passes on application code with `ignore_missing_imports`; it is not a
  strict-mode type gate.
- No live integration tests, contract tests against AWS, load tests,
  failure-injection tests, or performance profiling.
- Browser evidence is of a generated verification console, not a product UI
  (there is no frontend).
- CI was added but not executed on GitHub from this environment.

### 7.5 Environment notes

- SAM's default layer cache under `~/.aws-sam` was blocked by the audit sandbox; `make` targets now use `.aws-sam/layers-pkg` inside the workspace. This is harmless outside the sandbox.
- Tests were run on Python 3.12.7 and Python 3.13.18 in clean virtual environments; Lambda execution used Python 3.13 in Docker.

---

## 8. Final Verdict

**PARTIAL PASS**

The locally runnable application and infrastructure code are in materially better condition than at the start:

- Three critical defects that broke every documented HTTP workflow and the full RAG path were reproduced and fixed.
- All Terraform modules are wired; API Gateway/WAF, RAG layer, S3 trigger, IAM roles, OpenSearch VPC/KMS, and Guardrail version resources were added.
- Bedrock Guardrails pass-through is implemented for inference, including the Terraform PII policy.
- 126 tests pass on Python 3.12 and 3.13; coverage is 88%; mypy, Ruff, SAM/CloudFormation validation, SAM build, Terraform format/validate, mock-provider full-stack plans, 11/11 HTTP E2E cases, 13/13 LocalStack assertions, and 5/5 browser API checks pass. Secret scanning found no committed credentials; Bandit reports no high-severity application findings.

It remains **PARTIAL PASS** rather than PASS because:

- No live AWS deployment or live Bedrock/OpenSearch/IAM verification was performed.
- LocalStack Community covers only S3/IAM/KMS; Bedrock, OpenSearch Serverless, WAF, GuardDuty, Config, and API Gateway are plan-tested only.
- API routes have no authentication/authorization.
- No live Guardrail call was tested, and the configured model may require account-specific access and/or an inference profile.
- CI was not executed on GitHub from this environment.

These limitations are recorded here rather than treated as verified.

---

## 9. Reproduction Commands

```bash
# Dependencies (locked)
python3 -m pip install -r requirements-dev.lock

# Static quality gates
ruff check .
mypy
python3 -m pytest -vv
python3 -m pytest --cov --cov-report=term-missing
sam validate --lint
cfn-lint template.yaml
pip-audit -r requirements-dev.lock
cyclonedx-py requirements requirements-dev.lock --of json -o sbom.cdx.json --validate

# Terraform validation + mock full-stack plans
terraform fmt -check -recursive
(cd terraform/environments/dev && terraform init -backend=false && terraform validate && terraform test -no-color)
(cd terraform/environments/prod && terraform init -backend=false && terraform validate && terraform test -no-color)

# LocalStack S3/IAM/KMS apply/verify/destroy
make localstack-infra-test

# Build
make sam-build

# Local E2E (three terminals)
make mock-aws
make sam-api-mock
make e2e
make screenshots
```

Evidence was generated from commit state with the changes described in §3. Generated `.aws-sam/`, `layers/prompt_builder/{builder,templates}.py`, and `env.mock.json`-driven runtime do not contain production secrets.
