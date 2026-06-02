"""AWS API Agent using Strands with direct boto3 tools (no MCP subprocess needed).

This avoids the known IAM credential passthrough issue with MCP subprocesses
by using strands_tools which call boto3 directly in-process.

Supports kiro-style steering files (.md) for guiding WA review flows.
"""
import os
import subprocess
import json
import logging
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import think
from steering import load_steering_files

logger = logging.getLogger(__name__)
DEFAULT_MODEL_ID = "anthropic.claude-opus-4-6-v1"
MODEL_ID_SSM_PARAM = os.getenv("MODEL_ID_SSM_PARAM", "")


def get_model_id():
    """Get model ID: SSM param > MODEL_ID env > default."""
    # Try SSM parameter first
    if MODEL_ID_SSM_PARAM:
        try:
            ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-west-2"))
            resp = ssm.get_parameter(Name=MODEL_ID_SSM_PARAM, WithDecryption=False)
            value = resp["Parameter"]["Value"]
            if value and value != "PLACEHOLDER":
                logger.info(f"Model ID from SSM ({MODEL_ID_SSM_PARAM}): {value}")
                return value
        except Exception as e:
            logger.warning(f"Failed to read model from SSM: {e}")

    # Fall back to env var or default
    model = os.getenv("MODEL_ID", DEFAULT_MODEL_ID)
    logger.info(f"Using model: {model}")
    return model


@tool
def call_aws(command: str) -> str:
    """Execute an AWS CLI command and return the output.

    Args:
        command: The full AWS CLI command starting with 'aws'. E.g. 'aws s3 ls'
    """
    if not command.strip().startswith("aws"):
        return "Error: Command must start with 'aws'"

    demo_read_only = os.getenv("DEMO_READ_ONLY", "false").lower() == "true"
    if demo_read_only:
        parts = command.split()
        write_verbs = ["create", "delete", "put", "update", "remove", "terminate", "start", "stop", "modify"]
        for verb in write_verbs:
            if verb in parts:
                return f"Error: Write operation '{verb}' is not allowed in read-only demo mode."

    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy(),
        )
        if result.returncode == 0:
            return result.stdout[:10000] if result.stdout else "(no output)"
        else:
            return f"Error (exit {result.returncode}): {result.stderr[:2000]}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def call_boto3(service: str, operation: str, params: str = "{}") -> str:
    """Execute an AWS API call using boto3 directly.

    Args:
        service: AWS service name (e.g. 's3', 'ec2', 'iam')
        operation: API operation (e.g. 'list_buckets', 'describe_instances')
        params: JSON string of parameters (optional)
    """
    try:
        client = boto3.client(service, region_name=os.getenv("AWS_REGION", "us-west-2"))
        kwargs = json.loads(params) if params and params != "{}" else {}
        method = getattr(client, operation)
        response = method(**kwargs)
        response.pop("ResponseMetadata", None)
        output = json.dumps(response, default=str, indent=2)
        return output[:10000]
    except Exception as e:
        return f"Error: {str(e)}"


def create_supervisor_agent():
    """Create the top-level supervisor agent."""
    model_id = get_model_id()
    bedrock_model = BedrockModel(model_id=model_id)

    # Load steering files (WA review flow, pillar guidance, etc.)
    steering = load_steering_files()

    base_prompt = """You are an AWS Operations Assistant. You help users query and inspect AWS resources.

Available tools:
- call_aws: Execute AWS CLI commands (e.g. 'aws s3 ls', 'aws ec2 describe-instances')
- call_boto3: Execute boto3 API calls directly (service, operation, params)
- think: Plan complex operations before executing

Always use call_boto3 for simple operations. Use call_aws for complex CLI commands with specific flags.
Be concise in responses. Show the key information users need."""

    if steering:
        system_prompt = f"{base_prompt}\n\n{steering}"
    else:
        system_prompt = base_prompt

    return Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=[call_aws, call_boto3, think],
    )
