from pathlib import Path

from backend.app.rag.chunking import (
    document_to_chunks,
    load_clean_chunks,
    load_final_documents,
)


def test_empty_sections_are_not_chunked():
    document = {
        "id": "TEST_001",
        "category": "SIPARIS",
        "subcategory": "TEST",
        "title": "Test Dokümanı",
        "amac": "Bu bir amaç metnidir.",
        "kapsam": "",
        "tanim": "",
        "genel_bilgiler": "Anlamlı genel bilgi metni.",
        "kosullar": [],
        "adimlar": ["İlk adım.", "İkinci adım."],
        "istisnalar": [],
        "surec": "",
        "standart_yanit": "Kısa bir standart yanıt.",
    }
    chunks = document_to_chunks(document)
    sections = {chunk["section"] for chunk in chunks}
    assert "kapsam" not in sections
    assert "kosullar" not in sections
    assert "adimlar" in sections
    assert all("Kategori: Sipariş" in chunk["contextual_content"] for chunk in chunks)


def test_final_rag_sources_are_valid():
    documents = load_final_documents(Path("rag_documents_final"))
    chunks = load_clean_chunks(Path("rag_chunks/rag_chunks_clean.jsonl"), documents)

    assert len(documents) == 70
    assert len(chunks) == 411
    assert len({document["id"] for document in documents}) == len(documents)
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert {chunk["doc_id"] for chunk in chunks} == {
        document["id"] for document in documents
    }
    assert all("contextual_content" in chunk for chunk in chunks)
    assert all("metadata" not in chunk for chunk in chunks)
    assert all("İçerik:" in chunk["contextual_content"] for chunk in chunks)
