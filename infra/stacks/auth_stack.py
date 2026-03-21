"""Authentication infrastructure stack: Cognito user pool and domain.

Provides AWS Cognito resources for ALB-integrated authentication.
Self-sign-up is disabled — only administrators can create user accounts.
The user pool is retained on stack deletion to preserve user data.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import CfnOutput, aws_cognito as cognito
from constructs import Construct

_PASSWORD_MIN_LENGTH = 12
_COGNITO_DOMAIN_PREFIX = "monopoly-economy"


class AuthStack(cdk.Stack):
    """Cognito user pool and domain for dashboard authentication.

    Args:
        scope: CDK app or stage that owns this stack.
        construct_id: Unique stack identifier.
        **kwargs: Passed through to cdk.Stack (env, description, etc.).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # User pool with email sign-in, admin-only user creation
        self.user_pool = cognito.UserPool(
            self,
            "EconomyTeamUsers",
            user_pool_name="monopoly-economy-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=_PASSWORD_MIN_LENGTH,
                require_lowercase=True,
                require_digits=True,
                require_uppercase=True,
                require_symbols=True,
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(otp=True, sms=False),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # Cognito-hosted UI domain for OAuth flows
        self.user_pool_domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=_COGNITO_DOMAIN_PREFIX,
            ),
        )

        # Outputs
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(
            self,
            "UserPoolDomainName",
            value=self.user_pool_domain.domain_name,
        )
