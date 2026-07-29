"""Text sanitizer for the Support Interactions API.

Detects the format of incoming message content and converts it to clean
plain text before sending to the API. Supports:
- ADF (Atlassian Document Format) — dict or stringified JSON
- HTML — tag-based markup from ServiceNow, Zendesk, Freshdesk
- Markdown — from GitHub, GitLab, Linear
- Jira Wiki Markup — from Jira Server/Data Center
- Plain text — passed through unchanged

This module uses Python standard library only (no third-party dependencies).
"""

import json
import re
from typing import Any

from .converters import adf_to_text, html_to_text, markdown_to_text, wiki_to_text

# Detection patterns
_HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z][^>]*>", re.DOTALL)
_WIKI_HEADING_PATTERN = re.compile(r"^h[1-6]\.\s", re.MULTILINE)
_WIKI_MACRO_PATTERN = re.compile(r"\{(noformat|code|quote|color|panel)")
_MARKDOWN_HEADER_PATTERN = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MARKDOWN_BOLD_PATTERN = re.compile(r"\*\*[^*]+\*\*")
_ADF_JSON_PREFIX = re.compile(r'^\s*\{\s*"type"\s*:\s*"doc"')


def sanitize_message(message: Any) -> str:
    """Convert any message format to clean plain text.

    This is the single entry point for text sanitization. It detects the
    format of the input and dispatches to the appropriate converter.

    Args:
        message: Input in any format — str, dict, or other.

    Returns:
        Clean plain text string suitable for the Support Interactions API.
        On any error, returns str(message) as a safe fallback.
    """
    try:
        return _detect_and_convert(message)
    except Exception:
        # Graceful degradation: if anything fails, return string representation
        return str(message) if message is not None else ""


def _detect_and_convert(message: Any) -> str:
    """Detect format and dispatch to the appropriate converter."""

    # Case 1: None or empty
    if message is None:
        return ""

    # Case 2: Dict — likely ADF
    if isinstance(message, dict):
        if message.get("type") == "doc":
            return adf_to_text(message)
        # Unknown dict structure — stringify it
        return str(message)

    # Case 3: Not a string — convert to string
    if not isinstance(message, str):
        return str(message)

    # Case 4: Empty string
    if not message.strip():
        return message

    # Case 5: Stringified ADF JSON (starts with {"type":"doc" or {"type": "doc")
    if _ADF_JSON_PREFIX.match(message):
        try:
            parsed = json.loads(message)
            if isinstance(parsed, dict) and parsed.get("type") == "doc":
                return adf_to_text(parsed)
        except (json.JSONDecodeError, ValueError):
            pass  # Not valid JSON — fall through to other checks

    # Case 6: HTML (contains HTML tags)
    if _HTML_TAG_PATTERN.search(message):
        return html_to_text(message)

    # Case 7: Jira Wiki Markup (h1. headings or {noformat}/{code}/{quote} macros)
    if _WIKI_HEADING_PATTERN.search(message) or _WIKI_MACRO_PATTERN.search(message):
        return wiki_to_text(message)

    # Case 8: Markdown (# headers or **bold**)
    if _MARKDOWN_HEADER_PATTERN.search(message) or _MARKDOWN_BOLD_PATTERN.search(message):
        return markdown_to_text(message)

    # Case 9: Plain text — pass through unchanged
    return message
