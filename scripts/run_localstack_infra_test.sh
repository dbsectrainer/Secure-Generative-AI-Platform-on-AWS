#!/usr/bin/env bash
# Run the LocalStack-backed Terraform infrastructure test.
#
# This uses LocalStack Community (S3, IAM, KMS, STS) to apply the S3/IAM
# modules, verify the resources with boto3, and destroy them. Services that
# LocalStack Community does not support are covered by Terraform mock-provider
# tests (terraform test).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/terraform/environments/localstack"
OUT_DIR="$ROOT/docs/evidence/test-results"
CONTAINER_NAME="secgenai-localstack"
LOCALSTACK_IMAGE="${LOCALSTACK_IMAGE:-localstack/localstack:3.8}"
ENDPOINT="${LOCALSTACK_ENDPOINT:-http://127.0.0.1:4566}"

mkdir -p "$OUT_DIR"

started_container=0

cleanup() {
  status=$?
  if command -v terraform >/dev/null 2>&1 && [ -d "$TF_DIR/.terraform" ]; then
    echo "Destroying LocalStack Terraform resources (best effort)…"
    (cd "$TF_DIR" && terraform destroy -auto-approve -input=false -no-color) \
      >"$OUT_DIR/localstack-destroy.log" 2>&1 || true
  fi
  if [ "$started_container" -eq 1 ]; then
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT

if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  if ! docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Starting LocalStack Community ($LOCALSTACK_IMAGE)…"
    docker run -d --name "$CONTAINER_NAME" -p 4566:4566 \
      -e SERVICES=s3,iam,kms,logs,lambda,ec2,sns,sqs,cloudwatch,cloudformation,sts,opensearch,wafv2,guardduty,config \
      "$LOCALSTACK_IMAGE" >/dev/null
    started_container=1
  else
    echo "Starting existing LocalStack container…"
    docker start "$CONTAINER_NAME" >/dev/null
    started_container=1
  fi
  for _ in $(seq 1 90); do
    if curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi

if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "ERROR: LocalStack is not reachable at $ENDPOINT" >&2
  exit 1
fi

echo "Running Terraform against LocalStack…"
(cd "$TF_DIR" &&
  terraform init -backend=false -input=false -no-color &&
  terraform fmt -check -recursive &&
  terraform validate -no-color &&
  terraform apply -auto-approve -input=false -no-color) \
  >"$OUT_DIR/localstack-terraform.log" 2>&1
apply_status=$?
if [ "$apply_status" -ne 0 ]; then
  echo "ERROR: Terraform apply failed; see $OUT_DIR/localstack-terraform.log" >&2
  exit "$apply_status"
fi

echo "Verifying resources with boto3…"
python3 "$ROOT/scripts/localstack_infra_test.py" \
  --endpoint "$ENDPOINT" \
  --terraform-dir "$TF_DIR" \
  --output "$OUT_DIR/localstack-assertions.json" \
  2>&1 | tee "$OUT_DIR/localstack-assertions.log"
verify_status=${PIPESTATUS[0]}

# cleanup() runs destroy and exits with verify_status.
exit "$verify_status"
