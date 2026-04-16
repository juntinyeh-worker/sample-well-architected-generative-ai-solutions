# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/bedrock_chat_service.py
"""

from unittest.mock import MagicMock, patch

import pytest


class TestBedrockChatService:
    @patch("boto3.client")
    def test_lazy_client(self, mock_boto):
        mock_boto.return_value = MagicMock()
        from services.bedrock_chat_service import BedrockChatService
        svc = BedrockChatService()
        assert svc._bedrock_client is None
        _ = svc.bedrock_client
        mock_boto.assert_called_once_with("bedrock-runtime")

    @patch("boto3.client", side_effect=Exception("nope"))
    def test_client_init_failure(self, mock_boto):
        from services.bedrock_chat_service import BedrockChatService
        svc = BedrockChatService()
        assert svc.bedrock_client is None

    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_health_check_healthy(self, mock_boto):
        mock_boto.return_value = MagicMock()
        from services.bedrock_chat_service import BedrockChatService
        svc = BedrockChatService()
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    @patch("boto3.client", side_effect=Exception("fail"))
    async def test_health_check_degraded(self, mock_boto):
        from services.bedrock_chat_service import BedrockChatService
        svc = BedrockChatService()
        result = await svc.health_check()
        assert result == "degraded"

    @pytest.mark.asyncio
    async def test_process_message(self):
        from services.bedrock_chat_service import BedrockChatService
        svc = BedrockChatService()
        result = await svc.process_message("hello", context={})
        assert result["response"] == "Echo: hello"
        assert "timestamp" in result
        assert result["tool_executions"] == []
