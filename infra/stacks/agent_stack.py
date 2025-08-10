from aws_cdk import Stack
from constructs import Construct


class AgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        # Placeholder: add ECS service, ALB, and secret wiring in follow-up edits


