"""Compute infrastructure stack: ECS Fargate service with ALB.

Runs the Streamlit dashboard container behind an Application Load Balancer
with auto-scaling. Receives VPC, ECR, S3, and DynamoDB references from
the network and data stacks via constructor injection.

Optionally integrates AWS Cognito authentication on the ALB listener
when user_pool and user_pool_domain are provided.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    aws_cognito as cognito,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecr_assets,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
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
        user_pool: Optional Cognito user pool for ALB authentication.
        user_pool_domain: Optional Cognito domain for the hosted UI.
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
        user_pool: cognito.IUserPool | None = None,
        user_pool_domain: cognito.UserPoolDomain | None = None,
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
                image=ecs.ContainerImage.from_asset(
                    ".",
                    platform=cdk.aws_ecr_assets.Platform.LINUX_AMD64,
                ),
                container_port=_CONTAINER_PORT,
                environment={
                    "DATA_BUCKET_NAME": data_bucket.bucket_name,
                    "HISTORY_TABLE_NAME": history_table.table_name,
                    "LLM_PROVIDER": "bedrock",
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
        task_role = self.fargate_service.task_definition.task_role
        data_bucket.grant_read_write(task_role)
        history_table.grant_read_write_data(task_role)

        # Grant Bedrock invoke access for AI features (insights, chat, optimizer)
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=["*"],
            )
        )

        # Optional Cognito authentication on ALB listener
        if user_pool is not None and user_pool_domain is not None:
            self._add_cognito_auth(user_pool, user_pool_domain)

        # Cross-stack exports
        CfnOutput(
            self,
            "ServiceUrl",
            value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
            export_name="monopoly-economy-service-url",
        )

    def _add_cognito_auth(
        self,
        user_pool: cognito.IUserPool,
        user_pool_domain: cognito.UserPoolDomain,
    ) -> None:
        """Configure Cognito authentication on the ALB listener.

        Creates a user pool client in this stack (not in the auth stack)
        to avoid circular cross-stack references, since the callback URL
        needs the ALB DNS which lives in this stack.
        """
        alb_dns = self.fargate_service.load_balancer.load_balancer_dns_name

        # Create the client in ComputeStack to avoid circular dependency:
        # AuthStack -> ComputeStack (ALB DNS) and ComputeStack -> AuthStack (UserPool ARN)
        user_pool_client = cognito.UserPoolClient(
            self,
            "AlbUserPoolClient",
            user_pool=user_pool,
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID],
                callback_urls=[
                    cdk.Fn.join("", ["https://", alb_dns, "/oauth2/idpresponse"]),
                ],
            ),
        )

        # Overwrite the default listener action with authenticate -> forward.
        # The ApplicationLoadBalancedFargateService creates a default forward
        # action on the listener. We replace it with a two-step action:
        # 1) Authenticate via Cognito  2) Forward to the target group.
        cfn_listener = self.fargate_service.listener.node.default_child
        cfn_listener.add_property_override(
            "DefaultActions",
            [
                {
                    "Type": "authenticate-cognito",
                    "Order": 1,
                    "AuthenticateCognitoConfig": {
                        "UserPoolArn": user_pool.user_pool_arn,
                        "UserPoolClientId": user_pool_client.user_pool_client_id,
                        "UserPoolDomain": user_pool_domain.domain_name,
                    },
                },
                {
                    "Type": "forward",
                    "Order": 2,
                    "TargetGroupArn": self.fargate_service.target_group.target_group_arn,
                },
            ],
        )
