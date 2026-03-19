#!/usr/bin/env python3
"""CDK application entry point for Monopoly Go Economy infrastructure."""

from __future__ import annotations

import aws_cdk as cdk

from infra.stacks.compute_stack import ComputeStack
from infra.stacks.data_stack import DataStack
from infra.stacks.network_stack import NetworkStack
from infra.stacks.pipeline_stack import PipelineStack

app = cdk.App()

_ENV = cdk.Environment(account="585008046382", region="us-east-1")

network_stack = NetworkStack(app, "MonopolyEconomy-Network", env=_ENV)

data_stack = DataStack(app, "MonopolyEconomy-Data", env=_ENV)

compute_stack = ComputeStack(
    app,
    "MonopolyEconomy-Compute",
    vpc=network_stack.vpc,
    ecr_repo=network_stack.ecr_repo,
    data_bucket=data_stack.data_bucket,
    history_table=data_stack.history_table,
    env=_ENV,
)

PipelineStack(
    app,
    "MonopolyEconomy-Pipeline",
    fargate_service=compute_stack.fargate_service,
    env=_ENV,
)

app.synth()
