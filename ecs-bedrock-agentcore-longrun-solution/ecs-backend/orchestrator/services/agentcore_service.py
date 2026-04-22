"""AgentCore Runtime invocation service with async polling."""
import json
import os
import re
import asyncio
import logging
import uuid
import boto3

logger = logging.getLogger(__name__)

AGENTCORE_REGION = os.getenv("AGENTCORE_REGION", "us-west-2")
RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")

DEMO_DISCLAIMER = "\n\n---\n*Some resource identifiers and names have been partially masked for this demo.*"

# Patterns: prefix-hex/alphanum IDs where we mask 2 chars before the last char
_ID_PATTERNS = re.compile(
    r'\b('
    r'i-[0-9a-f]{8,17}'           # EC2 instance
    r'|vol-[0-9a-f]{8,17}'        # EBS volume
    r'|snap-[0-9a-f]{8,17}'       # snapshot
    r'|sg-[0-9a-f]{8,17}'         # security group
    r'|subnet-[0-9a-f]{8,17}'     # subnet
    r'|vpc-[0-9a-f]{8,17}'        # VPC
    r'|igw-[0-9a-f]{8,17}'        # internet gateway
    r'|nat-[0-9a-f]{8,17}'        # NAT gateway
    r'|eni-[0-9a-f]{8,17}'        # network interface
    r'|rtb-[0-9a-f]{8,17}'        # route table
    r'|acl-[0-9a-f]{8,17}'        # network ACL
    r'|ami-[0-9a-f]{8,17}'        # AMI
    r'|lt-[0-9a-f]{8,17}'         # launch template
    r'|[0-9]{12}'                  # account ID (12 digits)
    r')\b'
)

# Patterns that capture resource names in common AWS output contexts
_NAME_PATTERNS = re.compile(
    r'(?:'
    # "Name: my-resource" or "Name=my-resource"
    r'(?:Name|name|InstanceName|BucketName|FunctionName|ClusterName|TableName|StackName|DBInstanceIdentifier|LogGroup|GroupName|KeyName|RoleName|TopicName|QueueName)'
    r'[\s]*[:=]\s*'
    r'([A-Za-z0-9/][A-Za-z0-9._/:-]{2,})'
    r'|'
    # ARN: arn:aws:service:region:account:type/name
    r'arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9*]*:[a-z-]*/([A-Za-z0-9][A-Za-z0-9._/-]{2,})'
    r'|'
    # ARN: arn:aws:service:region:account:type:name
    r'arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9*]*:[a-z-]+:([A-Za-z0-9][A-Za-z0-9._/-]{2,})'
    r'|'
    # "named X" / "called X"
    r'(?:named|called)\s+`?([A-Za-z0-9][A-Za-z0-9._/-]{2,})`?'
    r'|'
    # **Name** bold markdown
    r'\*\*([A-Za-z0-9][A-Za-z0-9._/-]{2,})\*\*'
    r')'
)

# Words that look like resource names but are actually generic terms — skip these
_NAME_SKIP = {
    'true', 'false', 'null', 'none', 'yes', 'no', 'enabled', 'disabled',
    'active', 'inactive', 'running', 'stopped', 'terminated', 'pending',
    'available', 'error', 'healthy', 'unhealthy', 'default', 'custom',
    'public', 'private', 'internal', 'external', 'standard', 'Name',
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was',
    'not', 'but', 'all', 'can', 'has', 'have', 'will', 'been', 'each',
    'Result', 'Here', 'following', 'below', 'above', 'Summary',
}


def _mask_name(name: str) -> str:
    """Mask middle portion of a resource name, keeping first 3 and last 1 chars."""
    if len(name) <= 5:
        return name[:2] + '**' + name[-1]
    return name[:3] + '***' + name[-1]


def _mask_ids(text: str) -> tuple[str, bool]:
    """Mask resource IDs and names. Returns (masked_text, had_matches)."""
    found = False

    def _replace_id(m):
        nonlocal found
        found = True
        v = m.group(0)
        if len(v) >= 4:
            return v[:-3] + '**' + v[-1]
        return v

    def _replace_name(m):
        nonlocal found
        # find which capture group matched
        name = next((g for g in m.groups() if g), None)
        if not name or name.lower() in {s.lower() for s in _NAME_SKIP}:
            return m.group(0)
        if len(name) < 3:
            return m.group(0)
        found = True
        return m.group(0).replace(name, _mask_name(name))

    masked = _ID_PATTERNS.sub(_replace_id, text)
    masked = _NAME_PATTERNS.sub(_replace_name, masked)
    return masked, found


def _get_client():
    return boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)


def _invoke(payload: dict, session_id: str = None) -> dict:
    """Single invoke call, returns parsed response."""
    client = _get_client()
    kwargs = {
        "agentRuntimeArn": RUNTIME_ARN,
        "payload": json.dumps(payload).encode(),
        "contentType": "application/json",
        "accept": "application/json",
    }
    if session_id:
        kwargs["runtimeSessionId"] = session_id
    resp = client.invoke_agent_runtime(**kwargs)
    body = resp["response"].read().decode()
    session = resp.get("runtimeSessionId", session_id)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"response": body}
    return {**data, "_session_id": session}


async def invoke_agentcore_runtime(user_input: str) -> dict:
    """Invoke AgentCore runtime with async polling for long-running tasks."""
    if not RUNTIME_ARN:
        return {"response": "AgentCore runtime ARN not configured", "error": True}

    session_id = str(uuid.uuid4())

    # First call: submit the task
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _invoke({"input": user_input}, session_id))

    status = result.get("status", "")
    task_id = result.get("task_id", "")
    sid = result.get("_session_id", session_id)

    # If immediate response (no async task), return directly
    if status != "accepted":
        resp = result.get("response", str(result))
        resp, masked = _mask_ids(resp)
        if masked:
            resp += DEMO_DISCLAIMER
        return {"response": resp}

    # Poll for completion
    for _ in range(60):  # up to 5 minutes (60 * 5s)
        await asyncio.sleep(5)
        try:
            poll = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _invoke({"check_task": task_id}, sid))
            poll_status = poll.get("status", "")
            if poll_status == "complete":
                resp = poll.get("response", "(empty)")
                resp, masked = _mask_ids(resp)
                if masked:
                    resp += DEMO_DISCLAIMER
                return {"response": resp}
            if poll_status not in ("processing", "accepted"):
                resp = poll.get("response", str(poll))
                resp, masked = _mask_ids(resp)
                if masked:
                    resp += DEMO_DISCLAIMER
                return {"response": resp}
        except Exception as e:
            logger.warning(f"Poll error: {e}")

    return {"response": "Task timed out waiting for agent response"}
