"""
Moto-backed integration test for the ingestion Lambda's S3 path.

This exercises real boto3 S3 request/response handling against Moto's in-memory
AWS emulation instead of patching `get_object`. The embedding Lambda invoke is
still mocked because the ingestion handler only needs to verify the dispatch
payload; Lambda container execution is a separate concern.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def _aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


@mock_aws
def test_ingestion_reads_s3_object_and_dispatches_embedding():
    import handler

    s3 = boto3.client("s3", region_name="eu-west-1")
    s3.create_bucket(
        Bucket="local-test-document-bucket",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )
    s3.put_object(
        Bucket="local-test-document-bucket",
        Key="raw/moto-document.txt",
        Body=("The retention policy requires seven years of audit logs. " * 30).encode(),
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "local-test-document-bucket"},
                    "object": {"key": "raw/moto-document.txt"},
                }
            }
        ]
    }

    with patch.object(handler._lambda_client, "invoke") as mock_invoke:
        mock_invoke.return_value = {}
        result = handler.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert result["body"]["processed"] == 1
    assert result["body"]["results"][0]["chunks_dispatched"] >= 1

    assert mock_invoke.call_count == result["body"]["results"][0]["chunks_dispatched"]
    first_payload = json.loads(mock_invoke.call_args_list[0].kwargs["Payload"])
    assert first_payload["metadata"]["document_key"] == "raw/moto-document.txt"
    assert first_payload["metadata"]["chunk_index"] == 0
    assert first_payload["text"]


@mock_aws
def test_ingestion_reports_missing_s3_object():
    import handler

    s3 = boto3.client("s3", region_name="eu-west-1")
    s3.create_bucket(
        Bucket="local-test-document-bucket",
        CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
    )

    event = {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "local-test-document-bucket"},
                    "object": {"key": "raw/missing.txt"},
                }
            }
        ]
    }

    result = handler.lambda_handler(event, None)

    assert result["statusCode"] == 207
    assert result["body"]["errors"][0]["key"] == "raw/missing.txt"
