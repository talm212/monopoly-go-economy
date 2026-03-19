"""Network infrastructure stack: VPC, subnets, ECR repository."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import CfnOutput, aws_ec2 as ec2, aws_ecr as ecr
from constructs import Construct

_MAX_AZS = 2
_NAT_GATEWAYS = 1
_SUBNET_CIDR_MASK = 24
_ECR_MAX_IMAGE_COUNT = 10


class NetworkStack(cdk.Stack):
    """Base network stack with VPC and ECR repository."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=_MAX_AZS,
            nat_gateways=_NAT_GATEWAYS,
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

        self.ecr_repo = ecr.Repository(
            self,
            "StreamlitRepo",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=_ECR_MAX_IMAGE_COUNT)],
        )

        CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        CfnOutput(self, "EcrRepoUri", value=self.ecr_repo.repository_uri)
