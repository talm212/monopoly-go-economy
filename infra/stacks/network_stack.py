"""Network infrastructure stack: VPC, subnets, ECR repository.

Provides the foundational networking and container registry resources
that other stacks (compute, dashboard) depend on via exported outputs.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import CfnOutput, aws_ec2 as ec2, aws_ecr as ecr
from constructs import Construct

_DEV_NAT_GATEWAYS = 1
_PROD_NAT_GATEWAYS = 2
_MAX_AZS = 2
_SUBNET_CIDR_MASK = 24
_ECR_MAX_IMAGE_COUNT = 10


class NetworkStack(cdk.Stack):
    """Base network stack with VPC and ECR repository.

    Args:
        scope: CDK app or stage that owns this stack.
        construct_id: Unique stack identifier.
        env_name: Deployment environment name (e.g. "dev", "prod").
            Controls NAT gateway count and ECR removal policy.
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

        is_prod = env_name == "prod"

        # VPC with 2 AZs, public + private subnets
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=_MAX_AZS,
            nat_gateways=_PROD_NAT_GATEWAYS if is_prod else _DEV_NAT_GATEWAYS,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=_SUBNET_CIDR_MASK,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=_SUBNET_CIDR_MASK,
                ),
            ],
        )

        # ECR repository for Streamlit container images
        self.ecr_repo = ecr.Repository(
            self,
            "StreamlitRepo",
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY
            ),
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=_ECR_MAX_IMAGE_COUNT)],
        )

        # Cross-stack exports
        CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            export_name=f"{env_name}-vpc-id",
        )
        CfnOutput(
            self,
            "EcrRepoUri",
            value=self.ecr_repo.repository_uri,
            export_name=f"{env_name}-ecr-repo-uri",
        )
