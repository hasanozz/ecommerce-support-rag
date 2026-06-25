from backend.app.services.retrieval import RetrievedChunk, group_chunks


def chunk(doc_id: str, section: str, content: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{doc_id}_{section}_{score}",
        doc_id=doc_id,
        title=f"Başlık {doc_id}",
        category="ODEME",
        subcategory=f"ALT_{doc_id}",
        section=section,
        content=content,
        contextual_content=content,
        score=score,
    )


def test_group_chunks_merges_by_document_and_limits_sections():
    chunks = [
        chunk("DOC_1", "tanim", "Tanım metni", 0.91),
        chunk("DOC_1", "kapsam", "Kapsam metni", 0.82),
        chunk("DOC_1", "kosullar", "Koşul metni", 0.79),
        chunk("DOC_1", "genel_bilgiler", "Genel bilgi", 0.74),
        chunk("DOC_1", "adimlar", "Adımlar", 0.70),
        chunk("DOC_1", "istisnalar", "İstisnalar", 0.68),
        chunk("DOC_1", "surec", "Süreç", 0.65),
        chunk("DOC_2", "tanim", "İkinci doküman", 0.88),
    ]
    grouped = group_chunks(chunks, max_documents=3, max_sections=6)
    assert [item.doc_id for item in grouped] == ["DOC_1", "DOC_2"]
    assert grouped[0].best_score == 0.91
    assert len(grouped[0].matched_sections) == 6
    assert "Doküman: Başlık DOC_1" in grouped[0].combined_context
    assert "Kategori: Ödemeler" in grouped[0].combined_context
    assert "Tanım:\nTanım metni" in grouped[0].combined_context


def test_group_chunks_supports_clean_rag_sections():
    grouped = group_chunks(
        [
            chunk("DOC_1", "sik_yapilan_hatalar", "Hata metni", 0.90),
            chunk("DOC_1", "amac_tanim", "Amaç ve tanım metni", 0.88),
        ],
        max_documents=1,
        max_sections=2,
    )

    assert grouped[0].matched_sections == ["amac_tanim", "sik_yapilan_hatalar"]
    assert "Amaç ve Tanım:\nAmaç ve tanım metni" in grouped[0].combined_context
    assert "Sık Yapılan Hatalar:\nHata metni" in grouped[0].combined_context


def test_group_chunks_uses_answer_content_not_embedding_context():
    item = chunk("DOC_1", "standart_yanit", "Temiz cevap metni", 0.90)
    item.contextual_content = (
        "review_notes: internal validation\n"
        "hard_negative_doc_ids: SHOULD_NOT_LEAK"
    )

    grouped = group_chunks([item], max_documents=1, max_sections=1)

    assert "Temiz cevap metni" in grouped[0].combined_context
    assert "review_notes" not in grouped[0].combined_context
    assert "hard_negative_doc_ids" not in grouped[0].combined_context
