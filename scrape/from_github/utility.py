"""
Text helpers for GitHub Markdown export (standalone; mirrors cloud_rag preprocessor behavior).
"""

from __future__ import annotations

import re


def clean_text(text: str, remove_extra_spaces: bool = True) -> str:
    """
    Clean and normalize text content.

    Args:
        text: Input text to clean
        remove_extra_spaces: Whether to remove extra whitespace

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    from html import unescape

    text = unescape(text)

    text = (
        text.replace("\xad", "")
        .replace("\u200b", "")
        .replace("\u200c", "")
        .replace("\u200d", "")
        .replace("\xa0", " ")
        .replace("\u2002", " ")
        .replace("\u2003", " ")
        .replace("\u2026", "...")
        .replace("\u202f", " ")
    )

    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)

    if remove_extra_spaces:
        text = re.sub(r" +", " ", text)
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.strip() for line in text.split("\n"))

    return text.strip()


def validate_content_length(content: str, min_length: int = 50) -> bool:
    """
    Return True if stripped content length is at least min_length.
    """
    if not content:
        return False
    cleaned = content.strip()
    return len(cleaned) >= min_length
