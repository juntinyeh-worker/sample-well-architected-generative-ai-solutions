"""
SupportInteractionsClient

A boto3-style client for the AWS Support Interactions API and Support Cases API.

Confirmed endpoints (captured from browser DevTools):

1. Support Interactions API (AI-enhanced troubleshooting):
   Base URL : https://assistant.support.{region}.amazonaws.com
   Protocol : REST — HTTP method + path identifies the operation
   SigV4    : service name = "support"

   Operations:
     POST   /interactions                       → start_interaction
     GET    /interactions                       → list_interactions
     GET    /interactions/{id}/entries          → list_interaction_entries
     POST   /interactions/{id}                  → update_interaction
     GET    /interactions/{id}                  → get_interaction
     POST   /interactions/{id}/resolve          → resolve_interaction

2. Support Cases API (traditional support tickets):
   Base URL : https://support.{region}.amazonaws.com/
   Protocol : JSON-RPC 1.1 — X-Amz-Target header identifies the operation
   SigV4    : service name = "support"

   Operations:
     AWSSupport_internal_v1.CreateCase          → create_case
     AWSSupport_internal_v1.ResolveCase         → resolve_case
     AWSSupport_internal_v1.DescribeCases       → describe_cases
     AWSSupport_internal_v1.DescribeServices    → describe_services
     AWSSupport_internal_v1.DescribeSeverityLevels → describe_severity_levels
"""

import uuid
from typing import Any

import boto3
from botocore.exceptions import NoCredentialsError, ProfileNotFound

from .auth import resolve_credentials, signed_request
from .exceptions import from_response
from .text_sanitizer import sanitize_message

_DEFAULT_REGION = "us-east-1"

# Interactions API (AI-enhanced troubleshooting)
_INTERACTIONS_BASE_URL = "https://assistant.support.{region}.amazonaws.com"

# Support Cases API (traditional support tickets)
_SUPPORT_BASE_URL = "https://support.{region}.amazonaws.com/"


def _interactions_base(region: str) -> str:
    return _INTERACTIONS_BASE_URL.format(region=region)


def _support_base(region: str) -> str:
    return _SUPPORT_BASE_URL.format(region=region)


def _response_metadata(status: int, headers: dict, request_id: str) -> dict:
    return {
        "RequestId": request_id,
        "HTTPStatusCode": status,
        "HTTPHeaders": {k.lower(): v for k, v in headers.items()},
        "RetryAttempts": 0,
    }


class _Exceptions:
    from .exceptions import (
        ClientError,
        AccessDeniedException,
        SubscriptionRequiredException,
        InteractionNotFoundException,
        ValidationException,
        ThrottlingException,
        InternalServerError,
    )


