from pathlib import Path

from backend.app.rag.chunking import (
    SYSTEM_LAYER_FIELDS,
    document_to_chunks,
    load_final_rag_sources,
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
    chunks_path = Path("rag_chunks/rag_chunks_clean.jsonl")
    chunks = load_final_rag_sources(Path("rag_documents_final"), chunks_path)[1]

    assert len(documents) == 61
    assert len(chunks) == 366
    assert all(document["id"] == document["doc_id"] for document in documents)
    assert len({document["id"] for document in documents}) == len(documents)
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert {chunk["doc_id"] for chunk in chunks} == {
        document["id"] for document in documents
    }
    assert all("contextual_content" in chunk for chunk in chunks)
    assert all("metadata" not in chunk for chunk in chunks)
    assert all("standart_yanit" not in chunk["contextual_content"] for chunk in chunks)


def test_final_rag_references_are_valid():
    documents = load_final_documents(Path("rag_documents_final"))
    document_ids = {document["id"] for document in documents}

    for document in documents:
        assert set(document["related_documents"]).issubset(document_ids)
        assert set(document["hard_negative_doc_ids"]).issubset(document_ids)


def test_system_layer_fields_do_not_leak_to_chunk_text():
    chunks = load_final_rag_sources(
        Path("rag_documents_final"), Path("rag_chunks/rag_chunks_clean.jsonl")
    )[1]

    for chunk in chunks:
        combined = f"{chunk['content']}\n{chunk['contextual_content']}"
        assert all(field not in combined for field in SYSTEM_LAYER_FIELDS)
        assert "SAFE_FINAL_WITH_OPEN_POLICY_NOTES" not in combined
