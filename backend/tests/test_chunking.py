from pathlib import Path

from backend.app.rag.chunking import document_to_chunks, load_documents


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


def test_project_documents_create_unique_chunks():
    source = Path("data/processed/rag_documents.jsonl")
    documents = load_documents(source)
    chunks = [chunk for document in documents for chunk in document_to_chunks(document)]
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert {chunk["doc_id"] for chunk in chunks} == {
        document["id"] for document in documents
    }
