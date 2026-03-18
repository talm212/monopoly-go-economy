#!/usr/bin/env python3
"""CDK application entry point for Monopoly Go Economy infrastructure."""

from __future__ import annotations

import aws_cdk as cdk

from infra.stacks.compute_stack import ComputeStack
from infra.stacks.data_stack import DataStack
from infra.stacks.network_stack import NetworkStack
from infra.stacks.pipeline_stack import PipelineStack

app = cdk.App()

env_name: str = app.node.try_get_context("env") or "dev"

network_stack = NetworkStack(
    app,
    f"MonopolyEconomy-Network-{env_name}",
    env=cdk.Environment(region="us-east-1"),
    env_name=env_name,
)

data_stack = DataStack(
    app,
    f"MonopolyEconomy-Data-{env_name}",
    env=cdk.Environment(region="us-east-1"),
    env_name=env_name,
)

compute_stack = ComputeStack(
    app,
    f"MonopolyEconomy-Compute-{env_name}",
    vpc=network_stack.vpc,
    ecr_repo=network_stack.ecr_repo,
    data_bucket=data_stack.data_bucket,
    history_table=data_stack.history_table,
    env=cdk.Environment(region="us-east-1"),
    env_name=env_name,
)

PipelineStack(
    app,
    f"MonopolyEconomy-Pipeline-{env_name}",
    fargate_service=compute_stack.fargate_service,
    env=cdk.Environment(region="us-east-1"),
    env_name=env_name,
)

app.synth()
