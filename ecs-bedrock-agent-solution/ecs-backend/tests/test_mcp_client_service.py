# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/mcp_client_service.py
"""

import pytest


class TestMCPClientService:
    def test_demo_mode_default(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService()
        assert svc.demo_mode is True

    def test_non_demo_mode(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService(demo_mode=False)
        assert svc.demo_mode is False

    @pytest.mark.asyncio
    async def test_health_check_demo(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService(demo_mode=True)
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_non_demo(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService(demo_mode=False)
        assert await svc.health_check() == "degraded"

    @pytest.mark.asyncio
    async def test_get_available_tools_demo(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService(demo_mode=True)
        tools = await svc.get_available_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "demo_tool"

    @pytest.mark.asyncio
    async def test_get_available_tools_non_demo(self):
        from services.mcp_client_service import MCPClientService
        svc = MCPClientService(demo_mode=False)
        tools = await svc.get_available_tools()
        assert tools == []
