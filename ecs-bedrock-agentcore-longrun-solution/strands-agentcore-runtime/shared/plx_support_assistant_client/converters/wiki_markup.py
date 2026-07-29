"""Jira Wiki Markup to plain text converter.

Strips Jira wiki notation (h3., {noformat}, *bold*, [links|url], etc.)
while preserving the text content and logical structure.

Used for Jira Server/Data Center which uses wiki markup instead of ADF.
Also handles wiki markup that may appear in Jira Cloud comment bodies
when sent via older integrations.

Reference: https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa?section=texteffects
"""

import re


def wiki_to_text(wiki_str: str) -> str:
    """Convert Jira wiki markup to plain text.

    Strips wiki notation markers while preserving text content
    and line structure.

    Args:
        wiki_str: Jira wiki markup string.

    Returns:
        Plain text with structure preserved.
    """
    if not wiki_str or not isinstance(wiki_str, str):
        return str(wiki_str) if wiki_str else ""

    result = wiki_str

    # Remove {noformat} blocks — keep content
    result = re.sub(r"\{noformat(?::.*?)?\}(.*?)\{noformat\}", r"\1", result, flags=re.DOTALL)

    # Remove {code} blocks — keep content
    result = re.sub(r"\{code(?::.*?)?\}(.*?)\{code\}", r"\1", result, flags=re.DOTALL)

    # Remove {quote} blocks — keep content
    result = re.sub(r"\{quote\}(.*?)\{quote\}", r"\1", result, flags=re.DOTALL)

    # Remove {panel} blocks — keep content
    result = re.sub(r"\{panel(?::.*?)?\}(.*?)\{panel\}", r"\1", result, flags=re.DOTALL)

    # Remove {color} markup — keep content
    result = re.sub(r"\{color(?::.*?)?\}(.*?)\{color\}", r"\1", result, flags=re.DOTALL)

    # Remove heading markers (h1. through h6.) — keep text
    result = re.sub(r"^h[1-6]\.\s+", "", result, flags=re.MULTILINE)

    # Remove bold *text* — keep text
    # Be careful: * at start of line is a list item, not bold
    result = re.sub(r"(?<!^)(?<!\n)\*([^*\n]+)\*", r"\1", result)

    # Remove italic _text_ — keep text
    result = re.sub(r"(?<!\s)_([^_\n]+)_(?!\s)", r"\1", result)

    # Remove strikethrough -text- — keep text
    result = re.sub(r"(?<!\s)-([^-\n]+)-(?!\s)", r"\1", result)

    # Remove underline +text+ — keep text
    result = re.sub(r"(?<!\s)\+([^+\n]+)\+(?!\s)", r"\1", result)

    # Remove superscript ^text^ — keep text
    result = re.sub(r"\^([^^]+)\^", r"\1", result)

    # Remove subscript ~text~ — keep text
    result = re.sub(r"~([^~]+)~", r"\1", result)

    # Remove monospace {{text}} — keep text
    result = re.sub(r"\{\{([^}]+)\}\}", r"\1", result)

    # Convert links [text|url] → text (url)
    result = re.sub(r"\[([^|^\]]+)\|([^\]]+)\]", r"\1 (\2)", result)

    # Convert bare links [url] → url
    result = re.sub(r"\[([^\]|]+)\]", r"\1", result)

    # Remove mention markup [~accountId:xxx] → empty
    result = re.sub(r"\[~accountId:[^\]]+\]", "", result, flags=re.IGNORECASE)

    # Convert user mentions [~username] → @username
    result = re.sub(r"\[~([^\]]+)\]", r"@\1", result)

    # Convert list items (* and #) to simple bullets
    # * item → - item
    # ** item → - item (nested)
    # # item → - item (ordered treated as unordered for plain text)
    result = re.sub(r"^[*#]+\s+", "- ", result, flags=re.MULTILINE)

    # Remove horizontal rule ----
    result = re.sub(r"^-{4,}\s*$", "---", result, flags=re.MULTILINE)

    # Remove image markup !image.png! or !image.png|width=100!
    result = re.sub(r"!([^|!\n]+)(?:\|[^!]*)?\!", r"[\1]", result)

    # Remove anchor markup {anchor:name}
    result = re.sub(r"\{anchor:[^}]+\}", "", result)

    # Remove table header markers ||
    result = re.sub(r"\|\|", " | ", result)

    # Clean up extra whitespace
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r" *\n *", "\n", result)

    # Collapse multiple blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
