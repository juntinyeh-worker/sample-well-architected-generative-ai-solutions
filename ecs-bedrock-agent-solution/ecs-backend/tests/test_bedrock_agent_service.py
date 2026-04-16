# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/bedrock_agent_service.py
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.chat_models import ChatSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(agent_id="agent-1", alias_id="alias-1"):
    """Create a BedrockAgentService with mocked config and clients."""
    with patch("services.bedrock_agent_service.get_config") as mock_cfg:
        def _cfg(key, default=None):
            mapping = {
                "AWS_DEFAULT_REGION": "us-east-1",
                "ENHANCED_SECURITY_AGENT_ID": agent_id,
                "ENHANCED_SECURITY_AGENT_ALIAS_ID": alias_id,
            }
            return mapping.get(key, default)
        mock_cfg.side_effect = _cfg
        from services.bedrock_agent_service import BedrockAgentService
        svc = BedrockAgentService()
    return svc


def _session():
    return ChatSession(
        session_id="sess-1", created_at=datetime(2026, 1, 1), messages=[], context={}
    )


# ---------------------------------------------------------------------------
# Init / config
# ---------------------------------------------------------------------------

class TestBedrockAgentServiceInit:
    def test_configured(self):
        svc = _make_service("a1", "al1")
        assert svc.agent_id == "a1"
        assert svc.agent_alias_id == "al1"

    def test_not_configured(self):
        svc = _make_service(None, None)
        assert svc.agent_id is None

    def test_get_agent_info(self):
        svc = _make_service("a1", "al1")
        info = svc.get_agent_info()
        assert info["configured"] is True
        assert info["agent_id"] == "a1"

    def test_get_agent_info_not_configured(self):
        svc = _make_service(None, None)
        info = svc.get_agent_info()
        assert info["configured"] is False


# ---------------------------------------------------------------------------
# Lazy client properties
# ---------------------------------------------------------------------------

class TestLazyClients:
    @patch("boto3.client")
    def test_bedrock_agent_runtime(self, mock_boto):
        mock_boto.return_value = MagicMock()
        svc = _make_service()
        _ = svc.bedrock_agent_runtime
        mock_boto.assert_called_with("bedrock-agent-runtime", region_name="us-east-1")

    @patch("boto3.client", side_effect=Exception("fail"))
    def test_bedrock_agent_runtime_failure(self, mock_boto):
        svc = _make_service()
        assert svc.bedrock_agent_runtime is None

    @patch("boto3.client")
    def test_bedrock_agent(self, mock_boto):
        mock_boto.return_value = MagicMock()
        svc = _make_service()
        _ = svc.bedrock_agent
        mock_boto.assert_called_with("bedrock-agent", region_name="us-east-1")

    @patch("boto3.client")
    def test_bedrock_runtime(self, mock_boto):
        mock_boto.return_value = MagicMock()
        svc = _make_service()
        _ = svc.bedrock_runtime
        mock_boto.assert_called_with("bedrock-runtime", region_name="us-east-1")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_degraded_when_not_configured(self):
        svc = _make_service(None, None)
        assert await svc.health_check() == "degraded"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_healthy_when_agent_prepared(self, mock_boto):
        mock_client = MagicMock()
        mock_client.get_agent.return_value = {
            "agent": {"agentStatus": "PREPARED"}
        }
        mock_boto.return_value = mock_client
        svc = _make_service()
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_unhealthy_when_agent_failed(self, mock_boto):
        mock_client = MagicMock()
        mock_client.get_agent.return_value = {
            "agent": {"agentStatus": "FAILED"}
        }
        mock_boto.return_value = mock_client
        svc = _make_service()
        assert await svc.health_check() == "unhealthy"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_degraded_on_exception(self, mock_boto):
        mock_client = MagicMock()
        mock_client.get_agent.side_effect = Exception("boom")
        mock_boto.return_value = mock_client
        svc = _make_service()
        assert await svc.health_check() == "degraded"


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_not_configured_returns_error_msg(self):
        svc = _make_service(None, None)
        resp = await svc.process_message("hello", _session())
        assert "not configured" in resp.response.lower()
        assert resp.model_id == "enhanced-security-agent"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_successful_response(self, mock_boto):
        mock_client = MagicMock()
        mock_client.invoke_agent.return_value = {
            "completion": [
                {"chunk": {"bytes": b"Part 1 "}},
                {"chunk": {"bytes": b"Part 2"}},
            ],
            "sessionId": "new-sess",
        }
        mock_boto.return_value = mock_client
        svc = _make_service()
        resp = await svc.process_message("test query", _session())
        assert "Part 1 Part 2" == resp.response
        assert resp.session_id == "new-sess"

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_client_error_handled(self, mock_boto):
        from botocore.exceptions import ClientError
        mock_client = MagicMock()
        mock_client.invoke_agent.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
            "InvokeAgent",
        )
        mock_boto.return_value = mock_client
        svc = _make_service()
        resp = await svc.process_message("test", _session())
        assert "error" in resp.response.lower()

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_unexpected_error_handled(self, mock_boto):
        mock_client = MagicMock()
        mock_client.invoke_agent.side_effect = RuntimeError("unexpected")
        mock_boto.return_value = mock_client
        svc = _make_service()
        resp = await svc.process_message("test", _session())
        assert "unexpected error" in resp.response.lower()

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_json_extraction_from_response(self, mock_boto):
        json_block = '```json\n{"finding": "critical"}\n```'
        mock_client = MagicMock()
        mock_client.invoke_agent.return_value = {
            "completion": [
                {"chunk": {"bytes": json_block.encode("utf-8")}},
            ],
            "sessionId": "s1",
        }
        mock_boto.return_value = mock_client
        svc = _make_service()
        resp = await svc.process_message("check", _session())
        assert resp.structured_data == {"finding": "critical"}


