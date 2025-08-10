#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.agent_stack import AgentStack


app = cdk.App()

env_name = app.node.try_get_context("env") or "dev"

AgentStack(app, f"intelycx-aris-agent-{env_name}")

app.synth()


