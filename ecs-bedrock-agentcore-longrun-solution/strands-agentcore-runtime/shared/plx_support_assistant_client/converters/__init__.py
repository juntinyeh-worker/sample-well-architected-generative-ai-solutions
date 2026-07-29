"""Format converters for text sanitization.

Each converter extracts plain text from a specific rich text format,
preserving logical structure (paragraphs, line breaks, bullet points).
"""

from .adf import adf_to_text
from .html_converter import html_to_text
from .markdown_converter import markdown_to_text
from .wiki_markup import wiki_to_text

__all__ = [
    "adf_to_text",
    "html_to_text",
    "markdown_to_text",
    "wiki_to_text",
]
