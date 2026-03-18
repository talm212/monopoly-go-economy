#!/usr/bin/env python3
"""CDK application entry point for Monopoly Go Economy infrastructure."""

from __future__ import annotations

import aws_cdk as cdk

from infra.stacks.network_stack import NetworkStack

app = cdk.App()

env_name: str = app.node.try_get_context("env") or "dev"

NetworkStack(
    app,
    f"MonopolyEconomy-Network-{env_name}",
    env=cdk.Environment(region="us-east-1"),
    env_name=env_name,
)

app.synth()
