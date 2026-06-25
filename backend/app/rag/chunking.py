from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SECTION_LABELS = {
    "amac": "Amaç",
    "amac_tanim": "Amaç ve Tanım",
    "kapsam": "Kapsam",
    "tanim": "Tanım",
    "genel_bilgiler": "Genel Bilgiler",
    "kullanici_ifadeleri": "Kullanıcı İfadeleri",
    "kosullar": "Koşullar",
    "adimlar": "Adımlar",
    "istisnalar": "İstisnalar",
    "destek_gerektiren_durumlar": "Destek Gerektiren Durumlar",
    "surec": "Süreç",
    "standart_yanit": "Standart Yanıt",
    "sik_yapilan_hatalar": "Sık Yapılan Hatalar",
}
CATEGORY_LABELS = {
    "SIPARIS": "Sipariş",
    "IADE": "İade",
    "ODEME": "Ödemeler",
    "KARGO_TESLIMAT": "Kargo / Teslimat",
    "HESAP_GUVENLIK": "Hesap ve Kullanıcı Güvenliği",
    "KAMPANYA_PUAN": "Kampanya ve Puan",
}
FIELD_LABELS = {
    "title": "Başlık",
    "category": "Kategori",
    "subcategory": "Alt Kategori",
}
SECTION_ORDER = list(SECTION_LABELS)
SEARCH_FIELDS = [
    "title",
    "category",
    "subcategory",
    "amac",
    "kapsam",
    "tanim",
    "kullanici_ifadeleri",
    "kosullar",
    "adimlar",
    "istisnalar",
    "destek_gerektiren_durumlar",
    "standart_yanit",
    "sik_yapilan_hatalar",
]
ANSWER_FIELDS = [
    "tanim",
    "kosullar",
    "adimlar",
    "istisnalar",
    "destek_gerektiren_durumlar",
    "standart_yanit",
]
SYSTEM_LAYER_FIELDS = {
    "hard_negative_doc_ids",
    "related_documents",
    "expected_action",
    "priority",
    "review_notes",
}
REQUIRED_FINAL_FIELDS = {
    "doc_id",
    "category",
    "subcategory",
    "title",
    "amac",
    "kapsam",
    "tanim",
    "kullanici_ifadeleri",
    "kosullar",
    "adimlar",
    "istisnalar",
    "destek_gerektiren_durumlar",
    "standart_yanit",
    "sik_yapilan_hatalar",
    "hard_negative_doc_ids",
    "related_documents",
    "expected_action",
    "priority",
    "review_notes",
}
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


def _field_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(
            f"- {normalize_text(str(item))}" for item in value if str(item).strip()
        )
    if isinstance(value, str):
        return normalize_text(value)
    return normalize_text(str(value)) if value is not None else ""


def build_search_text(document: dict) -> str:
    parts = []
    category = CATEGORY_LABELS.get(document["category"], document["category"])
    for field in SEARCH_FIELDS:
        value = category if field == "category" else document.get(field)
        text = _field_text(value)
        if text:
            label = FIELD_LABELS.get(
                field, SECTION_LABELS.get(field, field.replace("_", " ").title())
            )
            parts.append(f"{label}: {text}")
    return "\n\n".join(parts)


def build_answer_section(document: dict, section: str, content: str) -> str:
    label = SECTION_LABELS.get(section, section.replace("_", " ").title())
    return f"{label}:\n{content}"


def build_clean_chunk_context(chunk: dict) -> str:
    category = CATEGORY_LABELS.get(chunk["category"], chunk["category"])
    section_label = SECTION_LABELS.get(
        chunk["section"], str(chunk["section"]).replace("_", " ").title()
    )
    return (
        f"Doküman: {chunk['title']}\n"
        f"Kategori: {category}\n"
        f"Alt kategori: {chunk['subcategory']}\n"
        f"Bölüm: {section_label}\n\n"
        f"İçerik:\n{chunk['content']}"
    )


def normalize_final_document(document: dict, source_name: str = "") -> dict:
    missing = REQUIRED_FINAL_FIELDS.difference(document)
    if missing:
        prefix = f"{source_name}: " if source_name else ""
        raise ValueError(
            prefix + "eksik RAG doküman alanları: " + ", ".join(sorted(missing))
        )
    normalized = dict(document)
    normalized["id"] = str(normalized["doc_id"]).strip()
    if not normalized["id"]:
        raise ValueError(f"{source_name}: doc_id boş olamaz.")
    for field in (
        "kullanici_ifadeleri",
        "kosullar",
        "adimlar",
        "istisnalar",
        "destek_gerektiren_durumlar",
        "sik_yapilan_hatalar",
        "hard_negative_doc_ids",
        "related_documents",
        "review_notes",
    ):
        if not isinstance(normalized.get(field), list):
            raise ValueError(f"{source_name}: {field} liste olmalıdır.")
    return normalized