# ---------------------------------------------------------------------------
# _execute_security_mcp_function
# ---------------------------------------------------------------------------

class TestSecurityMCPFunctions:
    @pytest.mark.asyncio
    async def test_check_security_services(self):
        svc = _make_service()
        result = await svc._execute_security_mcp_function(
            "CheckSecurityServices", {"region": "us-east-1"}
        )
        assert result["region"] == "us-east-1"
        assert "service_statuses" in result
        assert "GuardDuty" in result["service_statuses"]

    @pytest.mark.asyncio
    async def test_get_security_findings(self):
        svc = _make_service()
        result = await svc._execute_security_mcp_function(
            "GetSecurityFindings", {"service": "guardduty"}
        )
        assert result["findings_count"] == 3
        assert len(result["findings"]) == 3

    @pytest.mark.asyncio
    async def test_check_storage_encryption(self):
        svc = _make_service()
        result = await svc._execute_security_mcp_function(
            "CheckStorageEncryption", {"services": ["s3", "ebs"]}
        )
        assert "compliance_by_service" in result
        assert "s3" in result["compliance_by_service"]

    @pytest.mark.asyncio
    async def test_unknown_function(self):
        svc = _make_service()
        result = await svc._execute_security_mcp_function("UnknownFunc", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# _execute_aws_api_mcp_function
# ---------------------------------------------------------------------------

class TestAWSAPIMCPFunction:
    @pytest.mark.asyncio
    async def test_returns_string(self):
        svc = _make_service()
        result = await svc._execute_aws_api_mcp_function("SomeFunc", {"a": "1"})
        assert isinstance(result, str)
        assert "SomeFunc" in result


# ---------------------------------------------------------------------------
# _generate_basic_summary
# ---------------------------------------------------------------------------

class TestGenerateBasicSummary:
    def test_check_security_services_summary(self):
        svc = _make_service()
        data = {
            "services_checked": ["GuardDuty"],
            "all_enabled": True,
            "service_statuses": {"GuardDuty": {"enabled": True, "status": "healthy"}},
            "recommendations": ["Enable X"],
        }
        result = svc._generate_basic_summary(data, "CheckSecurityServices")
        assert "Security Services Status" in result
        assert "GuardDuty" in result

    def test_get_security_findings_summary(self):
        svc = _make_service()
        data = {
            "service": "guardduty",
            "findings_count": 1,
            "findings": [{"severity": "HIGH", "title": "Bad thing"}],
        }
        result = svc._generate_basic_summary(data, "GetSecurityFindings")
        assert "Security Findings" in result
        assert "HIGH" in result

    def test_check_storage_encryption_summary(self):
        svc = _make_service()
        data = {
            "compliant_resources": 3,
            "non_compliant_resources": 1,
            "compliance_by_service": {
                "s3": {"total": 2, "encrypted": 1, "unencrypted": 1}
            },
        }
        result = svc._generate_basic_summary(data, "CheckStorageEncryption")
        assert "Encryption" in result

    def test_unknown_function_summary(self):
        svc = _make_service()
        result = svc._generate_basic_summary({"key": "val"}, "RandomFunc")
        assert "RandomFunc" in result

    def test_summary_error_handling(self):
        svc = _make_service()
        # Pass None to trigger exception in summary logic
        result = svc._generate_basic_summary(None, "Test")
        assert "Test" in result


# ---------------------------------------------------------------------------
# _handle_return_control
# ---------------------------------------------------------------------------

class TestHandleReturnControl:
    @pytest.mark.asyncio
    async def test_empty_invocation_inputs(self):
        svc = _make_service()
        result = await svc._handle_return_control(
            {"invocationInputs": []}, _session()
        )
        assert "No tools" in result

    @pytest.mark.asyncio
    async def test_function_invocation(self):
        svc = _make_service()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "security-mcp-server",
                        "function": "CheckSecurityServices",
                        "parameters": [
                            {"name": "region", "value": "us-east-1", "type": "string"}
                        ],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, _session())
        assert "CheckSecurityServices" in result

    @pytest.mark.asyncio
    async def test_array_parameter_parsing(self):
        svc = _make_service()
        payload = {
            "invocationInputs": [
                {
                    "functionInvocationInput": {
                        "actionGroup": "security-mcp-server",
                        "function": "CheckSecurityServices",
                        "parameters": [
                            {
                                "name": "services",
                                "value": "[GuardDuty, SecurityHub]",
                                "type": "array",
                            }
                        ],
                    }
                }
            ]
        }
        result = await svc._handle_return_control(payload, _session())
        assert isinstance(result, str)
