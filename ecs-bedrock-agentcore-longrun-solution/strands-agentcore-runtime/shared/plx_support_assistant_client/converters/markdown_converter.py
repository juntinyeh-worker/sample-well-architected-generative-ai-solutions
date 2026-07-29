"""Markdown to plain text converter.

Strips markdown syntax markers while preserving the text content and
logical structure (line breaks, bullet points, paragraphs).

Markdown is already mostly human-readable, so this is a light-touch
conversion. Used for ITSM platforms like GitHub Issues, GitLab, Linear.
"""

import re


def markdown_to_text(md_str: str) -> str:
    """Convert markdown-formatted string to plain text.

    Strips syntax markers (#, **, `, [](), etc.) while preserving
    the text content and line structure.

    Args:
        md_str: Markdown-formatted string.

    Returns:
        Plain text with structure preserved.
    """
    if not md_str or not isinstance(md_str, str):
        return str(md_str) if md_str else ""

    result = md_str

    # Remove code fences (``` ... ```) but keep content
    result = re.sub(r"```[^\n]*\n(.*?)```", r"\1", result, flags=re.DOTALL)

    # Remove inline code backticks but keep content
    result = re.sub(r"`([^`]+)`", r"\1", result)

    # Convert images ![alt](url) → alt
    result = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", result)

    # Convert links [text](url) → text (url)
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)

    # Remove reference-style link definitions [id]: url
    result = re.sub(r"^\[[^\]]+\]:\s+\S+.*$", "", result, flags=re.MULTILINE)

    # Remove heading markers (# ## ### etc.) but keep text
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Remove bold markers **text** or __text__
    result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
    result = re.sub(r"__([^_]+)__", r"\1", result)

    # Remove italic markers *text* or _text_ (careful not to match list items)
    # Only match when surrounded by non-space characters
    result = re.sub(r"(?<!\s)\*([^*\n]+)\*(?!\s)", r"\1", result)
    result = re.sub(r"(?<!\s)_([^_\n]+)_(?!\s)", r"\1", result)

    # Remove strikethrough ~~text~~
    result = re.sub(r"~~([^~]+)~~", r"\1", result)

    # Remove horizontal rules (---, ***, ___)
    result = re.sub(r"^[-*_]{3,}\s*$", "---", result, flags=re.MULTILINE)

    # Remove blockquote markers > but keep text
    result = re.sub(r"^>\s?", "", result, flags=re.MULTILINE)

    # Keep list items as-is (- item, * item, 1. item are already readable)
    # Just normalize * bullets to - bullets for consistency
    result = re.sub(r"^\*\s+", "- ", result, flags=re.MULTILINE)

    # Remove HTML comments <!-- ... -->
    result = re.sub(r"<!--.*?-->", "", result, flags=re.DOTALL)

    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
