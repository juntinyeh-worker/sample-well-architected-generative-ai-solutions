"""HTML to plain text converter.

Strips HTML tags and converts structural elements (paragraphs, lists,
line breaks) to plain text equivalents. Uses Python's stdlib html.parser.

Used for ITSM platforms that send descriptions as HTML:
ServiceNow, Zendesk, Freshdesk, Freshservice.
"""

import html
import re
from html.parser import HTMLParser
from typing import Any


def html_to_text(html_str: str) -> str:
    """Convert HTML string to plain text.

    Preserves logical structure: paragraphs become double newlines,
    list items get bullet prefixes, links show URL in parentheses.

    Args:
        html_str: HTML-formatted string.

    Returns:
        Plain text with structure preserved.
    """
    if not html_str or not isinstance(html_str, str):
        return str(html_str) if html_str else ""

    parser = _HTMLToTextParser()
    parser.feed(html_str)
    result = parser.get_text()

    # Decode any remaining HTML entities
    result = html.unescape(result)

    # Collapse multiple blank lines into at most 2 newlines
    result = re.sub(r"\n{3,}", "\n\n", result)

    # Remove leading/trailing whitespace per line, then strip overall
    lines = [line.rstrip() for line in result.split("\n")]
    result = "\n".join(lines).strip()

    return result


class _HTMLToTextParser(HTMLParser):
    """Custom HTML parser that extracts text with structure."""

    # Block-level tags that should produce newlines
    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                  "blockquote", "pre", "section", "article", "header",
                  "footer", "main", "aside", "nav", "figure", "figcaption"}

    # Tags that produce line breaks
    BREAK_TAGS = {"br", "hr"}

    # Tags to skip entirely (don't extract text from these)
    SKIP_TAGS = {"script", "style", "head", "meta", "link", "title"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0
        self._in_list_item: bool = False
        self._in_anchor: bool = False
        self._anchor_href: str = ""
        self._anchor_text: str = ""
        self._in_pre: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()

        # Skip content inside script/style/head
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return

        if self._skip_depth > 0:
            return

        # Block-level elements: add newline before
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

        # Line breaks
        if tag in self.BREAK_TAGS:
            self._parts.append("\n")
            if tag == "hr":
                self._parts.append("---\n")

        # List items
        if tag == "li":
            self._parts.append("\n- ")
            self._in_list_item = True

        # Lists themselves get a newline
        if tag in ("ul", "ol"):
            self._parts.append("\n")

        # Table elements
        if tag == "tr":
            self._parts.append("\n")
        if tag in ("td", "th"):
            if self._parts and not self._parts[-1].endswith("\n"):
                self._parts.append(" | ")

        # Anchor tags — capture href for output
        if tag == "a":
            self._in_anchor = True
            self._anchor_text = ""
            attrs_dict = dict(attrs)
            self._anchor_href = attrs_dict.get("href", "")

        # Pre/code blocks
        if tag == "pre":
            self._in_pre = True
            self._parts.append("\n")

        # Images — extract alt text
        if tag == "img":
            attrs_dict = dict(attrs)
            alt = attrs_dict.get("alt", "")
            if alt:
                self._parts.append(alt)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag in self.SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return

        if self._skip_depth > 0:
            return

        # Block-level elements: add newline after
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

        # End of list item
        if tag == "li":
            self._in_list_item = False

        # End of anchor — output text + URL
        if tag == "a":
            self._in_anchor = False
            if self._anchor_href and self._anchor_text:
                self._parts.append(f"{self._anchor_text} ({self._anchor_href})")
            elif self._anchor_text:
                self._parts.append(self._anchor_text)
            elif self._anchor_href:
                self._parts.append(self._anchor_href)
            self._anchor_href = ""
            self._anchor_text = ""

        # End of pre block
        if tag == "pre":
            self._in_pre = False
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return

        # If inside an anchor, capture text separately
        if self._in_anchor:
            self._anchor_text += data
            return

        # In pre blocks, preserve whitespace
        if self._in_pre:
            self._parts.append(data)
            return

        # Normal text: collapse whitespace (unless in pre)
        text = re.sub(r"[ \t]+", " ", data)
        if text:
            self._parts.append(text)

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        char = html.unescape(f"&{name};")
        if self._in_anchor:
            self._anchor_text += char
        else:
            self._parts.append(char)

    def handle_charref(self, name: str) -> None:
        if self._skip_depth > 0:
            return
        char = html.unescape(f"&#{name};")
        if self._in_anchor:
            self._anchor_text += char
        else:
            self._parts.append(char)

    def get_text(self) -> str:
        """Return the accumulated plain text."""
        return "".join(self._parts)
