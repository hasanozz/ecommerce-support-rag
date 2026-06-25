from __future__ import annotations

import hashlib
import hmac
import re

from fastapi import Request

from ..config import Settings, get_settings


PII_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[E-POSTA]"),
    (re.compile(r"\b(?:\+?90\s?)?0?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b"), "[TELEFON]"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[KART/NUMARA]"),
    (re.compile(r"\b\d{11}\b"), "[KIMLIK/NUMARA]"),
]


def mask_pii(text: str) -> tuple[str, list[str]]:
    masked = text
    findings = []
    for pattern, replacement in PII_PATTERNS:
        if pattern.search(masked):
            findings.append(replacement.strip("[]"))
            masked = pattern.sub(replacement, masked)
    return masked, findings


def request_ip_hash(
    request: Request, settings: Settings | None = None
) -> str:
    config = settings or get_settings()
    ip = request.client.host if request.client else "unknown"
    return hmac.new(
        config.ip_hash_secret.get_secret_value().encode("utf-8"),
        ip.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
