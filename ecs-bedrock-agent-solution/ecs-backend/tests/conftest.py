# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Shared fixtures for ecs-backend unit tests.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the ecs-backend root is on sys.path so imports work like the app
ECS_BACKEND_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir
)
sys.path.insert(0, os.path.abspath(ECS_BACKEND_DIR))


# ---------------------------------------------------------------------------
# Boto3 mock helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_boto3_client():
    """Generic boto3.client mock that returns a MagicMock for any service."""
    with patch("boto3.client") as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        yield mock_client, client_instance


@pytest.fixture
def mock_ssm_client():
    """Pre-configured SSM client mock."""
    client = MagicMock()
    client.describe_parameters.return_value = {"Parameters": []}
    client.get_parameter.return_value = {
        "Parameter": {"Value": "test-value", "Type": "String"}
    }
    client.put_parameter.return_value = {"Version": 1}
    return client


@pytest.fixture
def mock_sts_client():
    """Pre-configured STS client mock."""
    client = MagicMock()
    client.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/TestRole/session",
        "UserId": "AROA1234567890:session",
    }
    return client


@pytest.fixture
def mock_bedrock_runtime_client():
    """Pre-configured Bedrock Runtime client mock."""
    import io, json as _json

    client = MagicMock()

    def _make_response(text: str):
        body = io.BytesIO(
            _json.dumps(
                {
                    "content": [{"type": "text", "text": text}],
                    "stop_reason": "end_turn",
                }
            ).encode()
        )
        body.read = body.read  # already present
        return {"body": body}

    client.invoke_model.return_value = _make_response("mock LLM response")
    return client


@pytest.fixture
def mock_bedrock_agent_runtime_client():
    """Pre-configured Bedrock Agent Runtime client mock."""
    client = MagicMock()
    client.invoke_agent.return_value = {
        "completion": [
            {"chunk": {"bytes": b"Hello from agent"}},
        ],
        "sessionId": "test-session-123",
    }
    return client


@pytest.fixture
def sample_chat_session():
    """Return a minimal ChatSession for testing."""
    from models.chat_models import ChatSession

    return ChatSession(
        session_id="test-session-1",
        created_at=datetime(2026, 1, 1),
        messages=[],
        context={},
    )


@pytest.fixture
def sample_chat_session_initialized(sample_chat_session):
    """Return a ChatSession that looks already initialised by the orchestrator."""
    sample_chat_session.context.update(
        {
            "orchestrator_initialized": True,
            "bedrock_available": True,
            "system_prompt": "You are a test assistant.",
            "available_tools": [],
        }
    )
    return sample_chat_session


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure test isolation for env vars."""
    for key in [
        "ENHANCED_SECURITY_AGENT_ID",
        "ENHANCED_SECURITY_AGENT_ALIAS_ID",
        "AWS_DEFAULT_REGION",
        "USER_POOL_ID",
        "WEB_APP_CLIENT_ID",
        "USE_ENHANCED_AGENT",
    ]:
        monkeypatch.delenv(key, raising=False)
