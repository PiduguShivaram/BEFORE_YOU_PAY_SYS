"""Date parsing, normalization, and OCR grounding utilities for Before You Pay."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from before_you_pay.models import OcrLine

logger = logging.getLogger(__name__)

MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "sept": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_date_to_iso(s: Any, default_dmy: bool = True) -> str | None:
    """Normalize a raw date string to ISO format YYYY-MM-DD.

    Supports:
    - ISO format (YYYY-MM-DD, YYYY/MM/DD)
    - Delimited DMY/MDY format (DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY)
    - Named month format (11 June 2020, 11 Jun 2020, June 11, 2020)

    Returns:
        ISO formatted date string 'YYYY-MM-DD' or None if invalid/unparseable.
    """
    if not s:
        return None
    raw = str(s).strip()
    if raw.upper() in ["NULL", "NONE", "UNKNOWN", "N/A", ""]:
        return None

    # 1. ISO format: YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", raw)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if 1900 <= y <= 2100:
            try:
                return date(y, m, d).isoformat()
            except ValueError:
                pass

    # 2. Named month: e.g. "11 June 2020", "11-Jun-2020", "June 11, 2020"
    m_named = re.search(r"\b(\d{1,2})[-/\s]+([A-Za-z]+)[-/\s]+(\d{4})\b", raw)
    if m_named:
        d = int(m_named.group(1))
        m_str = m_named.group(2).lower()
        y = int(m_named.group(3))
        if m_str in MONTH_NAME_MAP and 1900 <= y <= 2100:
            try:
                return date(y, MONTH_NAME_MAP[m_str], d).isoformat()
            except ValueError:
                pass

    m_named_rev = re.search(r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b", raw)
    if m_named_rev:
        m_str = m_named_rev.group(1).lower()
        d = int(m_named_rev.group(2))
        y = int(m_named_rev.group(3))
        if m_str in MONTH_NAME_MAP and 1900 <= y <= 2100:
            try:
                return date(y, MONTH_NAME_MAP[m_str], d).isoformat()
            except ValueError:
                pass

    # 3. Delimited numeric: DD-MM-YYYY or MM-DD-YYYY
    m_dmy = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", raw)
    if m_dmy:
        p1, p2, y = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
        if 1900 <= y <= 2100:
            if p1 > 12:
                d, m = p1, p2
            elif p2 > 12:
                m, d = p1, p2
            elif default_dmy:
                d, m = p1, p2
            else:
                m, d = p1, p2
            try:
                return date(y, m, d).isoformat()
            except ValueError:
                pass

    return None


def extract_date_from_text(text: str, default_dmy: bool = True) -> str | None:
    """Extract and normalize a date string from free text."""
    if not text:
        return None
    return normalize_date_to_iso(text, default_dmy=default_dmy)


def verify_date_grounding(
    raw_date: Any,
    all_lines: list[OcrLine],
    field_type: str = "date",
    default_dmy: bool = True,
) -> tuple[str | None, OcrLine | None]:
    """Verify that an extracted date is strictly grounded in the OCR lines.

    Ensures:
    1. The candidate year exists in document OCR text (never invented/hallucinated).
    2. Identifies the specific physical OCR line containing the date and keyword.

    Returns:
        tuple[normalized_iso_date | None, matched_ocr_line | None]
    """
    if not raw_date:
        return None, None

    cand_iso = normalize_date_to_iso(raw_date, default_dmy=default_dmy)
    if not cand_iso:
        return None, None

    parts = cand_iso.split("-")
    y, m, d = parts[0], parts[1], parts[2]

    # Year MUST appear in document lines (rejects e.g. hallucinated 2028 when doc is 2020)
    year_present = any(y in line.text for line in all_lines)
    if not year_present:
        logger.warning(
            "Rejecting ungrounded date '%s': year %s does not appear in OCR lines.",
            raw_date,
            y,
        )
        return None, None

    # Priority keywords for matching specific line
    kw_due = ["due date", "payment due", "due on", "due by", "pay by", "due"]
    kw_issued = [
        "bill date",
        "invoice date",
        "issue date",
        "inv date",
        "date :",
        "bill",
        "invoice",
        "date",
    ]
    kws = kw_due if field_type == "due_date" else kw_issued

    best_line: OcrLine | None = None
    best_score = -1

    for line in all_lines:
        txt = line.text.lower()
        if field_type == "issued_date" and "due" in txt:
            continue
        if field_type == "due_date" and any(k in txt for k in ["bill date", "invoice date", "issue date", "inv date"]):
            continue

        score = 0
        if y in line.text:
            score += 1

            # Day and month match
            if (
                f"{d}-{m}" in line.text
                or f"{d}/{m}" in line.text
                or f"{d}.{m}" in line.text
                or f"{m}-{d}" in line.text
                or f"{m}/{d}" in line.text
            ):
                score += 3
            elif d in line.text and m in line.text:
                score += 2

            # Field keyword match
            if any(k in txt for k in kws):
                score += 5

            if score > best_score and score >= 4:
                best_score = score
                best_line = line

    if best_line:
        return cand_iso, best_line

    # Fallback to any line containing the year and day/month if specific keyword wasn't present
    for line in all_lines:
        txt = line.text.lower()
        if field_type == "issued_date" and "due" in txt:
            continue
        if field_type == "due_date" and any(k in txt for k in ["bill date", "invoice date", "issue date", "inv date"]):
            continue

        if y in line.text and (
            f"{d}-{m}" in line.text
            or f"{d}/{m}" in line.text
            or f"{m}-{d}" in line.text
            or f"{m}/{d}" in line.text
            or (d in line.text and m in line.text)
        ):
            return cand_iso, line

    return None, None


def fallback_extract_date(
    all_lines: list[OcrLine],
    field_type: str = "issued_date",
    default_dmy: bool = True,
) -> tuple[str | None, OcrLine | None]:
    """Deterministically scan OCR lines for explicit dates matching the field type."""
    kw_due = ["due date", "payment due", "due on", "due by", "pay by", "due :"]
    kw_issued = ["bill date", "invoice date", "issue date", "inv date", "date :"]
    kws = kw_due if field_type == "due_date" else kw_issued

    for line in all_lines:
        txt = line.text.lower()
        if field_type == "issued_date" and "due" in txt:
            continue
        if field_type == "due_date" and any(k in txt for k in ["bill date", "invoice date", "issue date", "inv date"]):
            continue

        if any(k in txt for k in kws):
            norm = extract_date_from_text(line.text, default_dmy=default_dmy)
            if norm:
                return norm, line

    # If issued_date and no explicit label found, check top lines for a standalone date
    if field_type == "issued_date":
        for line in all_lines[:15]:
            # Don't pick lines that explicitly state "due"
            if "due" not in line.text.lower():
                norm = extract_date_from_text(line.text, default_dmy=default_dmy)
                if norm:
                    return norm, line

    return None, None
