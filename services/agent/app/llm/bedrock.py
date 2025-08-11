from typing import Dict, Any, Optional
import logging

import boto3


class BedrockClient:
    def __init__(self, region: str):
        config = boto3.session.Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 2})
        self._client = boto3.client("bedrock-runtime", region_name=region, config=config)
        self._logger = logging.getLogger("llm.bedrock")

    def converse(self, model_id: str, messages: list[Dict[str, Any]], system: Optional[list] = None, temperature: float = 0.0) -> str:
        self._logger.info(f"Bedrock.converse model_id={model_id} temp={temperature} msgs={len(messages)}")
        resp = self._client.converse(
            modelId=model_id,
            messages=messages,
            system=system or [],
            inferenceConfig={"temperature": temperature},
        )
        self._logger.debug(f"Bedrock raw response keys: {list(resp.keys())}")
        message = resp["output"]["message"]
        return "\n".join([c.get("text", "") for c in message.get("content", [])])


