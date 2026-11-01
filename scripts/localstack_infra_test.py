#!/usr/bin/env python3
"""
Verify the Terraform-created LocalStack resources with boto3.

Run after:
    terraform -chdir=terraform/environments/localstack apply -auto-approve

This is a local infrastructure test. It validates the S3/KMS/IAM modules that
LocalStack Community supports; it does not validate Bedrock, OpenSearch
Serverless, WAF, GuardDuty, or Config.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def _terraform_outputs(directory: Path) -> dict[str, object]:
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
    )
    raw = json.loads(result.stdout)
    return {key: value["value"] for key, value in raw.items()}


def _record(checks: list[dict[str, object]], name: str, ok: bool, detail: object) -> None:
    checks.append({"name": name, "passed": bool(ok), "detail": detail})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terraform-dir",
        default="terraform/environments/localstack",
        help="Terraform root for the LocalStack environment",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:4566")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", default="docs/evidence/test-results/localstack-assertions.json")
    args = parser.parse_args()

    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", args.region)

    outputs = _terraform_outputs(Path(args.terraform_dir))
    bucket = str(outputs["document_bucket_name"])
    key_arn = str(outputs["kms_key_arn"])
    role_arns = [
        str(outputs["orchestrator_role_arn"]),
        str(outputs["embedding_role_arn"]),
        str(outputs["retrieval_role_arn"]),
        str(outputs["rag_orchestrator_role_arn"]),
    ]

    config = Config(
        region_name=args.region,
        retries={"max_attempts": 2, "mode": "standard"},
        connect_timeout=5,
        read_timeout=30,
    )
    s3 = boto3.client("s3", endpoint_url=args.endpoint, config=config)
    kms = boto3.client("kms", endpoint_url=args.endpoint, config=config)
    iam = boto3.client("iam", endpoint_url=args.endpoint, config=config)

    checks: list[dict[str, object]] = []

    # ── S3 ──────────────────────────────────────────────────────────────────
    try:
        s3.head_bucket(Bucket=bucket)
        _record(checks, "s3_bucket_exists", True, bucket)
    except ClientError as exc:
        _record(checks, "s3_bucket_exists", False, str(exc))

    try:
        versioning = s3.get_bucket_versioning(Bucket=bucket)
        status = versioning.get("Status")
        _record(checks, "s3_versioning_enabled", status == "Enabled", status)
    except ClientError as exc:
        _record(checks, "s3_versioning_enabled", False, str(exc))

    try:
        encryption = s3.get_bucket_encryption(Bucket=bucket)
        rule = encryption["ServerSideEncryptionConfiguration"]["Rules"][0][
            "ApplyServerSideEncryptionByDefault"
        ]
        _record(
            checks,
            "s3_kms_encryption",
            rule.get("SSEAlgorithm") == "aws:kms" and rule.get("KMSMasterKeyID") == key_arn,
            rule,
        )
    except ClientError as exc:
        _record(checks, "s3_kms_encryption", False, str(exc))

    try:
        pab = s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"]
        _record(
            checks,
            "s3_public_access_blocked",
            all(
                pab.get(flag, False)
                for flag in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            ),
            pab,
        )
    except ClientError as exc:
        _record(checks, "s3_public_access_blocked", False, str(exc))

    try:
        policy = json.loads(s3.get_bucket_policy(Bucket=bucket)["Policy"])
        statements = policy.get("Statement", [])
        has_tls_deny = any(statement.get("Sid") == "DenyNonTLSRequests" for statement in statements)
        has_checksum = any(statement.get("Sid") == "RequireChecksumOnUpload" for statement in statements)
        _record(
            checks,
            "s3_bucket_policy_controls",
            has_tls_deny and has_checksum,
            {"DenyNonTLSRequests": has_tls_deny, "RequireChecksumOnUpload": has_checksum},
        )
    except ClientError as exc:
        _record(checks, "s3_bucket_policy_controls", False, str(exc))

    object_key = "raw/localstack-smoke.txt"
    object_body = b"localstack terraform integration test"
    try:
        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=object_body,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=key_arn,
            ChecksumAlgorithm="SHA256",
        )
        fetched = s3.get_object(Bucket=bucket, Key=object_key)["Body"].read()
        head = s3.head_object(Bucket=bucket, Key=object_key)
        _record(
            checks,
            "s3_write_read_roundtrip",
            fetched == object_body,
            {"bytes": len(fetched), "sse": head.get("ServerSideEncryption")},
        )
    except ClientError as exc:
        _record(checks, "s3_write_read_roundtrip", False, str(exc))
    finally:
        try:
            s3.delete_object(Bucket=bucket, Key=object_key)
        except ClientError:
            pass

    # ── KMS ─────────────────────────────────────────────────────────────────
    try:
        key = kms.describe_key(KeyId=key_arn)["KeyMetadata"]
        _record(checks, "kms_key_enabled", key.get("Enabled") is True, key.get("KeyState"))
    except ClientError as exc:
        _record(checks, "kms_key_enabled", False, str(exc))

    try:
        rotation = kms.get_key_rotation_status(KeyId=key_arn)
        _record(
            checks,
            "kms_key_rotation_enabled",
            rotation.get("KeyRotationEnabled") is True,
            rotation.get("KeyRotationEnabled"),
        )
    except ClientError as exc:
        _record(checks, "kms_key_rotation_enabled", False, str(exc))

    # ── Cleanup object versions so Terraform can delete the bucket ──────────
    try:
        versions = s3.list_object_versions(Bucket=bucket)
        version_ids = [
            (item["Key"], item["VersionId"]) for item in versions.get("Versions", [])
        ] + [
            (item["Key"], item["VersionId"])
            for item in versions.get("DeleteMarkers", [])
        ]
        for key, version_id in version_ids:
            s3.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
        _record(
            checks,
            "s3_versions_cleaned",
            True,
            f"{len(version_ids)} version(s)/delete marker(s) removed",
        )
    except ClientError as exc:
        _record(checks, "s3_versions_cleaned", False, str(exc))

    # ── IAM ─────────────────────────────────────────────────────────────────
    for role_arn in role_arns:
        role_name = role_arn.rsplit("/", 1)[-1]
        try:
            iam.get_role(RoleName=role_name)
            attachments = iam.list_attached_role_policies(RoleName=role_name).get(
                "AttachedPolicies", []
            )
            _record(
                checks,
                f"iam_role_{role_name}",
                len(attachments) >= 2,
                [policy["PolicyName"] for policy in attachments],
            )
        except ClientError as exc:
            _record(checks, f"iam_role_{role_name}", False, str(exc))

    passed = sum(1 for check in checks if check["passed"])
    report = {
        "endpoint": args.endpoint,
        "terraform_dir": args.terraform_dir,
        "bucket": bucket,
        "kms_key_arn": key_arn,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "failed": len(checks) - passed,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(checks)} checks passed; evidence: {output_path}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
