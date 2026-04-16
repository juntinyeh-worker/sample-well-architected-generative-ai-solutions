# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/llm_orchestrator_service.py
"""

import io
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.chat_models import ChatSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(initialized=False):
    ctx = {}
    if initialized:
        ctx = {
            "orchestrator_initialized": True,
            "bedrock_available": True,
            "system_prompt": "You are a test assistant.",
            "available_tools": [],
        }
    return ChatSession(
        session_id="test-sess",
        created_at=datetime(2026, 1, 1),
        messages=[],
        context=ctx,
    )


def _make_bedrock_response(text):
    body = io.BytesIO(
        json.dumps(
            {"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"}
        ).encode()
    )
    return {"body": body}


def _make_service(bedrock_available=True):
    """Create LLMOrchestratorService with mocked dependencies."""
    with patch("services.llm_orchestrator_service.get_config") as mock_cfg:
        mock_cfg.return_value = "us-east-1"
        with patch("services.llm_orchestrator_service.MCPClientService") as mock_mcp_cls:
            mock_mcp = MagicMock()
            mock_mcp.health_check = AsyncMock(return_value="healthy")
            mock_mcp.get_available_tools = AsyncMock(return_value=[
                {"name": "CheckSecurityServices", "description": "Check security services"},
                {"name": "CheckStorageEncryption", "description": "Check storage encryption"},
            ])
            mock_mcp.call_tool = AsyncMock(return_value={"status": "ok"})
            mock_mcp_cls.return_value = mock_mcp

            from services.llm_orchestrator_service import LLMOrchestratorService
            svc = LLMOrchestratorService()

    if bedrock_available:
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(
            '{"intent": "test", "tools_to_use": [], "analysis_approach": "direct"}'
        )
        svc._bedrock_runtime = mock_bedrock
        svc._bedrock_initialization_error = None
    else:
        svc._bedrock_runtime = None
        from services.llm_orchestrator_service import BedrockInitializationError
        svc._bedrock_initialization_error = BedrockInitializationError("no bedrock")

    return svc


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

class TestLLMOrchestratorInit:
    def test_init(self):
        svc = _make_service()
        assert svc.model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert svc.tools_discovered is False

    def test_bedrock_available(self):
        svc = _make_service(bedrock_available=True)
        assert svc._is_bedrock_available() is True

    def test_bedrock_not_available(self):
        svc = _make_service(bedrock_available=False)
        assert svc._is_bedrock_available() is False


# ---------------------------------------------------------------------------
# Lazy bedrock_runtime property
# ---------------------------------------------------------------------------

class TestBedrockRuntimeProperty:
    @patch("boto3.client")
    def test_lazy_init_success(self, mock_boto):
        mock_boto.return_value = MagicMock()
        with patch("services.llm_orchestrator_service.get_config", return_value="us-east-1"):
            with patch("services.llm_orchestrator_service.MCPClientService"):
                from services.llm_orchestrator_service import LLMOrchestratorService
                svc = LLMOrchestratorService()
                _ = svc.bedrock_runtime
                assert svc._bedrock_runtime is not None

    @patch("boto3.client", side_effect=Exception("fail"))
    def test_lazy_init_failure_raises(self, mock_boto):
        with patch("services.llm_orchestrator_service.get_config", return_value="us-east-1"):
            with patch("services.llm_orchestrator_service.MCPClientService"):
                from services.llm_orchestrator_service import (
                    LLMOrchestratorService,
                    BedrockInitializationError,
                )
                svc = LLMOrchestratorService()
                with pytest.raises(BedrockInitializationError):
                    _ = svc.bedrock_runtime


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self):
        svc = _make_service(bedrock_available=True)
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_no_bedrock(self):
        svc = _make_service(bedrock_available=False)
        assert await svc.health_check() == "degraded"

    @pytest.mark.asyncio
    async def test_unhealthy_mcp_down(self):
        svc = _make_service(bedrock_available=True)
        svc.mcp_service.health_check = AsyncMock(return_value="unhealthy")
        assert await svc.health_check() == "unhealthy"


# ---------------------------------------------------------------------------
# initialize_session / _discover_tools
# ---------------------------------------------------------------------------

class TestInitializeSession:
    @pytest.mark.asyncio
    async def test_initialize_session(self):
        svc = _make_service()
        session = _session()
        result = await svc.initialize_session(session)
        assert result["status"] == "initialized"
        assert result["tools_count"] == 2
        assert session.context["orchestrator_initialized"] is True

    @pytest.mark.asyncio
    async def test_initialize_session_error(self):
        svc = _make_service()
        svc.mcp_service.get_available_tools = AsyncMock(side_effect=Exception("fail"))
        session = _session()
        result = await svc.initialize_session(session)
        # Should still return initialized (tools just empty)
        assert result["status"] == "initialized"
        assert result["tools_count"] == 0

    @pytest.mark.asyncio
    async def test_discover_tools(self):
        svc = _make_service()
        await svc._discover_tools()
        assert svc.tools_discovered is True
        assert len(svc.available_tools) == 2

    @pytest.mark.asyncio
    async def test_discover_tools_failure(self):
        svc = _make_service()
        svc.mcp_service.get_available_tools = AsyncMock(side_effect=RuntimeError("x"))
        await svc._discover_tools()
        assert svc.available_tools == []


# ---------------------------------------------------------------------------
# _generate_system_prompt
# ---------------------------------------------------------------------------

class TestGenerateSystemPrompt:
    def test_contains_tools(self):
        svc = _make_service()
        svc.available_tools = [
            {"name": "Tool1", "description": "Does thing 1"},
        ]
        prompt = svc._generate_system_prompt()
        assert "Tool1" in prompt
        assert "Does thing 1" in prompt

    def test_no_tools(self):
        svc = _make_service()
        svc.available_tools = []
        prompt = svc._generate_system_prompt()
        assert "No tools currently available" in prompt

    def test_bedrock_unavailable_status(self):
        svc = _make_service(bedrock_available=False)
        prompt = svc._generate_system_prompt()
        assert "unavailable" in prompt


# ---------------------------------------------------------------------------
# _analyze_user_request_fallback
# ---------------------------------------------------------------------------

class TestAnalyzeUserRequestFallback:
    def test_security_keyword(self):
        svc = _make_service()
        result = svc._analyze_user_request_fallback("check my security posture")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckSecurityServices" in tools

    def test_storage_keyword(self):
        svc = _make_service()
        result = svc._analyze_user_request_fallback("are my s3 buckets encrypted?")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckStorageEncryption" in tools

    def test_network_keyword(self):
        svc = _make_service()
        result = svc._analyze_user_request_fallback("check vpc security groups")
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckNetworkSecurity" in tools

    def test_no_keywords(self):
        svc = _make_service()
        result = svc._analyze_user_request_fallback("hello world")
        assert result["tools_to_use"] == []

    def test_multiple_keywords(self):
        svc = _make_service()
        result = svc._analyze_user_request_fallback(
            "check security and s3 storage encryption"
        )
        tools = [t["name"] for t in result["tools_to_use"]]
        assert "CheckSecurityServices" in tools
        assert "CheckStorageEncryption" in tools


# ---------------------------------------------------------------------------
# _analyze_user_request (with Bedrock)
# ---------------------------------------------------------------------------

class TestAnalyzeUserRequest:
    @pytest.mark.asyncio
    async def test_parses_llm_json(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.return_value = _make_bedrock_response(
            '{"intent": "security check", "tools_to_use": [{"name": "CheckSecurityServices", "arguments": {"region": "us-east-1"}, "reason": "security"}], "analysis_approach": "tool"}'
        )
        session = _session(initialized=True)
        result = await svc._analyze_user_request("check security", session)
        assert result["intent"] == "security check"
        assert len(result["tools_to_use"]) == 1

    @pytest.mark.asyncio
    async def test_fallback_on_bad_json(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.return_value = _make_bedrock_response(
            "I cannot parse this as JSON"
        )
        session = _session(initialized=True)
        result = await svc._analyze_user_request("check security", session)
        assert result["tools_to_use"] == []

    @pytest.mark.asyncio
    async def test_fallback_on_bedrock_error(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.side_effect = Exception("timeout")
        session = _session(initialized=True)
        result = await svc._analyze_user_request("check security", session)
        # Should fall back to keyword matching
        assert "tools_to_use" in result


# ---------------------------------------------------------------------------
# _generate_fallback_response
# ---------------------------------------------------------------------------

class TestGenerateFallbackResponse:
    def test_no_tool_results(self):
        svc = _make_service()
        result = svc._generate_fallback_response("hello", [])
        assert "limited mode" in result.lower()

    def test_with_tool_results(self):
        svc = _make_service()
        tool_results = [
            {
                "tool_name": "CheckSecurityServices",
                "result": {"all_enabled": True, "resources_checked": 5},
            }
        ]
        result = svc._generate_fallback_response("check security", tool_results)
        assert "CheckSecurityServices" in result
        assert "All services enabled" in result

    def test_with_non_compliant_results(self):
        svc = _make_service()
        tool_results = [
            {
                "tool_name": "CheckStorageEncryption",
                "result": {
                    "compliant_resources": 3,
                    "non_compliant_resources": 2,
                },
            }
        ]
        result = svc._generate_fallback_response("check storage", tool_results)
        assert "Compliant resources: 3" in result
        assert "Non-compliant resources: 2" in result


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_with_bedrock_no_tools(self):
        svc = _make_service()
        # Analysis returns no tools
        svc._bedrock_runtime.invoke_model.side_effect = [
            # First call: _analyze_user_request
            _make_bedrock_response(
                '{"intent": "greeting", "tools_to_use": [], "analysis_approach": "direct"}'
            ),
            # Second call: _generate_final_response
            _make_bedrock_response("Hello! How can I help you?"),
        ]
        session = _session(initialized=True)
        resp = await svc.process_message("hello", session)
        assert resp.response == "Hello! How can I help you?"
        assert resp.tool_executions == []

    @pytest.mark.asyncio
    async def test_with_bedrock_with_tools(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.side_effect = [
            # Analysis
            _make_bedrock_response(
                '{"intent": "security", "tools_to_use": [{"name": "CheckSecurityServices", "arguments": {"region": "us-east-1"}}], "analysis_approach": "tool"}'
            ),
            # Final response
            _make_bedrock_response("Security looks good overall."),
        ]
        session = _session(initialized=True)
        resp = await svc.process_message("check security", session)
        assert resp.response == "Security looks good overall."
        assert len(resp.tool_executions) == 1
        assert resp.tool_executions[0].tool_name == "CheckSecurityServices"

    @pytest.mark.asyncio
    async def test_tool_execution_failure(self):
        svc = _make_service()
        svc.mcp_service.call_tool = AsyncMock(side_effect=Exception("tool broke"))
        svc._bedrock_runtime.invoke_model.side_effect = [
            _make_bedrock_response(
                '{"intent": "test", "tools_to_use": [{"name": "CheckSecurityServices", "arguments": {}}], "analysis_approach": "tool"}'
            ),
            _make_bedrock_response("There was a problem."),
        ]
        session = _session(initialized=True)
        resp = await svc.process_message("check security", session)
        assert resp.tool_executions[0].status.value == "error"
        assert resp.tool_executions[0].error_message == "tool broke"

    @pytest.mark.asyncio
    async def test_without_bedrock_security(self):
        svc = _make_service(bedrock_available=False)
        session = _session()
        resp = await svc.process_message("check my security", session)
        assert resp.model_id == "fallback-mode"
        # Should have attempted tool call via keyword matching
        assert isinstance(resp.response, str)

    @pytest.mark.asyncio
    async def test_without_bedrock_storage(self):
        svc = _make_service(bedrock_available=False)
        session = _session()
        resp = await svc.process_message("check s3 encryption", session)
        assert resp.model_id == "fallback-mode"

    @pytest.mark.asyncio
    async def test_without_bedrock_no_keywords(self):
        svc = _make_service(bedrock_available=False)
        session = _session()
        resp = await svc.process_message("hello", session)
        assert "limited mode" in resp.response.lower()

    @pytest.mark.asyncio
    async def test_session_auto_initializes(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.side_effect = [
            # Analysis
            _make_bedrock_response(
                '{"intent": "test", "tools_to_use": [], "analysis_approach": "direct"}'
            ),
            # Final
            _make_bedrock_response("Done."),
        ]
        session = _session(initialized=False)
        resp = await svc.process_message("hello", session)
        assert session.context.get("orchestrator_initialized") is True

    @pytest.mark.asyncio
    async def test_process_message_exception(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.side_effect = RuntimeError("catastrophic")
        session = _session(initialized=True)
        resp = await svc.process_message("hello", session)
        assert "error" in resp.response.lower()


# ---------------------------------------------------------------------------
# _generate_final_response
# ---------------------------------------------------------------------------

class TestGenerateFinalResponse:
    @pytest.mark.asyncio
    async def test_with_bedrock(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.return_value = _make_bedrock_response(
            "Here is a summary of findings."
        )
        result = await svc._generate_final_response(
            "check security",
            {"intent": "security"},
            [{"tool_name": "CheckSecurityServices", "result": {"ok": True}}],
            _session(initialized=True),
        )
        assert result["response"] == "Here is a summary of findings."
        assert result["structured_data"] is not None

    @pytest.mark.asyncio
    async def test_without_bedrock(self):
        svc = _make_service(bedrock_available=False)
        result = await svc._generate_final_response(
            "check security",
            {"intent": "security"},
            [],
            _session(initialized=True),
        )
        assert isinstance(result["response"], str)

    @pytest.mark.asyncio
    async def test_bedrock_error_fallback(self):
        svc = _make_service()
        svc._bedrock_runtime.invoke_model.side_effect = Exception("model error")
        result = await svc._generate_final_response(
            "test", {"intent": "test"}, [], _session(initialized=True)
        )
        assert "error" in result["response"].lower()


# ---------------------------------------------------------------------------
# get_session_info
# ---------------------------------------------------------------------------

class TestGetSessionInfo:
    def test_returns_session_info(self):
        svc = _make_service()
        svc.available_tools = [
            {"name": "T1", "description": "D1"},
        ]
        session = _session(initialized=True)
        info = svc.get_session_info(session)
        assert info["session_id"] == "test-sess"
        assert info["tools_available"] == 1
        assert info["initialized"] is True
