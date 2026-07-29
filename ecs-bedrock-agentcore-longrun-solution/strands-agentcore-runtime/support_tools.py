"""Support Investigation Tools for Strands AgentCore Runtime.

Provides tools to interact with the AWS Support Interactions API (AI-enhanced
troubleshooting) and AWS Support Cases API (traditional tickets).

Uses plx_support_assistant_client — the same SigV4 shim library used by sup-beta.
Credentials come from the ECS task role (single-account) or can be extended
with explicit credentials for multi-account (CODA) scenarios.
"""

import json
import os
import logging
from typing import Optional

from strands import tool

logger = logging.getLogger(__name__)

# Lazy-initialized client (uses ECS task role credentials via boto3 chain)
_client = None
SUPPORT_API_REGION = os.environ.get("SUPPORT_API_REGION", "us-east-1")
PLX_DOMAIN = os.environ.get("PLX_DOMAIN_ENABLED", "false").lower() == "true"


def _get_client():
    """Get or create the SupportInteractionsClient singleton."""
    global _client
    if _client is None:
        from plx_support_assistant_client import get_client
        _client = get_client(region_name=SUPPORT_API_REGION)
    return _client


def _format_response(response: dict) -> str:
    """Format API response as indented JSON string."""
    response.pop("ResponseMetadata", None)
    return json.dumps(response, default=str, indent=2)


# ═══════════════════════════════════════════════════════════════
# Support Interactions API (AI-Enhanced Troubleshooting)
# ═══════════════════════════════════════════════════════════════


@tool
def start_support_interaction(message: str) -> str:
    """Start a new AI-enhanced support interaction (troubleshooting session).

    Use this AFTER gathering evidence from AWS resources. Include all relevant
    context in the message to minimize back-and-forth with the support system.

    Args:
        message: Detailed description of the issue. Include:
            - Affected AWS service and resource identifiers
            - Symptom description with timestamps
            - Error messages or codes
            - Evidence gathered from resource inspection
            Maximum 4096 characters.

    Returns:
        JSON with interactionId, status, and subject.
        Status will be IN_PROGRESS — poll with get_interaction_status().
    """
    try:
        client = _get_client()
        kwargs = {"message": message}
        if PLX_DOMAIN:
            kwargs["domain"] = "plx"
        response = client.start_interaction(**kwargs)
        logger.info(f"Started interaction: {response.get('interactionId')}")
        return _format_response(response)
    except Exception as e:
        logger.error(f"start_support_interaction failed: {e}")
        return f"Error starting interaction: {str(e)}"


@tool
def get_interaction_status(interaction_id: str) -> str:
    """Get current status, AI findings, and details of a support interaction.

    Call this to check if the investigation has completed. Wait at least 10
    seconds between calls to avoid throttling.

    Status meanings:
    - IN_PROGRESS: AI is still investigating
    - AWAITING_INPUT: The system needs more information — check result.details
      for the specific fields requested, then call update_support_interaction()
    - COMPLETED: Investigation finished — result contains findings
    - CLOSED: Interaction was resolved
    - FAILED: Investigation could not complete

    Args:
        interaction_id: The interaction ID from start_support_interaction.

    Returns:
        JSON with status, subject, result (containing details and metadata),
        and statusUpdates showing the investigation progress.
    """
    try:
        client = _get_client()
        response = client.get_interaction(interaction_id)
        return _format_response(response)
    except Exception as e:
        logger.error(f"get_interaction_status failed: {e}")
        return f"Error getting interaction: {str(e)}"


@tool
def update_support_interaction(interaction_id: str, message: str) -> str:
    """Send a follow-up message to an existing support interaction.

    Use this to:
    1. Respond to AWAITING_INPUT prompts with requested information
    2. Provide additional context discovered during investigation
    3. Answer follow-up questions from the AI system

    Args:
        interaction_id: The interaction ID to update.
        message: Follow-up text. For field responses, be specific:
            "AWS Region: us-west-2, Instance ID: i-0abc123def"
            Maximum 4096 characters.

    Returns:
        JSON with messageId confirming the update was received.
    """
    try:
        client = _get_client()
        response = client.update_interaction(interaction_id, message)
        logger.info(f"Updated interaction {interaction_id}")
        return _format_response(response)
    except Exception as e:
        logger.error(f"update_support_interaction failed: {e}")
        return f"Error updating interaction: {str(e)}"


