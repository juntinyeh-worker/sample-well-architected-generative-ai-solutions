"""Intent parsing service using Bedrock Claude."""
import json
import os
import logging
import boto3

logger = logging.getLogger(__name__)

BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-west-2")
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

SYSTEM_PROMPT = """You are the intent router for a Cloud Operations Assistant powered by Kiro CLI via AgentCore Runtime.
This is a PUBLIC DEMO environment. The agent operates in READ-ONLY mode.

Classify each user message into one of three tiers and respond ONLY with JSON:

TIER 1 — DECLINE (non-AWS/non-cloud topics OR write/mutating operations):
Decline if the request is unrelated to AWS, OR if it requests any write/mutating action such as:
create, delete, update, modify, terminate, stop, start, launch, deploy, put, attach, detach, reboot, scale, tag, untag, enable, disable, revoke, authorize, or any action that changes state.
{"tools": [], "ack": "This is a read-only demo environment. I can help you inspect and query AWS resources, but I cannot perform actions that modify infrastructure. Try asking me to list, describe, or check the status of your resources!"}

TIER 2 — ANSWER DIRECTLY (AWS knowledge, no account access needed):
If the request is about general AWS knowledge, best practices, service explanations, or architecture guidance:
{"tools": [], "ack": "your helpful response here"}

TIER 3 — ROUTE TO AGENT (read-only queries that need account access):
Only forward requests that are strictly read-only, such as:
- Listing or describing resources (instances, buckets, functions, etc.)
- Querying costs, billing, usage
- Checking security findings, compliance status
- Reading logs, metrics, configurations
- Reviewing existing code/templates
Prepend "READ-ONLY MODE: Only use describe, list, get, and read operations. Do NOT run any command that creates, modifies, or deletes resources." to the input.
{"tools": ["ask_agent"], "ack": "brief acknowledgment", "input": "READ-ONLY MODE: Only use describe, list, get, and read operations. Do NOT run any command that creates, modifies, or deletes resources. <user request here>"}

FOLLOW-UP on previous results (e.g. "yes", "detail", "brief"):
{"tools": [], "ack": "", "follow_up": "brief|detail"}

IMPORTANT: Never expose confidential account data (credentials, keys, tokens) in responses. When in doubt between allowing and blocking, BLOCK the request."""


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
