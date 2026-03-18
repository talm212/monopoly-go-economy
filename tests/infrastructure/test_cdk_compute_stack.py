"""Tests for ComputeStack CDK infrastructure.

Verifies:
- ECS cluster created
- Fargate service with ALB created
- Task definition CPU/memory configuration (512 / 1024)
- Auto-scaling configured (1-4 tasks, CPU 70%)
- Container port 8501 (Streamlit)
- Environment variables for bucket name and table name
- CfnOutput for service URL
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.stacks.compute_stack import ComputeStack
from infra.stacks.data_stack import DataStack
from infra.stacks.network_stack import NetworkStack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synth_template(env_name: str = "dev") -> Template:
    """Synthesize a ComputeStack with its dependencies and return the Template."""
    app = cdk.App()
    network = NetworkStack(app, "Network", env_name=env_name)
    data = DataStack(app, "Data", env_name=env_name)
    stack = ComputeStack(
        app,
        "Compute",
        vpc=network.vpc,
        ecr_repo=network.ecr_repo,
        data_bucket=data.data_bucket,
        history_table=data.history_table,
        env_name=env_name,
    )
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackCluster:
    """Verify ECS cluster is created."""

    def test_ecs_cluster_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::ECS::Cluster", 1)


# ---------------------------------------------------------------------------
# Fargate Service & ALB
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackFargateService:
    """Verify Fargate service and ALB configuration."""

    def test_fargate_service_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::ECS::Service", 1)

    def test_alb_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 1)

    def test_task_definition_cpu_memory(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "Cpu": "512",
                "Memory": "1024",
            },
        )

    def test_container_port_8501(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "PortMappings": Match.array_with(
                                    [
                                        Match.object_like(
                                            {"ContainerPort": 8501}
                                        ),
                                    ]
                                ),
                            }
                        ),
                    ]
                ),
            },
        )

    def test_environment_variables_set(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Environment": Match.array_with(
                                    [
                                        Match.object_like(
                                            {"Name": "DATA_BUCKET_NAME"}
                                        ),
                                        Match.object_like(
                                            {"Name": "HISTORY_TABLE_NAME"}
                                        ),
                                        Match.object_like(
                                            {
                                                "Name": "LLM_PROVIDER",
                                                "Value": "bedrock",
                                            }
                                        ),
                                        Match.object_like(
                                            {
                                                "Name": "ENV_NAME",
                                                "Value": "dev",
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
# Auto-Scaling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackAutoScaling:
    """Verify auto-scaling configuration."""

    def test_auto_scaling_configured(self) -> None:
        template = _synth_template()
        # Scalable target defines min/max capacity
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalableTarget",
            {
                "MinCapacity": 1,
                "MaxCapacity": 4,
            },
        )

    def test_cpu_scaling_policy(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalingPolicy",
            {
                "TargetTrackingScalingPolicyConfiguration": Match.object_like(
                    {
                        "TargetValue": 70,
                        "PredefinedMetricSpecification": Match.object_like(
                            {
                                "PredefinedMetricType": "ECSServiceAverageCPUUtilization",
                            }
                        ),
                    }
                ),
            },
        )


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackHealthCheck:
    """Verify target group health check."""

    def test_health_check_path(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "HealthCheckPath": "/_stcore/health",
                "Matcher": Match.object_like({"HttpCode": "200"}),
            },
        )


# ---------------------------------------------------------------------------
# IAM Permissions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackPermissions:
    """Verify task role has correct IAM permissions."""

    def test_s3_read_write_policy(self) -> None:
        template = _synth_template()
        # The task role should have an IAM policy granting S3 access
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": Match.object_like(
                    {
                        "Statement": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "Action": Match.array_with(
                                            ["s3:GetObject*"]
                                        ),
                                        "Effect": "Allow",
                                    }
                                ),
                            ]
                        ),
                    }
                ),
            },
        )

    def test_dynamodb_read_write_policy(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": Match.object_like(
                    {
                        "Statement": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "Action": Match.array_with(
                                            ["dynamodb:BatchGetItem"]
                                        ),
                                        "Effect": "Allow",
                                    }
                                ),
                            ]
                        ),
                    }
                ),
            },
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackOutputs:
    """Verify CfnOutputs are exported for the service URL."""

    def test_service_url_output_exported(self) -> None:
        template = _synth_template(env_name="dev")
        template.has_output(
            "ServiceUrl",
            {"Export": {"Name": "dev-service-url"}},
        )

    def test_prod_output_uses_prod_prefix(self) -> None:
        template = _synth_template(env_name="prod")
        template.has_output(
            "ServiceUrl",
            {"Export": {"Name": "prod-service-url"}},
        )