@tool
def resolve_support_interaction(interaction_id: str, resolution: str = "resolved") -> str:
    """Mark a support interaction as resolved and close it.

    Call this after the investigation is complete and findings have been
    delivered to the user.

    Args:
        interaction_id: The interaction ID to resolve.
        resolution: Brief resolution note (default: "resolved").

    Returns:
        JSON confirmation with status CLOSED.
    """
    try:
        client = _get_client()
        response = client.resolve_interaction(interaction_id, resolution)
        logger.info(f"Resolved interaction {interaction_id}")
        return _format_response(response)
    except Exception as e:
        logger.error(f"resolve_support_interaction failed: {e}")
        return f"Error resolving interaction: {str(e)}"


@tool
def list_support_interactions(max_results: int = 10, status_filter: str = "") -> str:
    """List recent support interactions for the account.

    Args:
        max_results: Maximum number to return (1-50, default: 10).
        status_filter: Optional comma-separated status filter.
            Valid: IN_PROGRESS, AWAITING_INPUT, COMPLETED, CLOSED, FAILED
            Empty string returns all.

    Returns:
        JSON with interactions list (id, status, subject, timestamps).
    """
    try:
        client = _get_client()
        kwargs = {"max_results": min(max_results, 50)}
        if status_filter:
            kwargs["status_equals"] = [s.strip() for s in status_filter.split(",")]
        response = client.list_interactions(**kwargs)
        return _format_response(response)
    except Exception as e:
        logger.error(f"list_support_interactions failed: {e}")
        return f"Error listing interactions: {str(e)}"


@tool
def list_interaction_entries(interaction_id: str, max_results: int = 50) -> str:
    """Get the full conversation history within a support interaction.

    Returns all messages exchanged — user inputs, AI responses, follow-up
    questions, and final findings.

    Args:
        interaction_id: The interaction ID.
        max_results: Maximum entries to return (default: 50).

    Returns:
        JSON with entries list showing the full interaction timeline.
    """
    try:
        client = _get_client()
        response = client.list_interaction_entries(interaction_id, max_results=max_results)
        return _format_response(response)
    except Exception as e:
        logger.error(f"list_interaction_entries failed: {e}")
        return f"Error listing entries: {str(e)}"


# ═══════════════════════════════════════════════════════════════
# Support Cases API (Traditional Tickets)
# ═══════════════════════════════════════════════════════════════


@tool
def create_support_case(
    subject: str,
    description: str,
    service_code: str = "general-info",
    category_code: str = "other",
    severity_code: str = "low",
) -> str:
    """Create a traditional AWS support case (ticket) for human engineer review.

    Use as LAST RESORT when AI-enhanced troubleshooting cannot resolve the issue.
    Requires an active AWS Support plan (Business or Enterprise).

    Args:
        subject: Brief issue title (max 200 chars).
        description: Detailed description including:
            - Affected resources and identifiers
            - Error messages and timestamps
            - Steps already attempted
            - AI investigation findings (if any)
        service_code: AWS service code (default: "general-info").
        category_code: Category within the service (default: "other").
        severity_code: "low", "normal", "high", "urgent", or "critical".
            Higher severities require Business/Enterprise support plan.

    Returns:
        JSON with caseId of the created support case.
    """
    try:
        client = _get_client()
        response = client.create_case(
            subject=subject,
            communication_body=description,
            service_code=service_code,
            category_code=category_code,
            severity_code=severity_code,
        )
        logger.info(f"Created support case: {response.get('caseId')}")
        return _format_response(response)
    except Exception as e:
        logger.error(f"create_support_case failed: {e}")
        return f"Error creating case: {str(e)}"


@tool
def describe_support_cases(case_id: str = "", include_resolved: bool = False) -> str:
    """Get details about existing support cases.

    Args:
        case_id: Specific case ID to look up. Leave empty to list recent cases.
        include_resolved: Include resolved/closed cases (default: False).

    Returns:
        JSON with case details including status, subject, and communications.
    """
    try:
        client = _get_client()
        kwargs = {"include_resolved_cases": include_resolved}
        if case_id:
            kwargs["case_id_list"] = [case_id]
        response = client.describe_cases(**kwargs)
        return _format_response(response)
    except Exception as e:
        logger.error(f"describe_support_cases failed: {e}")
        return f"Error describing cases: {str(e)}"
