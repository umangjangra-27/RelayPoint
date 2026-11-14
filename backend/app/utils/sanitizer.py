"""Deterministic Secret Sanitization Utility.

Provides regex-based scrubbing of high-risk credentials, tokens, passwords,
private keys, and connection strings prior to persistence or AI processing.

SECURITY & ARCHITECTURAL LIMITATION:
Regex-based scanning provides deterministic protection against common and standard
secret formats, but cannot guarantee detection of every possible secret (such as
obfuscated, split, low-entropy custom passwords, or non-standard token formats).
It serves as an essential defense-in-depth sanitization layer, not an infallible
guarantee against all information leaks.
"""

from dataclasses import dataclass, field
import re
from typing import List, Pattern, Tuple

REDACTION_TOKEN = "[REDACTED]"

# Compiled regex patterns organized by category
SECRET_PATTERNS: List[Tuple[str, Pattern]] = [
    # 1. Private Keys (RSA, EC, OpenSSH, PGP, Generic)
    (
        "private_key",
        re.compile(
            r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----[\s\S]*?-----END\s+[A-Z\s]+PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
    ),
    # 2. GitHub Personal Access Tokens and App Tokens
    (
        "github_token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b"
            r"|\bgithub_pat_[A-Za-z0-9_]{50,120}\b",
        ),
    ),
    # 3. AWS Access Keys
    (
        "aws_key",
        re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
    ),
    # 4. Google Cloud / Gemini API Keys
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{30,45}\b"),
    ),
    # 5. OpenAI API Keys
    (
        "openai_api_key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    ),
    # 6. Slack Tokens
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    ),
    # 7. Bearer / Authorization Tokens
    (
        "bearer_token",
        re.compile(
            r"(?i)\b(Bearer\s+)[A-Za-z0-9\-._~+/=]{16,}\b",
        ),
    ),
    # 8. Database Connection URIs with credentials
    (
        "database_uri",
        re.compile(
            r"(?i)\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|sqlite)://[^:\s@/]+:)([^@\s/]+)(@[^\s/]+)",
        ),
    ),
    # 9. Password, Secret, and Key assignments in configs/code
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b((?:password|passwd|secret|api[_-]?key|client[_-]?secret|auth[_-]?token)"
            r"\s*[:=]\s*['\"]?)([^'\"\s,;\r\n]{4,})(['\"]?)",
        ),
    ),
]

# Email pattern (optional or standard)
EMAIL_PATTERN: Tuple[str, Pattern] = (
    "email_address",
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


@dataclass
class SanitizedReport:
    """Diagnostic report of sanitization actions."""
    sanitized_text: str
    redactions_count: int
    detected_categories: List[str] = field(default_factory=list)


def sanitize_text(text: str, redact_emails: bool = True) -> str:
    """Sanitize secrets from the given text string.
    
    Replaces detected secrets with [REDACTED] while preserving surrounding syntax context.
    
    Args:
        text: Input string (diff, commit message, code snippet, config file).
        redact_emails: When True, also replaces plain email addresses.
        
    Returns:
        Scrubbed string safe for logging, persistence, or AI prompts.
    """
    return sanitize_with_report(text, redact_emails=redact_emails).sanitized_text


def sanitize_with_report(text: str, redact_emails: bool = True) -> SanitizedReport:
    """Sanitize secrets and return detailed audit metrics without exposing sensitive values.
    
    Args:
        text: Input string.
        redact_emails: When True, also replaces plain email addresses.
        
    Returns:
        SanitizedReport with sanitized text, count of redactions, and detected categories.
    """
    if not text:
        return SanitizedReport(sanitized_text="", redactions_count=0, detected_categories=[])

    working_text = text
    total_redactions = 0
    categories_found = []

    # Process all primary secret patterns
    for category, pattern in SECRET_PATTERNS:
        match_count = 0

        if category == "bearer_token":
            # Preserve 'Bearer ' prefix, redact token payload
            def _replace_bearer(match: re.Match) -> str:
                nonlocal match_count
                match_count += 1
                return f"{match.group(1)}{REDACTION_TOKEN}"
            working_text = pattern.sub(_replace_bearer, working_text)

        elif category == "database_uri":
            # Preserve protocol and host, redact password
            def _replace_db_uri(match: re.Match) -> str:
                nonlocal match_count
                match_count += 1
                return f"{match.group(1)}{REDACTION_TOKEN}{match.group(3)}"
            working_text = pattern.sub(_replace_db_uri, working_text)

        elif category == "credential_assignment":
            # Preserve variable key and quotes, redact value
            def _replace_assignment(match: re.Match) -> str:
                nonlocal match_count
                match_count += 1
                return f"{match.group(1)}{REDACTION_TOKEN}{match.group(3)}"
            working_text = pattern.sub(_replace_assignment, working_text)

        else:
            # Full match redaction
            def _replace_full(match: re.Match) -> str:
                nonlocal match_count
                match_count += 1
                return REDACTION_TOKEN
            working_text = pattern.sub(_replace_full, working_text)

        if match_count > 0:
            total_redactions += match_count
            if category not in categories_found:
                categories_found.append(category)

    # Optional email redaction
    if redact_emails:
        email_category, email_pattern = EMAIL_PATTERN
        email_count = 0

        def _replace_email(match: re.Match) -> str:
            nonlocal email_count
            email_count += 1
            return REDACTION_TOKEN

        working_text = email_pattern.sub(_replace_email, working_text)
        if email_count > 0:
            total_redactions += email_count
            if email_category not in categories_found:
                categories_found.append(email_category)

    return SanitizedReport(
        sanitized_text=working_text,
        redactions_count=total_redactions,
        detected_categories=categories_found,
    )
