"""Compute infrastructure stack: ECS Fargate service with ALB.

Runs the Streamlit dashboard container behind an Application Load Balancer
with auto-scaling. Receives VPC, ECR, S3, and DynamoDB references from
the network and data stacks via constructor injection.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct

_TASK_CPU = 512
_TASK_MEMORY_MIB = 1024
_CONTAINER_PORT = 8501
_DESIRED_COUNT = 1
_MIN_CAPACITY = 1
_MAX_CAPACITY = 4
_CPU_TARGET_UTILIZATION_PERCENT = 70
_HEALTH_CHECK_PATH = "/_stcore/health"


class ComputeStack(cdk.Stack):
    """ECS Fargate + ALB stack for the Streamlit dashboard.

    Args:
        scope: CDK app or stage that owns this stack.
        construct_id: Unique stack identifier.
        vpc: VPC to deploy the Fargate service into.
        ecr_repo: ECR repository containing the Streamlit container image.
        data_bucket: S3 bucket for player data and simulation results.
        history_table: DynamoDB table for simulation run history.
        env_name: Deployment environment name (e.g. "dev", "prod").
        **kwargs: Passed through to cdk.Stack (env, description, etc.).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        ecr_repo: ecr.IRepository,
        data_bucket: s3.IBucket,
        history_table: dynamodb.ITable,
        env_name: str = "dev",
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        # Fargate service with ALB
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "StreamlitService",
            cluster=cluster,
            cpu=_TASK_CPU,
            memory_limit_mib=_TASK_MEMORY_MIB,
            desired_count=_DESIRED_COUNT,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(ecr_repo),
                container_port=_CONTAINER_PORT,
                environment={
                    "DATA_BUCKET_NAME": data_bucket.bucket_name,
                    "HISTORY_TABLE_NAME": history_table.table_name,
                    "LLM_PROVIDER": "bedrock",
                    "ENV_NAME": env_name,
                },
            ),
            public_load_balancer=True,
        )

        # Streamlit health check endpoint
        self.fargate_service.target_group.configure_health_check(
            path=_HEALTH_CHECK_PATH,
            healthy_http_codes="200",
        )

        # Auto-scaling
        scaling = self.fargate_service.service.auto_scale_task_count(
            min_capacity=_MIN_CAPACITY,
            max_capacity=_MAX_CAPACITY,
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=_CPU_TARGET_UTILIZATION_PERCENT,
        )

        # Grant the task role access to data resources
        data_bucket.grant_read_write(self.fargate_service.task_definition.task_role)
        history_table.grant_read_write_data(
            self.fargate_service.task_definition.task_role
        )

        # Cross-stack exports
        CfnOutput(
            self,
            "ServiceUrl",
            value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
            export_name=f"{env_name}-service-url",
        )
