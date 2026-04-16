# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/aws_config_service.py
"""

from unittest.mock import MagicMock, patch

import pytest


class TestAWSConfigServiceInit:
    @patch("boto3.client")
    def test_lazy_sts_client(self, mock_boto):
        mock_boto.return_value = MagicMock()
        from services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        assert svc._sts_client is None
        _ = svc.sts_client
        mock_boto.assert_called_with("sts")

    @patch("boto3.client", side_effect=Exception("no creds"))
    def test_sts_client_init_failure(self, mock_boto):
        from services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        assert svc.sts_client is None


class TestGetCurrentConfig:
    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_returns_account_info(self, mock_boto, monkeypatch):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        mock_client = MagicMock()
        mock_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:role/TestRole",
        }
        mock_boto.return_value = mock_client

        from services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        config = await svc.get_current_config()
        assert config["account_id"] == "123456789012"
        assert config["status"] == "configured"

    @pytest.mark.asyncio
    @patch("boto3.client", side_effect=Exception("fail"))
    async def test_returns_not_configured_on_error(self, mock_boto):
        from services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        config = await svc.get_current_config()
        assert config["status"] == "not_configured"
        assert config["account_id"] is None


class TestUpdateConfig:
    @pytest.mark.asyncio
    @patch("boto3.client")
    async def test_update_returns_current_config(self, mock_boto):
        mock_client = MagicMock()
        mock_client.get_caller_identity.return_value = {
            "Account": "111111111111",
            "Arn": "arn:aws:sts::111111111111:role/Test",
        }
        mock_boto.return_value = mock_client

        from services.aws_config_service import AWSConfigService
        svc = AWSConfigService()
        result = await svc.update_config(region="us-east-1")
        assert result["status"] == "configured"
