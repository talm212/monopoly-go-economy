"""Data infrastructure stack: S3 bucket and DynamoDB table."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct

_IA_TRANSITION_DAYS = 30


class DataStack(cdk.Stack):
    """S3 + DynamoDB stack for simulation data and run history."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(_IA_TRANSITION_DAYS),
                        ),
                    ],
                ),
            ],
        )

        self.history_table = dynamodb.Table(
            self,
            "SimulationHistory",
            partition_key=dynamodb.Attribute(
                name="run_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True,
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.history_table.add_global_secondary_index(
            index_name="feature-created-index",
            partition_key=dynamodb.Attribute(
                name="feature", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)
        CfnOutput(self, "HistoryTableName", value=self.history_table.table_name)
