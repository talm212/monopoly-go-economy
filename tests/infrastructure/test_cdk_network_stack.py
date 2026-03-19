"""Tests for NetworkStack CDK infrastructure.

Verifies:
- VPC created with expected subnet configuration
- ECR repository created with lifecycle rules
- CfnOutputs exported for VPC ID and ECR repo URI
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.stacks.network_stack import NetworkStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synth_template() -> Template:
    """Synthesize a NetworkStack and return its Template for assertions."""
    app = cdk.App()
    stack = NetworkStack(app, "TestNetwork")
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNetworkStackVpc:
    """Verify VPC resource configuration."""

    def test_vpc_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::EC2::VPC", 1)

    def test_vpc_has_private_subnets(self) -> None:
        template = _synth_template()
        # Private subnets have a route to a NAT gateway
        template.resource_count_is("AWS::EC2::NatGateway", 1)
        # Each AZ gets a public + private subnet; 2 AZs = 4 subnets total
        template.resource_count_is("AWS::EC2::Subnet", 4)


# ---------------------------------------------------------------------------
# ECR
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNetworkStackEcr:
    """Verify ECR repository configuration."""

    def test_ecr_repository_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::ECR::Repository", 1)

    def test_ecr_has_lifecycle_rule(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {
                "LifecyclePolicy": Match.object_like({"LifecyclePolicyText": Match.any_value()}),
            },
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNetworkStackOutputs:
    """Verify CfnOutputs are exported for cross-stack references."""

    def test_vpc_id_output_exported(self) -> None:
        template = _synth_template()
        template.has_output(
            "VpcId",
            {"Value": Match.any_value()},
        )

    def test_ecr_repo_uri_output_exported(self) -> None:
        template = _synth_template()
        template.has_output(
            "EcrRepoUri",
            {"Value": Match.any_value()},
        )
