"""Data infrastructure stack: S3 bucket and DynamoDB table.

Provides storage for player data, simulation results (S3), and
simulation run history (DynamoDB) that the compute stack consumes
via exported outputs.
"""

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
    """S3 + DynamoDB stack for simulation data and run history.

    Args:
        scope: CDK app or stage that owns this stack.
        construct_id: Unique stack identifier.
        env_name: Deployment environment name (e.g. "dev", "prod").
            Controls removal policies and auto-delete behaviour.
        **kwargs: Passed through to cdk.Stack (env, description, etc.).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str = "dev",
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_dev = env_name == "dev"

        # S3 bucket for player data and simulation results
        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY if is_dev else RemovalPolicy.RETAIN,
            auto_delete_objects=is_dev,
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

        # DynamoDB table for simulation run history
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
            point_in_time_recovery=not is_dev,
            removal_policy=RemovalPolicy.DESTROY if is_dev else RemovalPolicy.RETAIN,
        )

        # GSI for listing runs by feature
        self.history_table.add_global_secondary_index(
            index_name="feature-created-index",
            partition_key=dynamodb.Attribute(
                name="feature", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        # Cross-stack exports
        CfnOutput(
            self,
            "DataBucketName",
            value=self.data_bucket.bucket_name,
            export_name=f"{env_name}-data-bucket-name",
        )
        CfnOutput(
            self,
            "HistoryTableName",
            value=self.history_table.table_name,
            export_name=f"{env_name}-history-table-name",
        )
