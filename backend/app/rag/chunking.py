from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SECTION_LABELS = {
    "amac": "Amaç",
    "kapsam": "Kapsam",
    "tanim": "Tanım",
    "genel_bilgiler": "Genel Bilgiler",
    "kosullar": "Koşullar",
    "adimlar": "Adımlar",
    "istisnalar": "İstisnalar",
    "surec": "Süreç",
    "standart_yanit": "Standart Yanıt",
}
CATEGORY_LABELS = {
    "SIPARIS": "Sipariş",
    "IADE": "İade",
    "ODEME": "Ödemeler",
    "KARGO_TESLIMAT": "Kargo / Teslimat",
    "HESAP_GUVENLIK": "Hesap ve Kullanıcı Güvenliği",
    "KAMPANYA_PUAN": "Kampanya ve Puan",
}
SECTION_ORDER = list(SECTION_LABELS)
SHORT_TEXT_LIMIT = 90
MAX_CHUNK_CHARS = 1600


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def section_content(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {normalize_text(str(item))}" for item in value if str(item).strip())
    if isinstance(value, str):
        return normalize_text(value)
    return ""


def split_long_content(content: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    lines = content.splitlines()
    if len(lines) == 1:
        sentences = re.split(r"(?<=[.!?])\s+", content)
    else:
        sentences = lines
    parts: list[str] = []
    current: list[str] = []
    current_length = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        projected = current_length + len(sentence) + (1 if current else 0)
        if current and projected > max_chars:
            parts.append("\n".join(current))
            current = []
            current_length = 0
        current.append(sentence)
        current_length += len(sentence) + 1
    if current:
        parts.append("\n".join(current))
    return parts


def build_context(document: dict, section_label: str, content: str) -> str:
    category = CATEGORY_LABELS.get(document["category"], document["category"])
    return (
        f"Kategori: {category}\n"
        f"Alt kategori: {document['title']}\n"
        f"Doküman: {document['title']}\n"
        f"Bölüm: {section_label}\n\n"
        f"İçerik:\n{content}"
    )


def document_to_chunks(document: dict) -> list[dict]:
    raw_sections = []
    for section in SECTION_ORDER:
        content = section_content(document.get(section))
        if content:
            raw_sections.append([section, SECTION_LABELS[section], content])

    # Only merge adjacent, short prose sections. Lists and standard answers retain
    # their independent retrieval meaning.
    merged: list[tuple[str, str, str]] = []
    mergeable = {"amac", "kapsam", "tanim"}
    index = 0
    while index < len(raw_sections):
        section, label, content = raw_sections[index]
        if (
            section in mergeable
            and len(content) < SHORT_TEXT_LIMIT
            and index + 1 < len(raw_sections)
            and raw_sections[index + 1][0] in mergeable
        ):
            next_section, next_label, next_content = raw_sections[index + 1]
            merged.append(
                (
                    f"{section}_{next_section}",
                    f"{label} + {next_label}",
                    f"{label}: {content}\n{next_label}: {next_content}",
                )
            )
            index += 2
        else:
            merged.append((section, label, content))
            index += 1

    chunks = []
    for section, label, content in merged:
        parts = split_long_content(content)
        for part_index, part in enumerate(parts, start=1):
            suffix = f"_{part_index:02d}" if len(parts) > 1 else ""
            chunks.append(
                {
                    "chunk_id": f"{document['id']}__{section.upper()}{suffix}",
                    "doc_id": document["id"],
                    "category": document["category"],
                    "subcategory": document["subcategory"],
                    "title": document["title"],
                    "section": section,
                    "content": part,
                    "contextual_content": build_context(document, label, part),
                }
            )
    return chunks


def load_documents(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def create_chunks(input_path: Path, output_path: Path) -> list[dict]:
    documents = load_documents(input_path)
    chunks = [
        chunk
        for document in documents
        for chunk in document_to_chunks(document)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    return chunks
