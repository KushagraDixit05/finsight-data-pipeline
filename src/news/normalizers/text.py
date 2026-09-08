"""
src/news/normalizers/text.py — HTML stripping and whitespace normalization.

These functions are the first two rules of the normalization pipeline
(06-normalization-validation.md, rules 4 & 5).  They run on title,
description, and content before any other normalization step.
"""

from __future__ import annotations

import re

import bleach


def strip_html(text: str | None) -> str | None:
    """
    Remove all HTML tags from text using bleach (safe, no regex hacks).

    Returns None for None or empty/whitespace-only input.

    bleach.clean with tags=[] strips every tag; strip=True removes the tag
    chars rather than escaping them so "&lt;b&gt;" becomes "".
    """
    if text is None:
        return None
    cleaned = bleach.clean(text, tags=[], attributes={}, strip=True)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def clean_whitespace(text: str | None) -> str | None:
    """
    Collapse runs of whitespace (spaces, tabs, newlines) into a single space
    and strip leading/trailing whitespace.

    Returns None for None or whitespace-only input.
    """
    if text is None:
        return None
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed if collapsed else None


def clean_text(text: str | None) -> str | None:
    """
    Convenience: strip_html then clean_whitespace in one call.

    Applied to title, description, and content by the normalization pipeline.
    """
    return clean_whitespace(strip_html(text))