class SupportInteractionsClient:
    """
    Client for the AWS Support Interactions API.

    Usage::

        from plx_support_assistant_client import SupportInteractionsClient

        client = SupportInteractionsClient()
        client = SupportInteractionsClient(region_name="us-east-1", profile_name="prod")

    When the official SDK ships, swap via get_client() — zero caller changes.
    """

    def __init__(
        self,
        region_name: str | None = None,
        profile_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        endpoint_url: str | None = None,
    ):
        session_kwargs: dict[str, Any] = {}
        if profile_name:
            session_kwargs["profile_name"] = profile_name
        if aws_access_key_id:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        self._session = boto3.Session(**session_kwargs)
        self._region = region_name or self._session.region_name or _DEFAULT_REGION
        self._interactions_url = endpoint_url or _interactions_base(self._region)
        self._support_url = _support_base(self._region)
        self._credentials = resolve_credentials(self._session)

        self.exceptions = _Exceptions()
        self.meta = _ClientMeta(
            endpoint_url=self._interactions_url,
            region_name=self._region,
        )

    # ── Internal dispatcher ───────────────────────────────────────────────────

    def _call(
        self,
        operation: str,
        method: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Call the Interactions API (REST style)."""
        url = self._interactions_url + path

        status, headers, resp_body = signed_request(
            method=method,
            url=url,
            region=self._region,
            credentials=self._credentials,
            body=body,
            params=params,
        )

        request_id = headers.get(
            "x-amzn-requestid",
            headers.get("x-amz-request-id", str(uuid.uuid4())),
        )

        if status >= 400:
            code = resp_body.get("code", resp_body.get("__type", f"HTTP{status}"))
            if "#" in str(code):
                code = code.split("#")[-1]
            message = resp_body.get("message", resp_body.get("Message", str(resp_body)))
            error_response = {
                "Error": {"Code": code, "Message": message},
                "ResponseMetadata": _response_metadata(status, headers, request_id),
            }
            raise from_response(error_response, operation)

        resp_body["ResponseMetadata"] = _response_metadata(status, headers, request_id)
        return resp_body

    def _call_support(
        self,
        operation: str,
        target: str,
        body: dict | None = None,
    ) -> dict:
        """
        Call the Support Cases API (JSON-RPC 1.1 style).
        
        :param operation: Operation name for error handling
        :param target: X-Amz-Target value (e.g., "AWSSupport_internal_v1.CreateCase")
        :param body: Request body as dict
        """
        status, headers, resp_body = signed_request(
            method="POST",
            url=self._support_url,
            region=self._region,
            credentials=self._credentials,
            body=body or {},
            headers={"X-Amz-Target": target},
            content_type="application/x-amz-json-1.1",
        )

        request_id = headers.get(
            "x-amzn-requestid",
            headers.get("x-amz-request-id", str(uuid.uuid4())),
        )

        if status >= 400:
            code = resp_body.get("__type", resp_body.get("code", f"HTTP{status}"))
            if "#" in str(code):
                code = code.split("#")[-1]
            message = resp_body.get("message", resp_body.get("Message", str(resp_body)))
            error_response = {
                "Error": {"Code": code, "Message": message},
                "ResponseMetadata": _response_metadata(status, headers, request_id),
            }
            raise from_response(error_response, operation)

        resp_body["ResponseMetadata"] = _response_metadata(status, headers, request_id)
        return resp_body

    # ── can_paginate ──────────────────────────────────────────────────────────

    def can_paginate(self, operation_name: str) -> bool:
        return operation_name in {"list_interactions", "list_interaction_entries"}

    # ── 1. start_interaction ──────────────────────────────────────────────────

    def start_interaction(self, message: str, domain: str | None = None) -> dict:
        """
        Start a new support interaction (AI-enhanced troubleshooting session).

        POST /interactions

        :param message: Natural-language description of the issue.
        :param domain: Optional domain context (e.g., "plx" for Partner-Led Experience).
            When provided, scopes the investigation to the specified partner context.

        :returns: Dict with keys:
            - interactionId (str)
            - status (str)
            - subject (str)
            - ResponseMetadata (dict)
        """
        message = sanitize_message(message)
        body: dict = {"message": message}
        if domain:
            body["domain"] = domain
        return self._call(
            "StartInteraction", "POST", "/interactions",
            body=body,
        )

    # ── 2. list_interactions ──────────────────────────────────────────────────

    def list_interactions(
        self,
        *,
        max_results: int | None = None,
        next_token: str | None = None,
        sort_by: str = "updatedAt",
        sort_order: str = "Descending",
        status_equals: list[str] | None = None,
    ) -> dict:
        """
        List interactions for the account.

        GET /interactions

        :param max_results: Maximum number of results to return.
        :param next_token: Pagination token from a previous response.
        :param sort_by: Field to sort by. Default: "updatedAt".
        :param sort_order: "Ascending" or "Descending". Default: "Descending".
        :param status_equals: Filter by status values e.g.
            ["IN_PROGRESS", "AWAITING_INPUT", "COMPLETED"]

        :returns: Dict with keys:
            - interactions (list of dicts)
            - nextToken (str, only if more results exist)
            - ResponseMetadata (dict)
        """
        params: dict[str, Any] = {
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        if max_results is not None:
            params["maxResults"] = max_results
        if next_token:
            params["nextToken"] = next_token
        if status_equals:
            params["statusEquals"] = status_equals

        return self._call("ListInteractions", "GET", "/interactions", params=params)

    # ── 3. list_interaction_entries ───────────────────────────────────────────

    def list_interaction_entries(
        self,
        interaction_id: str,
        *,
        max_results: int | None = None,
        next_token: str | None = None,
    ) -> dict:
        """
        Get the entries (messages, AI responses) within an interaction.

        GET /interactions/{interactionId}/entries

        :param interaction_id: The interaction ID.
        :param max_results: Maximum number of entries to return.
        :param next_token: Pagination token from a previous response.

        :returns: Dict with keys:
            - interactionId (str)
            - status (str)
            - entries (list of dicts)
            - nextToken (str, only if more results exist)
            - ResponseMetadata (dict)
        """
        params: dict[str, Any] = {}
        if max_results is not None:
            params["maxResults"] = max_results
        if next_token:
            params["nextToken"] = next_token

        return self._call(
            "ListInteractionEntries", "GET",
            f"/interactions/{interaction_id}/entries",
            params=params or None,
        )

    # ── 4. update_interaction ─────────────────────────────────────────────────

    def update_interaction(self, interaction_id: str, message: str) -> dict:
        """
        Add a follow-up message to an existing interaction.

        POST /interactions/{interactionId}

        This is used for:
        1. Responding to AWAITING_INPUT prompts (e.g., providing requested field values)
        2. Adding additional details about your issue (the "Add more details" button)
        3. Sending any free-form follow-up message to continue the conversation

        :param interaction_id: The interaction ID.
        :param message: The follow-up message text. Can be:
            - Field responses: "AWS region: Sydney, EC2 Instance IDs: i-xxx"
            - Free-form text: "Can you help me with this step?"
            - Multi-line responses for multiple fields

        :returns: Dict with keys:
            - messageId (str) - ID of the created message
            - ResponseMetadata (dict)

        Example usage::

            # Respond to AWAITING_INPUT with requested fields
            client.update_interaction(
                interaction_id,
                "AWS region: ap-southeast-2, EC2 Instance IDs: i-0abcdef0123456789"
            )

            # Add more details about the issue
            client.update_interaction(
                interaction_id,
                "I need someone to help me step by step"
            )
        """
        message = sanitize_message(message)
        return self._call(
            "UpdateInteraction", "POST",
            f"/interactions/{interaction_id}",
            body={"message": message},
        )

    # ── 5. get_interaction ────────────────────────────────────────────────────

    def get_interaction(self, interaction_id: str) -> dict:
        """
        Retrieve details about a specific interaction.

        GET /interactions/{interactionId}

        :param interaction_id: The interaction ID.

        :returns: Dict with keys:
            - interactionId (str)
            - status (str) - One of: IN_PROGRESS, AWAITING_INPUT, COMPLETED
            - subject (str)
            - createdAt (str)
            - updatedAt (str)
            - result (dict, optional) - Contains AI response details:
                - messageId (str)
                - details (list) - List of response components:
                    - assistantName (str) - e.g., "ROUTABLE", "GENERAL_GUIDANCE"
                    - category (str) - e.g., "FOLLOW_UP_RESPONSE", "FINAL_RESPONSE"
                    - content (str) - The response content or JSON array of field names
                    - metadata (list) - Recommendations with URLs
            - statusUpdates (list, optional) - Troubleshooting steps with checkboxes:
                - name (str) - Description of the troubleshooting step
                - executionStatus (str) - "IN_PROGRESS" or "COMPLETED"
            - ResponseMetadata (dict)
        
        When status is "AWAITING_INPUT", check result.details for entries with
        category="FOLLOW_UP_RESPONSE" - the content field contains a JSON array
        of field names the user needs to provide (e.g., ["AWS region", "Stack name"]).
        """
        return self._call(
            "GetInteraction", "GET",
            f"/interactions/{interaction_id}",
        )

    # ── 6. resolve_interaction ────────────────────────────────────────────────

    def resolve_interaction(self, interaction_id: str, resolution: str = "resolved") -> dict:
        """
        Mark an interaction as resolved (status → CLOSED).

        POST /interactions/{interactionId}/resolve

        :param interaction_id: The interaction ID to resolve.
        :param resolution: Resolution reason (default: "resolved").

        :returns: Dict with keys:
            - status (str) — "CLOSED"
            - ResponseMetadata (dict)
        """
        return self._call(
            "ResolveInteraction", "POST",
            f"/interactions/{interaction_id}/resolve",
            body={"resolution": resolution},
        )

    # ══════════════════════════════════════════════════════════════════════════
    # SUPPORT CASES API (Traditional Support Tickets)
    # ══════════════════════════════════════════════════════════════════════════

    # ── 7. create_case ────────────────────────────────────────────────────────

    def create_case(
        self,
        subject: str,
        communication_body: str,
        service_code: str,
        category_code: str,
        severity_code: str = "low",
        language: str = "en",
        issue_type: str = "technical",
        cc_email_addresses: list[str] | None = None,
        attachment_set_id: str | None = None,
    ) -> dict:
        """
        Create a new support case (traditional support ticket).

        This uses the AWS Support API (not the Interactions API).

        :param subject: Brief description of the issue (case title).
        :param communication_body: Detailed description of the issue.
        :param service_code: AWS service code (e.g., "amazon-elastic-compute-cloud-linux").
            Use describe_services() to get available service codes.
        :param category_code: Category within the service (e.g., "instance-issue").
            Use describe_services() to get available categories.
        :param severity_code: Severity level. One of: "low", "normal", "high", "urgent".
            Use describe_severity_levels() to get available levels.
        :param language: Language code (default: "en").
        :param issue_type: Type of issue. One of: "technical", "customer-service".
        :param cc_email_addresses: Optional list of email addresses to CC.
        :param attachment_set_id: Optional attachment set ID from add_attachments_to_set.

        :returns: Dict with keys:
            - caseId (str) - The created case ID (e.g., "case-123456789012-muen-2026-xxx")
            - ResponseMetadata (dict)

        Example usage::

            response = client.create_case(
                subject="Cannot SSH to EC2 instance",
                communication_body="I cannot login to my EC2 instance i-xxx...",
                service_code="amazon-elastic-compute-cloud-linux",
                category_code="instance-issue",
                severity_code="low",
            )
            case_id = response["caseId"]
        """
        body: dict[str, Any] = {
            "subject": subject,
            "communicationBody": communication_body,
            "serviceCode": service_code,
            "categoryCode": category_code,
            "severityCode": severity_code,
            "language": language,
            "issueType": issue_type,
        }
        if cc_email_addresses:
            body["ccEmailAddresses"] = cc_email_addresses
        if attachment_set_id:
            body["attachmentSetId"] = attachment_set_id

        return self._call_support(
            "CreateCase",
            "AWSSupport_internal_v1.CreateCase",
            body=body,
        )

    # ── 8. resolve_case ───────────────────────────────────────────────────────

    def resolve_case(self, case_id: str) -> dict:
        """
        Resolve (close) a support case.

        :param case_id: The case ID to resolve (e.g., "case-123456789012-muen-2026-xxx").

        :returns: Dict with keys:
            - initialCaseStatus (str) - Status before resolution (e.g., "unassigned")
            - finalCaseStatus (str) - Status after resolution (e.g., "resolved")
            - ResponseMetadata (dict)

        Example usage::

            response = client.resolve_case("case-123456789012-muen-2026-1d66c5dc3e3d1f41")
            print(response["finalCaseStatus"])  # "resolved"
        """
        return self._call_support(
            "ResolveCase",
            "AWSSupport_internal_v1.ResolveCase",
            body={"caseId": case_id},
        )

    # ── 9. describe_cases ─────────────────────────────────────────────────────

    def describe_cases(
        self,
        case_id_list: list[str] | None = None,
        include_resolved_cases: bool = False,
        max_results: int | None = None,
        next_token: str | None = None,
        language: str = "en",
    ) -> dict:
        """
        Get details about support cases.

        :param case_id_list: Optional list of case IDs to retrieve.
        :param include_resolved_cases: Include resolved cases (default: False).
        :param max_results: Maximum number of results to return.
        :param next_token: Pagination token from a previous response.
        :param language: Language code (default: "en").

        :returns: Dict with keys:
            - cases (list) - List of case details
            - nextToken (str, optional) - Pagination token
            - ResponseMetadata (dict)
        """
        body: dict[str, Any] = {
            "includeResolvedCases": include_resolved_cases,
            "language": language,
        }
        if case_id_list:
            body["caseIdList"] = case_id_list
        if max_results is not None:
            body["maxResults"] = max_results
        if next_token:
            body["nextToken"] = next_token

        return self._call_support(
            "DescribeCases",
            "AWSSupport_internal_v1.DescribeCases",
            body=body,
        )

    # ── 10. describe_services ─────────────────────────────────────────────────

    def describe_services(
        self,
        service_code_list: list[str] | None = None,
        language: str = "en",
    ) -> dict:
        """
        Get available AWS services and their categories for support cases.

        :param service_code_list: Optional list of service codes to filter.
        :param language: Language code (default: "en").

        :returns: Dict with keys:
            - services (list) - List of services with their categories
            - ResponseMetadata (dict)

        Each service contains:
            - code (str) - Service code (e.g., "amazon-elastic-compute-cloud-linux")
            - name (str) - Service name (e.g., "Elastic Compute Cloud (Linux)")
            - categories (list) - List of category dicts with "code" and "name"
        """
        body: dict[str, Any] = {"language": language}
        if service_code_list:
            body["serviceCodeList"] = service_code_list

        return self._call_support(
            "DescribeServices",
            "AWSSupport_internal_v1.DescribeServices",
            body=body,
        )

    # ── 11. describe_severity_levels ──────────────────────────────────────────

    def describe_severity_levels(self, language: str = "en") -> dict:
        """
        Get available severity levels for support cases.

        :param language: Language code (default: "en").

        :returns: Dict with keys:
            - severityLevels (list) - List of severity level dicts
            - ResponseMetadata (dict)

        Each severity level contains:
            - code (str) - Severity code (e.g., "low", "normal", "high", "urgent")
            - name (str) - Display name
            - maxResponseTimeMinutes (int) - Maximum response time in minutes
        """
        return self._call_support(
            "DescribeSeverityLevels",
            "AWSSupport_internal_v1.DescribeSeverityLevels",
            body={"language": language, "includeAllSeverityLevels": False},
        )


class _ClientMeta:
    def __init__(self, endpoint_url: str, region_name: str):
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.service_model = _ServiceModel()


class _ServiceModel:
    service_name = "support"
    api_version = "2013-04-15"
