"""AWS API Agent using Strands with Support Interactions API integration.

Extends the base agent with:
- call_aws / call_boto3 / think (existing — resource inspection)
- Support Interactions API tools (NEW — AI-enhanced troubleshooting)

Supports kiro-style steering files (.md) for guiding investigation flows.
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
from support_tools import (
    start_support_interaction,
    get_interaction_status,
    update_support_interaction,
    resolve_support_interaction,
    list_support_interactions,
    list_interaction_entries,
    create_support_case,
    describe_support_cases,
)

logger = logging.getLogger(__name__)
DEFAULT_MODEL_ID = "us.anthropic.claude-opus-4-6-v1"
MODEL_ID_SSM_PARAM = os.getenv("MODEL_ID_SSM_PARAM", "")


def get_model_id():
    """Get model ID: SSM param > MODEL_ID env > default."""
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

    demo_read_only = os.getenv("DEMO_READ_ONLY", "true").lower() == "true"
    if demo_read_only:
        parts = command.split()
        write_verbs = ["create", "delete", "put", "update", "remove", "terminate", "start", "stop", "modify"]
        for verb in write_verbs:
            if verb in parts:
                return f"Error: Write operation '{verb}' is not allowed in read-only mode."

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
    """Create the top-level supervisor agent with all tools."""
    model_id = get_model_id()
    bedrock_model = BedrockModel(model_id=model_id)

    # Load steering files (investigation flow, role definition, etc.)
    steering = load_steering_files()

    base_prompt = f"""You are an AWS Support Investigation Agent. You diagnose AWS issues by inspecting resources and leveraging AI-enhanced troubleshooting.

Current date: {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

Available tools:

Resource Inspection:
- call_aws: Execute AWS CLI commands (read-only: describe, list, get)
- call_boto3: Execute boto3 API calls directly (service, operation, params)
- think: Plan complex operations before executing

Support Interactions API (AI-Enhanced Troubleshooting):
- start_support_interaction: Start an AI investigation session with detailed context
- get_interaction_status: Check investigation progress and get findings
- update_support_interaction: Answer follow-up questions from the AI system
- resolve_support_interaction: Close a completed interaction
- list_support_interactions: List recent interactions
- list_interaction_entries: Get full conversation history of an interaction

Support Cases (Traditional Tickets — last resort):
- create_support_case: Create a support ticket for human engineer review
- describe_support_cases: Check status of existing support cases

Workflow:
1. ALWAYS use call_boto3 to inspect resources BEFORE starting a support interaction
2. Include gathered evidence in the start_support_interaction message
3. If the support system asks follow-up questions, answer from your inspection data
4. Report findings clearly with root cause and recommendations"""

    if steering:
        system_prompt = f"{base_prompt}\n\n{steering}"
    else:
        system_prompt = base_prompt

    return Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=[
            # Resource inspection
            call_aws, call_boto3, think,
            # Support Interactions API
            start_support_interaction, get_interaction_status,
            update_support_interaction, resolve_support_interaction,
            list_support_interactions, list_interaction_entries,
            # Support Cases
            create_support_case, describe_support_cases,
        ],
    )
