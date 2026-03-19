"""CI/CD pipeline support stack: secrets management and monitoring.

Creates Secrets Manager secrets for sensitive API keys, SSM parameters
for non-secret configuration, and CloudWatch alarms for service health.

NOTE: The actual CodePipeline resource requires a GitHub connection
(manual one-time console setup).  This stack provides the supporting
infrastructure so that a pipeline can be wired in later without changes
to secrets, config, or monitoring.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    aws_cloudwatch as cloudwatch,
    aws_ecs_patterns as ecs_patterns,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
)
from constructs import Construct

_UNHEALTHY_THRESHOLD = 1
_UNHEALTHY_EVAL_PERIODS = 2
_CPU_THRESHOLD_PERCENT = 85
_CPU_EVAL_PERIODS = 3

_DEFAULT_LLM_PROVIDER = "bedrock"
_DEFAULT_REWARD_THRESHOLD = "100"
_DEFAULT_CHURN_BOOST = "1.3"


class PipelineStack(cdk.Stack):
    """CI/CD pipeline, secrets management, and monitoring.

    NOTE: CodePipeline setup requires a GitHub connection (manual one-time
    setup).  This stack creates the supporting infrastructure:
    - Secrets Manager for API keys
    - SSM Parameters for app config
    - CloudWatch alarms for service health

    The actual pipeline can be added later when the GitHub connection is
    established.

    Args:
        scope: CDK app or stage that owns this stack.
        construct_id: Unique stack identifier.
        fargate_service: The ALB Fargate service from the compute stack.
        env_name: Deployment environment name (e.g. "dev", "prod").
        **kwargs: Passed through to cdk.Stack (env, description, etc.).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        fargate_service: ecs_patterns.ApplicationLoadBalancedFargateService,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -- Secrets Manager: Anthropic API key --------------------------------
        self.api_key_secret = secretsmanager.Secret(
            self,
            "AnthropicApiKey",
            description="Anthropic API key for AI features",
            secret_name=f"/monopoly-economy/anthropic-api-key",
        )

        # -- SSM Parameters: non-secret config ---------------------------------
        self.llm_provider_param = ssm.StringParameter(
            self,
            "LlmProvider",
            parameter_name=f"/monopoly-economy/llm-provider",
            string_value=_DEFAULT_LLM_PROVIDER,
            description="LLM provider: bedrock or anthropic",
        )

        self.reward_threshold_param = ssm.StringParameter(
            self,
            "RewardThreshold",
            parameter_name=f"/monopoly-economy/reward-threshold",
            string_value=_DEFAULT_REWARD_THRESHOLD,
            description="Default reward threshold for simulations",
        )

        self.churn_boost_param = ssm.StringParameter(
            self,
            "ChurnBoost",
            parameter_name=f"/monopoly-economy/churn-boost",
            string_value=_DEFAULT_CHURN_BOOST,
            description="Default churn boost multiplier",
        )

        # -- CloudWatch Alarms -------------------------------------------------

        # Unhealthy targets on the ALB target group
        target_group = fargate_service.target_group
        self.unhealthy_alarm = cloudwatch.Alarm(
            self,
            "UnhealthyTargets",
            metric=target_group.metrics.unhealthy_host_count(),
            threshold=_UNHEALTHY_THRESHOLD,
            evaluation_periods=_UNHEALTHY_EVAL_PERIODS,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_description="Alert when Fargate targets are unhealthy",
        )

        # High CPU utilisation on the ECS service
        self.cpu_alarm = cloudwatch.Alarm(
            self,
            "HighCpu",
            metric=fargate_service.service.metric_cpu_utilization(),
            threshold=_CPU_THRESHOLD_PERCENT,
            evaluation_periods=_CPU_EVAL_PERIODS,
            alarm_description="Alert when CPU exceeds 85%",
        )

        # -- Outputs -----------------------------------------------------------
        CfnOutput(self, "ApiKeySecretArn", value=self.api_key_secret.secret_arn)
        CfnOutput(
            self,
            "LlmProviderParam",
            value=self.llm_provider_param.parameter_name,
        )
