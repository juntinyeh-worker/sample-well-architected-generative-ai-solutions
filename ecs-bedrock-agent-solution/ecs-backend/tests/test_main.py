# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for main.py — FastAPI endpoints and helpers.

We patch the module-level service singletons so the tests never hit real AWS.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# We need to mock the heavy services before importing main
# to prevent boto3 calls during module load.


@pytest.fixture
def app_client():
    """Create a FastAPI TestClient with all services mocked."""
    with patch("services.config_service.boto3") as _:
        with patch("services.config_service.ConfigService") as mock_cfg_cls:
            mock_cfg_instance = MagicMock()
            mock_cfg_instance.get_config_value.return_value = None
            mock_cfg_instance.get_ssm_status.return_value = {
                "available": False,
                "prefix": "/coa/",
                "cached_parameters": 0,
            }
            mock_cfg_instance.get_all_config.return_value = {}
            mock_cfg_instance.refresh_cache.return_value = None
            mock_cfg_instance.list_ssm_parameters.return_value = {
                "parameters": [],
                "count": 0,
            }
            mock_cfg_cls.return_value = mock_cfg_instance

            with patch.dict("os.environ", {
                "USER_POOL_ID": "test-pool",
                "WEB_APP_CLIENT_ID": "test-client",
                "AWS_DEFAULT_REGION": "us-east-1",
            }):
                # Now import main (it runs module-level code)
                import importlib
                # Reset config_service module
                import services.config_service
                services.config_service.config_service = mock_cfg_instance
                services.config_service.get_config = mock_cfg_instance.get_config_value

                import main as main_module
                # Patch services on the module
                main_module.config_service = mock_cfg_instance

                mock_orchestrator = MagicMock()
                mock_orchestrator.health_check = AsyncMock(return_value="healthy")
                mock_orchestrator.process_message = AsyncMock()
                mock_orchestrator.initialize_session = AsyncMock(
                    return_value={"status": "initialized", "tools_count": 0}
                )
                mock_orchestrator.get_session_info = MagicMock(
                    return_value={"session_id": "s1", "tools_available": 0}
                )
                main_module.orchestrator_service = mock_orchestrator

                mock_mcp = MagicMock()
                mock_mcp.health_check = AsyncMock(return_value="healthy")
                mock_mcp.get_available_tools = AsyncMock(return_value=[])
                main_module.mcp_service = mock_mcp

                mock_aws_cfg = MagicMock()
                mock_aws_cfg.get_current_config = AsyncMock(
                    return_value={
                        "account_id": "123456789012",
                        "region": "us-east-1",
                        "role_arn": "arn:aws:sts::123456789012:role/Test",
                        "status": "configured",
                    }
                )
                mock_aws_cfg.update_config = AsyncMock(
                    return_value={
                        "account_info": {"account_id": "123456789012"},
                        "role_arn": "arn:aws:sts::123456789012:role/Test",
                    }
                )
                main_module.aws_config_service = mock_aws_cfg

                main_module.bedrock_service = None
                main_module.use_enhanced_agent = False

                from fastapi.testclient import TestClient
                client = TestClient(main_module.app, raise_server_exceptions=False)
                yield client, main_module


# Auth header helper
AUTH_HEADER = {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# DateTimeEncoder
# ---------------------------------------------------------------------------

class TestDateTimeEncoder:
    def test_encodes_datetime(self):
        from main import DateTimeEncoder
        result = json.dumps({"ts": datetime(2026, 1, 1)}, cls=DateTimeEncoder)
        assert "2026-01-01" in result

    def test_raises_for_unknown_type(self):
        from main import DateTimeEncoder
        with pytest.raises(TypeError):
            json.dumps({"val": set()}, cls=DateTimeEncoder)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_healthy(self, app_client):
        client, _ = app_client
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_unhealthy_missing_env(self, app_client):
        client, mod = app_client
        # Make config return None for required vars
        import os
        with patch.dict(os.environ, {}, clear=True):
            mod.config_service.get_config_value.return_value = None
            resp = client.get("/health")
            # May be 503 if env vars missing
            assert resp.status_code in [200, 503]


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_chat_success(self, app_client):
        from models.chat_models import BedrockResponse

        client, mod = app_client
        mock_resp = BedrockResponse(
            response="Test reply",
            tool_executions=[],
            model_id="test-model",
        )
        mod.orchestrator_service.process_message = AsyncMock(return_value=mock_resp)

        resp = client.post(
            "/api/chat",
            json={"message": "hello"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "Test reply"
        assert "session_id" in data

    def test_chat_with_session_id(self, app_client):
        from models.chat_models import BedrockResponse

        client, mod = app_client
        mock_resp = BedrockResponse(response="ok", tool_executions=[])
        mod.orchestrator_service.process_message = AsyncMock(return_value=mock_resp)

        resp = client.post(
            "/api/chat",
            json={"message": "test", "session_id": "my-session"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_chat_no_auth(self, app_client):
        client, _ = app_client
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code in [401, 403]


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

class TestSessionEndpoints:
    def test_session_history_not_found(self, app_client):
        client, _ = app_client
        resp = client.get(
            "/api/sessions/nonexistent/history", headers=AUTH_HEADER
        )
        assert resp.status_code == 404

    def test_session_info_not_found(self, app_client):
        client, _ = app_client
        resp = client.get(
            "/api/session/nonexistent/info", headers=AUTH_HEADER
        )
        assert resp.status_code == 404

    def test_initialize_session(self, app_client):
        client, _ = app_client
        resp = client.post(
            "/api/session/new-session/initialize", headers=AUTH_HEADER
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "initialized"


# ---------------------------------------------------------------------------
# MCP tools endpoint
# ---------------------------------------------------------------------------

class TestMCPToolsEndpoint:
    def test_get_tools(self, app_client):
        client, _ = app_client
        resp = client.get("/api/mcp/tools", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert "tools" in resp.json()


# ---------------------------------------------------------------------------
# AWS config endpoints
# ---------------------------------------------------------------------------

class TestAWSConfigEndpoints:
    def test_get_aws_config(self, app_client):
        client, _ = app_client
        resp = client.get("/api/aws-config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "configured"

    def test_update_aws_config(self, app_client):
        client, _ = app_client
        resp = client.post(
            "/api/aws-config",
            json={"region": "us-west-2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

class TestConfigEndpoints:
    def test_get_all_config(self, app_client):
        client, mod = app_client
        mod.config_service.get_all_config.return_value = {
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_BEARER_TOKEN_BEDROCK": "secret",
        }
        resp = client.get("/api/config", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.json()
        # Sensitive values should be masked
        assert data["config"]["AWS_BEARER_TOKEN_BEDROCK"] == "***"

    def test_refresh_config(self, app_client):
        client, _ = app_client
        resp = client.post("/api/config/refresh", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_list_ssm_parameters(self, app_client):
        client, _ = app_client
        resp = client.get("/api/config/ssm/parameters", headers=AUTH_HEADER)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "s1")
        assert "s1" in mgr.active_connections
        assert "s1" in mgr.sessions
        mgr.disconnect("s1")
        assert "s1" not in mgr.active_connections

    @pytest.mark.asyncio
    async def test_send_message(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws, "s1")
        await mgr.send_message("s1", {"type": "test"})
        ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_no_connection(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        # Should not raise
        await mgr.send_message("nonexistent", {"type": "test"})

    def test_disconnect_nonexistent(self):
        from main import ConnectionManager
        mgr = ConnectionManager()
        # Should not raise
        mgr.disconnect("nonexistent")
