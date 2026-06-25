from __future__ import annotations

import html
import re
import unicodedata

from fastapi import HTTPException, status

from ..config import Settings, get_settings


JAILBREAK_PATTERNS = [
    r"önceki talimatları unut",
    r"(tüm|bütün) (önceki )?talimatları (unut|yok say)",
    r"(kuralları|güvenlik kurallarını) (yok say|devre dışı bırak)",
    r"rolünü değiştir",
    r"şimdi sen .* ol",
    r"ignore (all )?previous instructions",
    r"disregard (all )?(previous|prior) instructions",
    r"reveal (the )?(system|developer) prompt",
    r"system prompt",
    r"developer message",
    r"admin mode",
    r"developer mode",
    r"jailbreak",
    r"prompt injection",
    r"api[\s_-]?key",
    r"gizli talimat",
]
ECOMMERCE_TERMS = {
    "sipariş",
    "ürün",
    "iade",
    "ödeme",
    "kart",
    "kargo",
    "teslimat",
    "hesap",
    "şifre",
    "e-posta",
    "telefon",
    "kupon",
    "puan",
    "kampanya",
    "fatura",
    "stok",
    "paket",
    "adres",
    "ücret",
}
OBVIOUSLY_OUT_OF_SCOPE = {
    "hava durumu",
    "futbol maçı",
    "borsa tahmini",
    "şiir yaz",
    "kod yaz",
    "matematik sorusu",
}


def sanitize_query(raw_query: str, settings: Settings | None = None) -> str:
    config = settings or get_settings()
    query = unicodedata.normalize("NFKC", html.unescape(raw_query or ""))
    query = "".join(
        character
        for character in query
        if character in "\n\t" or not unicodedata.category(character).startswith("C")
    )
    query = re.sub(
        r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>",
        " ",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    query = re.sub(r"<[^>]+>", " ", query)
    query = re.sub(r"\s+", " ", query).strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mesaj boş olamaz.",
        )
    if len(query) > config.max_query_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Mesaj en fazla {config.max_query_length} karakter olabilir.",
        )
    lowered = query.casefold()
    if any(re.search(pattern, lowered) for pattern in JAILBREAK_PATTERNS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mesaj güvenlik politikası nedeniyle işlenemedi.",
        )
    if any(phrase in lowered for phrase in OBVIOUSLY_OUT_OF_SCOPE) and not any(
        term in lowered for term in ECOMMERCE_TERMS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu asistan yalnızca e-ticaret müşteri destek konularını yanıtlar.",
        )
    return query
