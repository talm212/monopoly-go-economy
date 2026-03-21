"""Tests for AuthStack and Cognito integration in ComputeStack.

Verifies:
- AuthStack creates a Cognito UserPool
- Self-sign-up is disabled (admin-only)
- Email sign-in is configured
- Password policy enforces min length 12, lowercase, digits, uppercase, symbols
- User pool domain is created
- User pool has RETAIN removal policy
- ComputeStack synthesizes without auth (backward compatible)
- ComputeStack with auth creates a user pool client and listener rule
"""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infra.stacks.auth_stack import AuthStack
from infra.stacks.compute_stack import ComputeStack
from infra.stacks.data_stack import DataStack
from infra.stacks.network_stack import NetworkStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _synth_auth_template() -> Template:
    """Synthesize an AuthStack and return the Template."""
    app = cdk.App()
    stack = AuthStack(app, "TestAuth")
    return Template.from_stack(stack)


def _synth_compute_without_auth() -> Template:
    """Synthesize ComputeStack without auth params (backward compatible)."""
    app = cdk.App()
    network = NetworkStack(app, "Network")
    data = DataStack(app, "Data")
    stack = ComputeStack(
        app,
        "Compute",
        vpc=network.vpc,
        ecr_repo=network.ecr_repo,
        data_bucket=data.data_bucket,
        history_table=data.history_table,
    )
    return Template.from_stack(stack)


def _synth_compute_with_auth() -> Template:
    """Synthesize ComputeStack with Cognito auth enabled."""
    app = cdk.App()
    network = NetworkStack(app, "Network")
    data = DataStack(app, "Data")
    auth = AuthStack(app, "Auth")
    stack = ComputeStack(
        app,
        "Compute",
        vpc=network.vpc,
        ecr_repo=network.ecr_repo,
        data_bucket=data.data_bucket,
        history_table=data.history_table,
        user_pool=auth.user_pool,
        user_pool_domain=auth.user_pool_domain,
    )
    return Template.from_stack(stack)


# ---------------------------------------------------------------------------
# AuthStack — User Pool
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthStackUserPool:
    """Verify Cognito UserPool configuration."""

    def test_user_pool_created(self) -> None:
        template = _synth_auth_template()
        template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_self_sign_up_disabled(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "AdminCreateUserConfig": Match.object_like(
                    {"AllowAdminCreateUserOnly": True}
                ),
            },
        )

    def test_email_sign_in(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "UsernameAttributes": ["email"],
            },
        )

    def test_auto_verify_email(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "AutoVerifiedAttributes": ["email"],
            },
        )

    def test_password_policy(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": Match.object_like(
                    {
                        "PasswordPolicy": Match.object_like(
                            {
                                "MinimumLength": 12,
                                "RequireLowercase": True,
                                "RequireNumbers": True,
                                "RequireUppercase": True,
                                "RequireSymbols": True,
                            }
                        ),
                    }
                ),
            },
        )

    def test_mfa_optional(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "MfaConfiguration": "OPTIONAL",
                "EnabledMfas": ["SOFTWARE_TOKEN_MFA"],
            },
        )

    def test_user_pool_retained_on_delete(self) -> None:
        template = _synth_auth_template()
        template.has_resource(
            "AWS::Cognito::UserPool",
            {
                "DeletionPolicy": "Retain",
                "UpdateReplacePolicy": "Retain",
            },
        )


# ---------------------------------------------------------------------------
# AuthStack — Domain
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthStackDomain:
    """Verify Cognito user pool domain."""

    def test_user_pool_domain_created(self) -> None:
        template = _synth_auth_template()
        template.resource_count_is("AWS::Cognito::UserPoolDomain", 1)

    def test_domain_prefix(self) -> None:
        template = _synth_auth_template()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolDomain",
            {
                "Domain": "monopoly-economy",
            },
        )


# ---------------------------------------------------------------------------
# AuthStack — Outputs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthStackOutputs:
    """Verify CfnOutputs from AuthStack."""

    def test_user_pool_id_output(self) -> None:
        template = _synth_auth_template()
        template.has_output("UserPoolId", {"Value": Match.any_value()})

    def test_user_pool_domain_output(self) -> None:
        template = _synth_auth_template()
        template.has_output("UserPoolDomainName", {"Value": Match.any_value()})


# ---------------------------------------------------------------------------
# ComputeStack — Backward Compatibility (no auth)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackWithoutAuth:
    """Verify ComputeStack works without auth params."""

    def test_synthesizes_without_auth(self) -> None:
        template = _synth_compute_without_auth()
        template.resource_count_is("AWS::ECS::Service", 1)

    def test_no_cognito_resources_without_auth(self) -> None:
        template = _synth_compute_without_auth()
        template.resource_count_is("AWS::Cognito::UserPoolClient", 0)


# ---------------------------------------------------------------------------
# ComputeStack — With Cognito Auth
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeStackWithAuth:
    """Verify ComputeStack creates Cognito auth resources when enabled."""

    def test_user_pool_client_created(self) -> None:
        template = _synth_compute_with_auth()
        template.resource_count_is("AWS::Cognito::UserPoolClient", 1)

    def test_user_pool_client_generates_secret(self) -> None:
        template = _synth_compute_with_auth()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "GenerateSecret": True,
            },
        )

    def test_user_pool_client_auth_code_grant(self) -> None:
        template = _synth_compute_with_auth()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "AllowedOAuthFlows": ["code"],
            },
        )

    def test_user_pool_client_openid_scope(self) -> None:
        template = _synth_compute_with_auth()
        template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "AllowedOAuthScopes": ["openid"],
            },
        )

    def test_listener_default_actions_include_cognito_auth(self) -> None:
        template = _synth_compute_with_auth()
        # The listener default actions should authenticate via Cognito
        # then forward to the target group.
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::Listener",
            {
                "DefaultActions": Match.array_with(
                    [
                        Match.object_like(
                            {"Type": "authenticate-cognito", "Order": 1}
                        ),
                        Match.object_like(
                            {"Type": "forward", "Order": 2}
                        ),
                    ]
                ),
            },
        )

    def test_ecs_service_still_created_with_auth(self) -> None:
        template = _synth_compute_with_auth()
        template.resource_count_is("AWS::ECS::Service", 1)