def document_to_chunks(document: dict) -> list[dict]:
    if "id" not in document and "doc_id" in document:
        document = dict(document)
        document["id"] = document["doc_id"]
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


def final_document_to_chunks(document: dict) -> list[dict]:
    search_text = build_search_text(document)
    chunks = []
    for section in ANSWER_FIELDS:
        content = section_content(document.get(section))
        if not content:
            continue
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
                    "content": build_answer_section(document, section, part),
                    "contextual_content": search_text,
                }
            )
    return chunks


def load_documents(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_final_documents(directory: Path) -> list[dict]:
    if not directory.exists():
        raise FileNotFoundError(f"RAG doküman klasörü bulunamadı: {directory}")
    documents: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise ValueError(f"RAG doküman dosyası liste veya obje olmalı: {path}")
        for item in data:
            if not isinstance(item, dict):
                raise ValueError(f"RAG dokümanı obje olmalı: {path}")
            documents.append(normalize_final_document(item, str(path)))
    ids = [item.get("id") for item in documents]
    duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
    if duplicate_ids:
        raise ValueError("Tekrarlı RAG doküman id değerleri: " + ", ".join(duplicate_ids))
    document_ids = set(ids)
    for document in documents:
        for field in ("related_documents", "hard_negative_doc_ids"):
            unknown = sorted(set(document[field]).difference(document_ids))
            if unknown:
                raise ValueError(
                    f"{document['id']} bilinmeyen {field} referansları: "
                    + ", ".join(unknown)
                )
    return documents


def load_clean_chunks(path: Path, documents: list[dict]) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"RAG chunk dosyası bulunamadı: {path}")
    document_ids = {item.get("id") or item["doc_id"] for item in documents}
    required_fields = {
        "chunk_id",
        "doc_id",
        "category",
        "subcategory",
        "title",
        "section",
        "content",
    }
    chunks: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        missing = required_fields.difference(item)
        if missing:
            raise ValueError(
                f"{path}:{line_number} eksik chunk alanları: "
                + ", ".join(sorted(missing))
            )
        if item["doc_id"] not in document_ids:
            raise ValueError(
                f"{path}:{line_number} bilinmeyen doc_id: {item['doc_id']}"
            )
        content = normalize_text(str(item["content"]))
        if not content:
            raise ValueError(f"{path}:{line_number} boş chunk content")
        chunk = {
            "chunk_id": item["chunk_id"],
            "doc_id": item["doc_id"],
            "category": item["category"],
            "subcategory": item["subcategory"],
            "title": item["title"],
            "section": item["section"],
            "content": content,
        }
        chunk["contextual_content"] = build_clean_chunk_context(chunk)
        chunks.append(chunk)
    chunk_ids = [item["chunk_id"] for item in chunks]
    duplicate_chunk_ids = sorted({item for item in chunk_ids if chunk_ids.count(item) > 1})
    if duplicate_chunk_ids:
        raise ValueError(
            "Tekrarlı RAG chunk_id değerleri: " + ", ".join(duplicate_chunk_ids)
        )
    return chunks


def load_final_rag_sources(documents_directory: Path, chunks_path: Path) -> tuple[list[dict], list[dict]]:
    del chunks_path  # Legacy clean chunk files are no longer authoritative.
    documents = load_final_documents(documents_directory)
    chunks = [
        chunk
        for document in documents
        for chunk in final_document_to_chunks(document)
    ]
    chunk_ids = [item["chunk_id"] for item in chunks]
    duplicate_chunk_ids = sorted({item for item in chunk_ids if chunk_ids.count(item) > 1})
    if duplicate_chunk_ids:
        raise ValueError(
            "Tekrarlı RAG chunk_id değerleri: " + ", ".join(duplicate_chunk_ids)
        )
    standard_answers = {
        chunk["doc_id"]: chunk["content"]
        for chunk in chunks
        if chunk["section"] == "standart_yanit"
    }
    for document in documents:
        standard_answer = standard_answers.get(document["id"])
        if standard_answer and "?" in str(document.get("standart_yanit", "")):
            document["standart_yanit"] = standard_answer
    return documents, chunks


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
