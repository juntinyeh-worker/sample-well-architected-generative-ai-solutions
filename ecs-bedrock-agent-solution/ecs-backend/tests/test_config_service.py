# MIT No Attribution
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""
Unit tests for services/config_service.py
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from botocore.exceptions import ClientError, NoCredentialsError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_error(code="ParameterNotFound", msg="not found"):
    return ClientError({"Error": {"Code": code, "Message": msg}}, "GetParameter")


# ---------------------------------------------------------------------------
# ConfigService — initialisation
# ---------------------------------------------------------------------------

class TestConfigServiceInit:
    @patch("boto3.client")
    def test_ssm_available_when_connected(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc._ssm_available is True

    @patch("boto3.client")
    def test_ssm_unavailable_on_no_credentials(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc._ssm_available is False
        assert svc._ssm_client is None

    @patch("boto3.client")
    def test_ssm_unavailable_on_client_error(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.side_effect = _client_error("AccessDenied")
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc._ssm_available is False


# ---------------------------------------------------------------------------
# ConfigService._load_env_file
# ---------------------------------------------------------------------------

class TestLoadEnvFile:
    @patch("boto3.client")
    def test_loads_env_file(self, mock_boto, monkeypatch, tmp_path):
        mock_boto.side_effect = NoCredentialsError()

        env_content = "MY_VAR=hello\n# comment\nANOTHER=world\n"
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        monkeypatch.delenv("MY_VAR", raising=False)
        monkeypatch.delenv("ANOTHER", raising=False)

        from services.config_service import ConfigService

        with patch.object(Path, "__truediv__", return_value=env_file):
            # Patch the path resolution to point to our tmp .env
            with patch("services.config_service.Path") as mock_path:
                mock_path.return_value.__truediv__ = MagicMock(return_value=mock_path.return_value)
                mock_path.return_value.parent.__truediv__ = MagicMock(return_value=env_file)
                # Just verify the method doesn't crash
                svc = ConfigService(ssm_prefix="/test/")
                assert svc is not None

    @patch("boto3.client")
    def test_no_env_file_is_ok(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc is not None


# ---------------------------------------------------------------------------
# ConfigService.get_config_value — priority chain
# ---------------------------------------------------------------------------

class TestGetConfigValue:
    @patch("boto3.client")
    def test_returns_default_when_nothing_set(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc.get_config_value("NONEXISTENT", "fallback") == "fallback"

    @patch("boto3.client")
    def test_returns_env_var(self, mock_boto, monkeypatch):
        mock_boto.side_effect = NoCredentialsError()
        monkeypatch.setenv("MY_KEY", "from_env")
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc.get_config_value("MY_KEY", "default") == "from_env"

    @patch("boto3.client")
    def test_ssm_takes_priority_over_env(self, mock_boto, monkeypatch):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "from_ssm"}
        }
        mock_boto.return_value = mock_client
        monkeypatch.setenv("ENHANCED_SECURITY_AGENT_ID", "from_env")

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        result = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID", "default")
        assert result == "from_ssm"

    @patch("boto3.client")
    def test_cache_hit(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "cached"}
        }
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        # First call populates cache
        v1 = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID")
        # Second call uses cache
        v2 = svc.get_config_value("ENHANCED_SECURITY_AGENT_ID")
        assert v1 == v2 == "cached"
        # SSM should only be called once
        assert mock_client.get_parameter.call_count == 1

    @patch("boto3.client")
    def test_returns_none_for_unmapped_ssm_key(self, mock_boto, monkeypatch):
        """Keys not in the SSM mapping return None from _get_ssm_parameter."""
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        # This key has no SSM mapping, so _get_ssm_parameter returns None
        assert svc._get_ssm_parameter("RANDOM_KEY") is None


# ---------------------------------------------------------------------------
# ConfigService._get_ssm_parameter — key mapping
# ---------------------------------------------------------------------------

class TestGetSSMParameter:
    @patch("boto3.client")
    def test_agent_id_mapping(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "agent-123"}
        }
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        result = svc._get_ssm_parameter("ENHANCED_SECURITY_AGENT_ID")
        assert result == "agent-123"
        mock_client.get_parameter.assert_called_with(
            Name="/coa/agent/wa-security-agent/agent-id",
            WithDecryption=True,
        )

    @patch("boto3.client")
    def test_alias_id_mapping(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "alias-456"}
        }
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        result = svc._get_ssm_parameter("ENHANCED_SECURITY_AGENT_ALIAS_ID")
        assert result == "alias-456"
        mock_client.get_parameter.assert_called_with(
            Name="/coa/agent/wa-security-agent/alias-id",
            WithDecryption=True,
        )

    @patch("boto3.client")
    def test_parameter_not_found(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.side_effect = _client_error("ParameterNotFound")
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        assert svc._get_ssm_parameter("ENHANCED_SECURITY_AGENT_ID") is None

    @patch("boto3.client")
    def test_client_error_other(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.get_parameter.side_effect = _client_error("AccessDenied")
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/coa/")
        assert svc._get_ssm_parameter("ENHANCED_SECURITY_AGENT_ID") is None


# ---------------------------------------------------------------------------
# ConfigService.refresh_cache / get_all_config / get_ssm_status
# ---------------------------------------------------------------------------

class TestConfigServiceMisc:
    @patch("boto3.client")
    def test_refresh_cache_clears(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        svc._config_cache["ssm:key"] = "val"
        svc.refresh_cache()
        assert len(svc._config_cache) == 0

    @patch("boto3.client")
    def test_get_all_config_returns_dict(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        result = svc.get_all_config()
        assert isinstance(result, dict)

    @patch("boto3.client")
    def test_get_ssm_status(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        status = svc.get_ssm_status()
        assert "available" in status
        assert "prefix" in status
        assert "cached_parameters" in status

    @patch("boto3.client")
    def test_set_ssm_parameter_no_client(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc.set_ssm_parameter("key", "val") is False

    @patch("boto3.client")
    def test_set_ssm_parameter_success(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {"Parameters": []}
        mock_client.put_parameter.return_value = {"Version": 1}
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        assert svc.set_ssm_parameter("key", "val", description="desc") is True

    @patch("boto3.client")
    def test_list_ssm_parameters_no_client(self, mock_boto):
        mock_boto.side_effect = NoCredentialsError()
        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        result = svc.list_ssm_parameters()
        assert "error" in result

    @patch("boto3.client")
    def test_list_ssm_parameters_success(self, mock_boto):
        mock_client = MagicMock()
        mock_client.describe_parameters.return_value = {
            "Parameters": [
                {"Name": "/test/key1", "Type": "String", "Description": "d"}
            ]
        }
        mock_boto.return_value = mock_client

        from services.config_service import ConfigService
        svc = ConfigService(ssm_prefix="/test/")
        result = svc.list_ssm_parameters()
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

class TestGetConfigFunction:
    @patch("boto3.client")
    def test_get_config_convenience(self, mock_boto, monkeypatch):
        mock_boto.side_effect = NoCredentialsError()
        monkeypatch.setenv("SOME_KEY", "val")
        # Import fresh to use module-level config_service
        from services.config_service import get_config
        # Will fall back to env since SSM is unavailable
        result = get_config("SOME_KEY", "default")
        assert result == "val"
