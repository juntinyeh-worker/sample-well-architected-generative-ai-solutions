# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/auth_service.py
"""

from unittest.mock import MagicMock, patch

import pytest


class TestAuthServiceInit:
    @patch("boto3.client")
    def test_lazy_cognito_client(self, mock_boto):
        mock_boto.return_value = MagicMock()
        from services.auth_service import AuthService
        svc = AuthService()
        assert svc._cognito_client is None
        # Accessing the property triggers lazy init
        _ = svc.cognito_client
        mock_boto.assert_called_once_with("cognito-idp")

    @patch("boto3.client", side_effect=Exception("no creds"))
    def test_cognito_client_init_failure(self, mock_boto):
        from services.auth_service import AuthService
        svc = AuthService()
        result = svc.cognito_client
        assert result is None


class TestAuthServiceVerifyToken:
    @pytest.mark.asyncio
    async def test_verify_token_returns_demo_user(self):
        from services.auth_service import AuthService
        svc = AuthService()
        user = await svc.verify_token("any-token")
        assert user["user_id"] == "demo_user"
        assert "email" in user

    @pytest.mark.asyncio
    async def test_verify_token_returns_dict(self):
        from services.auth_service import AuthService
        svc = AuthService()
        user = await svc.verify_token("token-123")
        assert isinstance(user, dict)
