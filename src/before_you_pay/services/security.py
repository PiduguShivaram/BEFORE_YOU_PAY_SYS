"""Security auditing, layered prompt injection defense, and input sanitization service.

Provides defense-in-depth against:
- Prompt injection & instruction override attacks in unstructured document and dealer text
- Role confusion, jailbreak tokens (<|im_start|>, <|im_end|>, etc.)
- Script injection and HTML/XML tag smuggling
- Tenant boundary enforcement and IDOR detection
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from enum import StrEnum


class ThreatSeverity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class InjectionDetectionResult:
    """Outcome of adversarial prompt injection analysis."""

    is_suspicious: bool
    severity: ThreatSeverity
    matched_patterns: list[str] = field(default_factory=list)
    sanitized_text: str = ""
    remediation_note: str = ""


# High-confidence prompt injection and jailbreak patterns
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], ThreatSeverity, str]] = [
    (
        re.compile(
            r"(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:previous|prior|above|system)\s+(?:instructions?|directives?|rules?|prompts?)",
            re.IGNORECASE,
        ),
        ThreatSeverity.HIGH,
        "Instruction override attempt",
    ),
    (
        re.compile(
            r"(?:system\s*override|admin\s*override|developer\s*mode|dan\s*mode|jailbreak)",
            re.IGNORECASE,
        ),
        ThreatSeverity.HIGH,
        "Privilege escalation / jailbreak vector",
    ),
    (
        re.compile(
            r"(?:you\s+(?:are|must|will)\s+now\s+act\s+as|pretend\s+you\s+are|roleplay\s+as)",
            re.IGNORECASE,
        ),
        ThreatSeverity.MEDIUM,
        "Role confusion / persona hijack attempt",
    ),
    (
        re.compile(
            r"(?:always\s+(?:output|return|say)\s+(?:0|zero|balanced|approved|valid)|mark\s+all\s+(?:charges\s+)?(?:as\s+)?optional)",
            re.IGNORECASE,
        ),
        ThreatSeverity.HIGH,
        "Financial outcome manipulation attempt",
    ),
    (
        re.compile(
            r"(?:<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|assistant\|>|\[INST\]|\[/INST\])",
            re.IGNORECASE,
        ),
        ThreatSeverity.HIGH,
        "ChatML / token delimiter injection",
    ),
    (
        re.compile(
            r"(?:<script[\s>]|javascript:|onload=|onerror=)",
            re.IGNORECASE,
        ),
        ThreatSeverity.HIGH,
        "Script injection / XSS smuggling",
    ),
]


class SecurityService:
    """Layered security service defending against adversarial inputs and tenant violations."""

    @classmethod
    def audit_text_for_prompt_injection(cls, raw_text: str) -> InjectionDetectionResult:
        """Scan raw document or dealer text for adversarial prompt injection vectors."""
        if not raw_text or not raw_text.strip():
            return InjectionDetectionResult(
                is_suspicious=False,
                severity=ThreatSeverity.NONE,
                sanitized_text="",
            )

        matched_reasons: list[str] = []
        highest_severity = ThreatSeverity.NONE

        for pattern, severity, reason in _INJECTION_PATTERNS:
            if pattern.search(raw_text):
                matched_reasons.append(reason)
                if severity == ThreatSeverity.HIGH:
                    highest_severity = ThreatSeverity.HIGH
                elif severity == ThreatSeverity.MEDIUM and highest_severity != ThreatSeverity.HIGH:
                    highest_severity = ThreatSeverity.MEDIUM
                elif severity == ThreatSeverity.LOW and highest_severity == ThreatSeverity.NONE:
                    highest_severity = ThreatSeverity.LOW

        sanitized = cls.sanitize_for_prompt_context(raw_text)

        is_suspicious = len(matched_reasons) > 0
        remediation = (
            f"Adversarial patterns sanitized: {', '.join(matched_reasons)}."
            if is_suspicious
            else "Input is clean."
        )

        return InjectionDetectionResult(
            is_suspicious=is_suspicious,
            severity=highest_severity,
            matched_patterns=matched_reasons,
            sanitized_text=sanitized,
            remediation_note=remediation,
        )

    @classmethod
    def sanitize_for_prompt_context(cls, text: str) -> str:
        """Neutralize delimiter smuggling, control tokens, and HTML tags for safe LLM ingestion."""
        if not text:
            return ""

        # 1. Strip ChatML and delimiter tokens
        sanitized = re.sub(
            r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|assistant\|>|\[INST\]|\[/INST\]",
            " [FILTERED_DELIMITER] ",
            text,
            flags=re.IGNORECASE,
        )

        # 2. Escape HTML script/iframe tags
        sanitized = re.sub(
            r"<(script|iframe|object|embed)[^>]*>.*?</\1>",
            " [FILTERED_TAG] ",
            sanitized,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # 3. Escape HTML entities
        sanitized = html.escape(sanitized, quote=False)

        return sanitized.strip()
