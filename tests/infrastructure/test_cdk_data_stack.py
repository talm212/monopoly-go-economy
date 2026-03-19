"""Tests for DataStack CDK infrastructure.

Verifies:
- S3 bucket with encryption, versioning, lifecycle, and public access block
- DynamoDB table with on-demand billing, partition/sort keys, and GSI
- CfnOutputs exported for bucket name and table name
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.stacks.data_stack import DataStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synth_template() -> Template:
    """Synthesize a DataStack and return its Template for assertions."""
    app = cdk.App()
    stack = DataStack(app, "TestData")
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDataStackS3:
    """Verify S3 bucket configuration."""

    def test_s3_bucket_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_s3_encryption_enabled(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": Match.object_like(
                    {
                        "ServerSideEncryptionConfiguration": [
                            {
                                "ServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256",
                                },
                            },
                        ],
                    }
                ),
            },
        )

    def test_s3_versioning_enabled(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {"Status": "Enabled"},
            },
        )

    def test_s3_lifecycle_rule_to_ia(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "LifecycleConfiguration": Match.object_like(
                    {
                        "Rules": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "Status": "Enabled",
                                        "Transitions": Match.array_with(
                                            [
                                                Match.object_like(
                                                    {
                                                        "StorageClass": "STANDARD_IA",
                                                        "TransitionInDays": 30,
                                                    }
                                                ),
                                            ]
                                        ),
                                    }
                                ),
                            ]
                        ),
                    }
                ),
            },
        )

    def test_s3_no_public_access(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )


# ---------------------------------------------------------------------------
# DynamoDB
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDataStackDynamoDB:
    """Verify DynamoDB table configuration."""

    def test_dynamodb_table_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_dynamodb_on_demand_billing(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_dynamodb_partition_key_is_run_id(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": Match.array_with(
                    [
                        Match.object_like({"AttributeName": "run_id", "KeyType": "HASH"}),
                    ]
                ),
            },
        )

    def test_dynamodb_sort_key_is_created_at(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": Match.array_with(
                    [
                        Match.object_like({"AttributeName": "created_at", "KeyType": "RANGE"}),
                    ]
                ),
            },
        )

    def test_dynamodb_gsi_for_feature_listing(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IndexName": "feature-created-index",
                                "KeySchema": Match.array_with(
                                    [
                                        Match.object_like(
                                            {
                                                "AttributeName": "feature",
                                                "KeyType": "HASH",
                                            }
                                        ),
                                        Match.object_like(
                                            {
                                                "AttributeName": "created_at",
                                                "KeyType": "RANGE",
                                            }
                                        ),
                                    ]
                                ),
                            }
                        ),
                    ]
                ),
            },
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDataStackOutputs:
    """Verify CfnOutputs are exported for cross-stack references."""

    def test_outputs_exported(self) -> None:
        template = _synth_template()
        template.has_output(
            "DataBucketName",
            {"Value": Match.any_value()},
        )
        template.has_output(
            "HistoryTableName",
            {"Value": Match.any_value()},
        )
