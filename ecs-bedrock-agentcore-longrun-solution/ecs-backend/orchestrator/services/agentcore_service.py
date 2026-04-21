"""AgentCore Runtime invocation service."""
import json
import os
import logging
import boto3

logger = logging.getLogger(__name__)

AGENTCORE_REGION = os.getenv("AGENTCORE_REGION", "us-west-2")
RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")


def _get_client():
    return boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)


async def invoke_agentcore_runtime(user_input: str) -> dict:
    """Invoke the AgentCore runtime with user input."""
    if not RUNTIME_ARN:
        return {"response": "AgentCore runtime ARN not configured", "error": True}

    client = _get_client()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        payload=json.dumps({"input": user_input}).encode(),
        contentType="application/json",
        accept="application/json",
    )
    body = resp["response"].read().decode()
    return json.loads(body)
