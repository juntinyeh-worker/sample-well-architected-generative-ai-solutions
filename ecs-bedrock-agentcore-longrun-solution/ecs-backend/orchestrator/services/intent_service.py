"""Intent parsing service using Bedrock Claude."""
import json
import os
import logging
import boto3

logger = logging.getLogger(__name__)

BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

SYSTEM_PROMPT = """You are a frontend router for Kiro CLI, an AI coding assistant powered by AgentCore Runtime.
Given a user message, determine if you should forward it to the agent.
Available tools: ask_agent (sends the user's request to the Kiro CLI AgentCore runtime).

Route ALL substantive questions to ask_agent, including questions about identity, capabilities, coding, AWS, or anything the agent can answer.

Respond ONLY with JSON:
{"tools": ["ask_agent"], "ack": "brief acknowledgment to user", "input": "the user's original request"}

If the user is responding to a previous result (e.g. "yes", "detail", "brief"), respond:
{"tools": [], "ack": "", "follow_up": "brief|detail"}

Only respond directly for trivial greetings (hi, hello, thanks):
{"tools": [], "ack": "your brief response"}"""


def _get_client():
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


async def parse_intent(message: str, pending_tasks: list[dict]) -> dict:
    """Use Claude to parse user intent."""
    client = _get_client()
    context = ""
    if pending_tasks:
        context = f"\nPending results: {json.dumps([{'id': t['id'], 'tool': t['tool']} for t in pending_tasks])}"

    resp = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "system": SYSTEM_PROMPT + context,
            "messages": [{"role": "user", "content": message}],
        }),
    )
    body = json.loads(resp["body"].read())
    text = body["content"][0]["text"]
    try:
        if "```" in text:
            text = text.split("```")[1].strip()
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {"tools": [], "ack": text}
