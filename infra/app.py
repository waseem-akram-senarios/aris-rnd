#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Tags

from stacks.agent_stack import AgentStack


app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"

# Create CDK environment with account and region
cdk_env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT", "975049910508"),
    region=os.getenv("CDK_DEFAULT_REGION", "us-east-2"),
)

# Create stack with environment context
stack = AgentStack(app, f"intelycx-aris-agent-{env_name}", env=cdk_env)

# Add tags to all resources in the stack
Tags.of(stack).add("Environment", env_name)
Tags.of(stack).add("Project", "intelycx-aris")
Tags.of(stack).add("ManagedBy", "CDK")

app.synth()


