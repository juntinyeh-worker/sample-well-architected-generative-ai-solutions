"""
SigV4 signing layer.

Borrows botocore's SigV4Auth and credential chain — the same machinery
the AWS CLI and boto3 use internally. Callers never touch this directly.

The Support Interactions API is a REST API (not JSON 1.1 RPC):
  - Base URL: https://assistant.support.{region}.amazonaws.com
  - SigV4 service name: "support"
  - No X-Amz-Target header — operations are identified by HTTP method + path
"""

import json
import logging
import os
import sys
import time as _time
from typing import Any
from urllib.parse import urlencode

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import NoCredentialsError

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


_SERVICE_NAME = "support"
_VERSION = "1.0"
_USER_AGENT = f"support-assistant-beta-kit/{_VERSION} Python/{sys.version.split()[0]}"

# Wire-level logger for the Support Interactions / Cases API.
# In production (default), logs method/URL/status and body length only.
# Set LOG_LEVEL=DEBUG to get full request/response bodies for debugging.
_wire_logger = logging.getLogger("plx_support_assistant_client.wire")
_wire_logger.setLevel(logging.INFO)

_VERBOSE_LOGGING = os.environ.get("LOG_LEVEL", "").upper() == "DEBUG"

# FIX-009: Allowlist approach — only log headers known to be safe.
# All unknown/new headers are redacted by default (fail-closed).
_SAFE_HEADERS = {
    "content-type",
    "content-length",
    "user-agent",
    "accept",
    "host",
    "x-amzn-requestid",
}

# ── Retry configuration ───────────────────────────────────────────────────────
# Bounded exponential backoff for transient API errors.
# POST+500 is NOT retried (non-idempotent — could create duplicate interactions).
_MAX_RETRIES = 2
_BASE_DELAY = 1.0  # seconds
_RETRYABLE_ANY_METHOD = {429, 502, 503}
_RETRYABLE_GET_ONLY = {500}


def _redact_headers(headers: dict) -> dict:
    """Allowlist approach: only log known-safe headers, redact everything else."""
    out = {}
    for k, v in headers.items():
        if k.lower() in _SAFE_HEADERS:
            out[k] = v
        else:
            out[k] = "<redacted>"
    return out


def resolve_credentials(session: boto3.Session):
    """
    Resolve credentials from the boto3 session.
    Respects the full credential chain: env vars, ~/.aws/credentials,
    IAM instance profile, ECS task role, etc. — identical to the AWS CLI.
    """
    creds = session.get_credentials()
    if creds is None:
        raise NoCredentialsError()
    return creds.get_frozen_credentials()


def signed_request(
    method: str,
    url: str,
    region: str,
    credentials,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    content_type: str = "application/json",
) -> tuple[int, dict, dict]:
    """
    Build, sign, and fire an HTTP request using botocore's SigV4Auth.

    :param method: HTTP method (GET, POST, etc.)
    :param url: Full URL to call
    :param region: AWS region
    :param credentials: Frozen credentials from boto3 session
    :param body: Request body as dict (will be JSON-encoded)
    :param params: Query string parameters
    :param headers: Additional headers (e.g., X-Amz-Target for JSON-RPC APIs)
    :param content_type: Content-Type header (default: application/json)

    Returns (http_status, response_headers, response_body_dict).
    """
    if params:
        url += "?" + urlencode(params, doseq=True)

    payload = json.dumps(body).encode() if body else b""

    request_headers = {
        "Content-Type": content_type,
        "User-Agent": _USER_AGENT,
    }
    if headers:
        request_headers.update(headers)

    req = AWSRequest(
        method=method.upper(),
        url=url,
        data=payload,
        headers=request_headers,
    )
    SigV4Auth(credentials, _SERVICE_NAME, region).add_auth(req)
    prepared = req.prepare()

    # ── Wire log: outbound REQUEST ────────────────────────────────────────────
    # FIX-015: Only log full bodies when LOG_LEVEL=DEBUG. In production, log
    # method/URL/body_length for correlation without exposing sensitive content.
    try:
        if _VERBOSE_LOGGING:
            _wire_logger.info(
                "[SUPPORT-API REQUEST] method=%s url=%s headers=%s body=%s",
                prepared.method,
                prepared.url,
                json.dumps(_redact_headers(dict(prepared.headers))),
                payload.decode("utf-8") if payload else "",
            )
        else:
            _wire_logger.info(
                "[SUPPORT-API REQUEST] method=%s url=%s body_len=%d",
                prepared.method,
                prepared.url,
                len(payload),
            )
    except Exception as _log_exc:  # never let logging break the call
        _wire_logger.warning("[SUPPORT-API REQUEST] log emit failed: %s", _log_exc)

    # ── HTTP execution with bounded retry ─────────────────────────────────────
    # Retries on transient errors: 429/502/503 for all methods, 500 for GET only.
    # POST+500 is NOT retried (non-idempotent — architect advisory).
    is_get = method.upper() == "GET"
    retryable_codes = _RETRYABLE_ANY_METHOD | (_RETRYABLE_GET_ONLY if is_get else set())

    status = None
    resp_headers = {}
    resp_body = {}
    raw_response_text = ""

    for attempt in range(_MAX_RETRIES + 1):
        if _HAS_REQUESTS:
            resp = _requests.request(
                method=prepared.method,
                url=prepared.url,
                headers=dict(prepared.headers),
                data=prepared.body,
                timeout=30,
            )
            status = resp.status_code
            resp_headers = dict(resp.headers)
            raw_response_text = resp.text
            try:
                resp_body = resp.json()
            except Exception:
                resp_body = {"_raw": resp.text}
        else:
            from http.client import HTTPSConnection
            from urllib.parse import urlparse

            u = urlparse(prepared.url)
            path = u.path + (f"?{u.query}" if u.query else "")
            conn = HTTPSConnection(u.hostname, timeout=30)
            conn.request(
                prepared.method,
                path,
                headers=dict(prepared.headers),
                body=prepared.body or None,
            )
            r = conn.getresponse()
            status = r.status
            resp_headers = dict(r.getheaders())
            raw = r.read().decode("utf-8", errors="replace")
            raw_response_text = raw
            try:
                resp_body = json.loads(raw)
            except Exception:
                resp_body = {"_raw": raw}

        # Check if retryable
        if status not in retryable_codes or attempt == _MAX_RETRIES:
            break

        delay = _BASE_DELAY * (2 ** attempt)
        _wire_logger.info(
            "[RETRY] status=%d method=%s attempt=%d/%d delay=%.1fs",
            status, method.upper(), attempt + 1, _MAX_RETRIES, delay,
        )
        _time.sleep(delay)

    # ── Wire log: inbound RESPONSE ────────────────────────────────────────────
    # FIX-015: Only log full response bodies when LOG_LEVEL=DEBUG.
    try:
        if _VERBOSE_LOGGING:
            _wire_logger.info(
                "[SUPPORT-API RESPONSE] method=%s url=%s status=%d body=%s",
                prepared.method,
                prepared.url,
                status,
                raw_response_text,
            )
        else:
            _wire_logger.info(
                "[SUPPORT-API RESPONSE] method=%s url=%s status=%d body_len=%d",
                prepared.method,
                prepared.url,
                status,
                len(raw_response_text),
            )
    except Exception as _log_exc:
        _wire_logger.warning("[SUPPORT-API RESPONSE] log emit failed: %s", _log_exc)

    return status, resp_headers, resp_body
