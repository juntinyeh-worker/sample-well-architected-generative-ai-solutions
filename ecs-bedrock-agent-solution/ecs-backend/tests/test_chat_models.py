# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for models/chat_models.py
"""

from datetime import datetime

import pytest
from models.chat_models import (
    BedrockResponse,
    ChatMessage,
    ChatSession,
    ToolExecution,
    ToolExecutionStatus,
)


# ---------------------------------------------------------------------------
# ToolExecutionStatus
# ---------------------------------------------------------------------------

class TestToolExecutionStatus:
    def test_status_values(self):
        assert ToolExecutionStatus.SUCCESS == "success"
        assert ToolExecutionStatus.ERROR == "error"
        assert ToolExecutionStatus.PENDING == "pending"

    def test_status_is_string(self):
        assert isinstance(ToolExecutionStatus.SUCCESS, str)


# ---------------------------------------------------------------------------
# ToolExecution
# ---------------------------------------------------------------------------

class TestToolExecution:
    def test_minimal_creation(self):
        te = ToolExecution(tool_name="mytool", timestamp=datetime(2026, 1, 1))
        assert te.tool_name == "mytool"
        assert te.parameters == {}
        assert te.result is None
        assert te.status == ToolExecutionStatus.SUCCESS

    def test_full_creation(self):
        te = ToolExecution(
            tool_name="check",
            parameters={"region": "us-east-1"},
            result={"ok": True},
            timestamp=datetime(2026, 1, 1),
            status=ToolExecutionStatus.ERROR,
            error_message="boom",
            tool_input={"a": 1},
            tool_output="done",
        )
        assert te.error_message == "boom"
        assert te.tool_input == {"a": 1}
        assert te.tool_output == "done"

    def test_model_dump_roundtrip(self):
        te = ToolExecution(tool_name="x", timestamp=datetime(2026, 1, 1))
        data = te.model_dump()
        assert data["tool_name"] == "x"
        te2 = ToolExecution(**data)
        assert te2.tool_name == te.tool_name


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class TestChatMessage:
    def test_user_message(self):
        msg = ChatMessage(role="user", content="hello", timestamp=datetime(2026, 1, 1))
        assert msg.role == "user"
        assert msg.tool_executions == []

    def test_assistant_message_with_tools(self):
        te = ToolExecution(tool_name="t", timestamp=datetime(2026, 1, 1))
        msg = ChatMessage(
            role="assistant",
            content="reply",
            timestamp=datetime(2026, 1, 1),
            tool_executions=[te],
        )
        assert len(msg.tool_executions) == 1


# ---------------------------------------------------------------------------
# ChatSession
# ---------------------------------------------------------------------------

class TestChatSession:
    def test_empty_session(self):
        s = ChatSession(
            session_id="s1", created_at=datetime(2026, 1, 1), messages=[]
        )
        assert s.session_id == "s1"
        assert s.context == {}
        assert s.messages == []

    def test_session_with_messages(self):
        msg = ChatMessage(role="user", content="hi", timestamp=datetime(2026, 1, 1))
        s = ChatSession(
            session_id="s2",
            created_at=datetime(2026, 1, 1),
            messages=[msg],
            context={"key": "val"},
        )
        assert len(s.messages) == 1
        assert s.context["key"] == "val"


# ---------------------------------------------------------------------------
# BedrockResponse
# ---------------------------------------------------------------------------

class TestBedrockResponse:
    def test_auto_timestamp(self):
        resp = BedrockResponse(response="hello")
        assert resp.timestamp is not None
        assert isinstance(resp.timestamp, datetime)

    def test_explicit_timestamp(self):
        ts = datetime(2026, 6, 15)
        resp = BedrockResponse(response="hello", timestamp=ts)
        assert resp.timestamp == ts

    def test_defaults(self):
        resp = BedrockResponse(response="hi")
        assert resp.tool_executions == []
        assert resp.structured_data is None
        assert resp.human_summary is None
        assert resp.model_id is None
        assert resp.session_id is None

    def test_full_creation(self):
        te = ToolExecution(tool_name="t", timestamp=datetime(2026, 1, 1))
        resp = BedrockResponse(
            response="analysis",
            tool_executions=[te],
            structured_data={"k": "v"},
            human_summary="summary",
            model_id="claude",
            session_id="sess1",
        )
        assert resp.model_id == "claude"
        assert len(resp.tool_executions) == 1
