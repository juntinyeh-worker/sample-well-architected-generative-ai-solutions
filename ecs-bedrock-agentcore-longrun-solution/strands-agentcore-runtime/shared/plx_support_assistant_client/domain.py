"""Single source of truth for the ``domain`` parameter on StartInteraction.

The PLX ``domain: "plx"`` flag is a **property of the destination account**, not of the
caller or the deployment. Every StartInteraction call site (Experience 1 web-chat,
Experience 2 investigation loop, Experience 3 MCP, and the coda-broker validation probe)
must resolve the domain through this one function so the decision can never drift.

Two regimes:

* **Brokered (multi-account):** a caller reaching into a destination account via the
  coda-broker assume-role path passes the broker's credential payload. The account's
  ``plx_domain`` toggle (stored on ``ConnectionProfile`` in the broker's DynamoDB table)
  wins. A payload that is missing the key entirely (broker/consumer version skew) defaults
  to ``"plx"`` — matching the broker model default — and emits a warning + metric so the
  skew is visible.

* **Single (deployment's own account):** the caller passes ``None`` and the deployment-wide
  ``PLX_DOMAIN_ENABLED`` env var (from the CFN ``PlxDomainEnabled`` param) decides. This
  reproduces the historical behavior byte-for-byte.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

PLX_DOMAIN = "plx"


def _env_domain() -> Optional[str]:
    """SINGLE-mode: the deployment's own account. Byte-for-byte the historical logic."""
    return PLX_DOMAIN if os.environ.get("PLX_DOMAIN_ENABLED") == "true" else None


def _emit_missing_metric(context: str) -> None:
    """Emit a CloudWatch EMF metric + structured warning when a brokered payload lacks the
    plx_domain key. Best-effort — never raises."""
    try:
        logger.warning(
            "[PLX_DOMAIN] brokered payload missing plx_domain key — defaulting to plx=on "
            "(possible broker/consumer version skew) context=%s",
            context,
        )
        # Embedded Metric Format: CloudWatch ingests this from the log stream, no API call.
        print(json.dumps({
            "_aws": {
                "CloudWatchMetrics": [{
                    "Namespace": "PlxSupportAssistant",
                    "Dimensions": [["Context"]],
                    "Metrics": [{"Name": "PlxDomainKeyMissing", "Unit": "Count"}],
                }],
            },
            "Context": context,
            "PlxDomainKeyMissing": 1,
        }))
    except Exception:  # pragma: no cover - observability must never break the call path
        pass


def resolve_domain(brokered_payload: Optional[dict], *, context: str = "unknown") -> Optional[str]:
    """Resolve the ``domain`` argument for StartInteraction.

    :param brokered_payload: The coda-broker credentials payload when reaching into a
        destination account (multi-account), or ``None`` for the deployment's own account
        (single-account / admin default).
    :param context: Short caller label for logs/metrics (e.g. ``"support-proxy"``,
        ``"mcp-server"``, ``"investigation-loop"``).
    :returns: ``"plx"`` or ``None``.

    Rules:
      * ``brokered_payload is None`` → SINGLE: follow ``PLX_DOMAIN_ENABLED``.
      * brokered, key present → follow the account toggle (``True`` → ``"plx"``, else ``None``).
      * brokered, key absent/None → default ``"plx"`` (matches broker model default) + warn/metric.
    """
    if brokered_payload is None:
        return _env_domain()

    value = brokered_payload.get("plx_domain") if isinstance(brokered_payload, dict) else None
    if value is None:
        # Present-but-None or key absent → version-skew safety: match the broker's True default.
        _emit_missing_metric(context)
        return PLX_DOMAIN
    return PLX_DOMAIN if value else None
