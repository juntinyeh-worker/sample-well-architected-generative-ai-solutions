"""AgentCore Memory integration — gated by AGENTCORE_MEMORY_ID env var."""
import os
import logging
import boto3

logger = logging.getLogger(__name__)

AGENTCORE_MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID", "")
AGENTCORE_MEMORY_REGION = os.getenv("AGENTCORE_MEMORY_REGION", os.getenv("AGENTCORE_REGION", "us-west-2"))

_client = None


def _get_client():
    global _client
    if not _client:
        _client = boto3.client("bedrock-agentcore", region_name=AGENTCORE_MEMORY_REGION)
    return _client


def is_enabled() -> bool:
    return bool(AGENTCORE_MEMORY_ID)


def write_turns(session_id: str, actor_id: str, user_text: str, assistant_text: str):
    """Write a user/assistant turn pair to AgentCore Memory."""
    if not is_enabled():
        return
    try:
        client = _get_client()
        client.create_memory_event(
            memoryId=AGENTCORE_MEMORY_ID,
            actorId=actor_id,
            sessionId=session_id,
            messages=[
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": assistant_text},
            ],
        )
    except Exception as e:
        logger.warning(f"Memory write failed: {e}")


def retrieve_context(session_id: str, actor_id: str, query: str, top_k: int = 3) -> str:
    """Retrieve relevant long-term memories as context string."""
    if not is_enabled():
        return ""
    try:
        client = _get_client()
        resp = client.search_memory(
            memoryId=AGENTCORE_MEMORY_ID,
            actorId=actor_id,
            sessionId=session_id,
            query=query,
            topK=top_k,
            namespacePath="/",
        )
        records = resp.get("records", [])
        if not records:
            return ""
        context_parts = [r.get("content", "") for r in records if r.get("content")]
        if not context_parts:
            return ""
        return "Relevant context from previous interactions:\n" + "\n---\n".join(context_parts) + "\n\n"
    except Exception as e:
        logger.warning(f"Memory retrieve failed: {e}")
        return ""
