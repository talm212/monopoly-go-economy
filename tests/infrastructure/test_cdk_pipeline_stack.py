"""Tests for PipelineStack CDK infrastructure.

Verifies:
- Secrets Manager secret created for API key
- SSM parameters created for app config (llm-provider, reward-threshold, churn-boost)
- CloudWatch alarm for unhealthy host count on ALB target group
- CloudWatch alarm for high CPU utilisation on ECS service
- CfnOutputs exported (secret ARN, SSM parameter names)
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.stacks.compute_stack import ComputeStack
from infra.stacks.data_stack import DataStack
from infra.stacks.network_stack import NetworkStack
from infra.stacks.pipeline_stack import PipelineStack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synth_template(env_name: str = "dev") -> Template:
    """Synthesize a PipelineStack with its dependencies and return the Template."""
    app = cdk.App()
    network = NetworkStack(app, "Network", env_name=env_name)
    data = DataStack(app, "Data", env_name=env_name)
    compute = ComputeStack(
        app,
        "Compute",
        vpc=network.vpc,
        ecr_repo=network.ecr_repo,
        data_bucket=data.data_bucket,
        history_table=data.history_table,
        env_name=env_name,
    )
    stack = PipelineStack(
        app,
        "Pipeline",
        fargate_service=compute.fargate_service,
        env_name=env_name,
    )
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# Secrets Manager
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineStackSecrets:
    """Verify Secrets Manager secret for Anthropic API key."""

    def test_secret_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::SecretsManager::Secret", 1)

    def test_secret_has_correct_name(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::SecretsManager::Secret",
            {
                "Description": "Anthropic API key for AI features",
                "Name": "/dev/monopoly-economy/anthropic-api-key",
            },
        )

    def test_secret_name_uses_env_prefix(self) -> None:
        template = _synth_template(env_name="prod")
        template.has_resource_properties(
            "AWS::SecretsManager::Secret",
            {
                "Name": "/prod/monopoly-economy/anthropic-api-key",
            },
        )


# ---------------------------------------------------------------------------
# SSM Parameters
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineStackSsmParameters:
    """Verify SSM parameters for non-secret config."""

    def test_ssm_parameters_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::SSM::Parameter", 3)

    def test_llm_provider_parameter(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/dev/monopoly-economy/llm-provider",
                "Value": "bedrock",
                "Type": "String",
            },
        )

    def test_reward_threshold_parameter(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/dev/monopoly-economy/reward-threshold",
                "Value": "100",
                "Type": "String",
            },
        )

    def test_churn_boost_parameter(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/dev/monopoly-economy/churn-boost",
                "Value": "1.3",
                "Type": "String",
            },
        )


# ---------------------------------------------------------------------------
# CloudWatch Alarms
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineStackAlarms:
    """Verify CloudWatch alarms for service health monitoring."""

    def test_cloudwatch_alarms_created(self) -> None:
        template = _synth_template()
        template.resource_count_is("AWS::CloudWatch::Alarm", 2)

    def test_unhealthy_targets_alarm(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "MetricName": "UnHealthyHostCount",
                "Threshold": 1,
                "EvaluationPeriods": 2,
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "AlarmDescription": "Alert when Fargate targets are unhealthy",
            },
        )

    def test_high_cpu_alarm(self) -> None:
        template = _synth_template()
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "MetricName": "CPUUtilization",
                "Threshold": 85,
                "EvaluationPeriods": 3,
                "AlarmDescription": "Alert when CPU exceeds 85%",
            },
        )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineStackOutputs:
    """Verify CfnOutputs are exported for secrets and SSM parameters."""

    def test_api_key_secret_arn_output(self) -> None:
        template = _synth_template()
        template.has_output(
            "ApiKeySecretArn",
            {"Value": Match.any_value()},
        )

    def test_llm_provider_param_output(self) -> None:
        template = _synth_template()
        template.has_output(
            "LlmProviderParam",
            {"Value": Match.any_value()},
        )
