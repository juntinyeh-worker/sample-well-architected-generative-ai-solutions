"""ADF (Atlassian Document Format) to plain text converter.

Recursively walks the ADF JSON tree and extracts all text content,
preserving logical structure (paragraphs, headings, lists, code blocks).

ADF is used by Jira Cloud REST API v3 for rich text fields like
issue descriptions and comments.

Reference: https://developer.atlassian.com/cloud/jira/platform/apis/document/structure
"""

import re
from typing import Any


def adf_to_text(doc: dict[str, Any]) -> str:
    """Convert an ADF document to plain text.

    Args:
        doc: ADF document dict with {"type": "doc", "version": 1, "content": [...]}

    Returns:
        Plain text string with logical structure preserved.
    """
    if not isinstance(doc, dict):
        return str(doc)

    content = doc.get("content", [])
    if not content:
        return ""

    parts = []
    for node in content:
        text = _process_node(node)
        if text:
            parts.append(text)

    result = "\n".join(parts)
    # Collapse 3+ consecutive newlines into 2
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _process_node(node: dict[str, Any], list_prefix: str = "") -> str:
    """Process a single ADF node recursively.

    Args:
        node: ADF node dict
        list_prefix: Prefix for list items (e.g., "- " or "1. ")

    Returns:
        Plain text representation of the node.
    """
    if not isinstance(node, dict):
        return str(node) if node else ""

    node_type = node.get("type", "")
    content = node.get("content", [])
    attrs = node.get("attrs", {})

    # Inline nodes (leaf nodes with text content)
    if node_type == "text":
        return node.get("text", "")

    if node_type == "hardBreak":
        return "\n"

    if node_type == "mention":
        # Prefer display text, fall back to ID
        return f"@{attrs.get('text', attrs.get('id', ''))}"

    if node_type == "emoji":
        # Prefer text representation, fall back to shortName
        return attrs.get("text", attrs.get("shortName", ""))

    if node_type == "date":
        return attrs.get("timestamp", "")

    if node_type == "status":
        return f"[{attrs.get('text', '')}]"

    if node_type == "inlineCard":
        return attrs.get("url", "")

    # Block nodes
    if node_type == "paragraph":
        return _process_children(content)

    if node_type == "heading":
        return _process_children(content)

    if node_type == "blockquote":
        inner = _process_children_block(content)
        # Prefix each line with >
        lines = inner.split("\n")
        return "\n".join(f"> {line}" for line in lines)

    if node_type == "codeBlock":
        return _process_children(content)

    if node_type == "rule":
        return "---"

    if node_type == "bulletList":
        return _process_list(content, ordered=False)

    if node_type == "orderedList":
        return _process_list(content, ordered=True)

    if node_type == "listItem":
        # Process children as block content (may contain paragraphs, nested lists)
        parts = []
        for child in content:
            child_type = child.get("type", "")
            if child_type in ("bulletList", "orderedList"):
                # Nested list — indent
                nested = _process_node(child)
                indented = "\n".join(f"  {line}" for line in nested.split("\n") if line)
                parts.append(indented)
            else:
                text = _process_node(child)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    if node_type == "table":
        return _process_table(content)

    if node_type == "tableRow":
        cells = []
        for cell in content:
            cells.append(_process_children(cell.get("content", [])))
        return " | ".join(cells)

    if node_type in ("tableCell", "tableHeader"):
        return _process_children_block(content)

    if node_type in ("panel", "expand", "nestedExpand"):
        return _process_children_block(content)

    if node_type == "mediaGroup":
        # Media groups contain media nodes — extract filenames if available
        parts = []
        for child in content:
            if child.get("type") == "media":
                name = child.get("attrs", {}).get("alt", "")
                if not name:
                    name = child.get("attrs", {}).get("id", "[media]")
                parts.append(f"[{name}]")
        return " ".join(parts) if parts else ""

    if node_type == "mediaSingle":
        for child in content:
            if child.get("type") == "media":
                alt = child.get("attrs", {}).get("alt", "")
                return f"[{alt}]" if alt else ""
        return ""

    # Fallback: recurse into content if present
    if content:
        return _process_children_block(content)

    return ""


def _process_children(content: list[dict]) -> str:
    """Process inline children and join without newlines."""
    parts = []
    for child in content:
        text = _process_node(child)
        if text is not None:
            parts.append(text)
    return "".join(parts)


def _process_children_block(content: list[dict]) -> str:
    """Process block children and join with newlines."""
    parts = []
    for child in content:
        text = _process_node(child)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _process_list(items: list[dict], ordered: bool = False) -> str:
    """Process a list (bullet or ordered) into plain text."""
    lines = []
    for i, item in enumerate(items):
        prefix = f"{i + 1}. " if ordered else "- "
        item_text = _process_node(item)
        if item_text:
            # Apply prefix to first line only
            item_lines = item_text.split("\n")
            item_lines[0] = f"{prefix}{item_lines[0]}"
            lines.extend(item_lines)
    return "\n".join(lines)


def _process_table(rows: list[dict]) -> str:
    """Process a table into plain text with | separators."""
    lines = []
    for row in rows:
        if row.get("type") == "tableRow":
            cells = []
            for cell in row.get("content", []):
                cell_text = _process_children_block(cell.get("content", []))
                cells.append(cell_text.replace("\n", " "))
            lines.append(" | ".join(cells))
    return "\n".join(lines)
