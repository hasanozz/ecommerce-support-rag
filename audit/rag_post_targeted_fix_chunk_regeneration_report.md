# RAG Post Targeted Fix Chunk Regeneration Report

## Kapsam
A?ama 2.6B kapsam?nda `rag_documents_final/*.json` kaynaklar?ndan `rag_chunks/rag_chunks_clean.jsonl` yeniden ?retildi.

## Dosyalar
- Kaynak RAG klas?r?: `rag_documents_final`
- Backup dosyas?: `rag_chunks\rag_chunks_clean.backup_before_2_6b_targeted_fix.jsonl`
- Yeni chunk dosyas?: `rag_chunks\rag_chunks_clean.jsonl`

## Chunk ?retimi
- Kullan?lan fonksiyon: `backend.app.rag.chunking.load_final_rag_sources()`
- Chunk kayna??: `final_document_to_chunks()`
- Kod de?i?ikli?i: yap?lmad?

## Say?sal Do?rulama
- Source doc_id count: `61`
- Chunk count: `366`
- Unique chunk doc_id count: `61`
- 61 doc_id / 366 chunk: `PASS`
- Her doc_id 6 chunk: `PASS`
- Missing doc_id: `0`
- Extra doc_id: `0`
- Duplicate chunk_id: `0`

## Metadata Do?rulama
- doc_id/category/subcategory eksik alan: `0`
- Category mismatch: `0`
- Subcategory mismatch: `0`

## PUAN_KAZANMA_001 Contextual Content Kontrol?
- PUAN_KAZANMA_001 chunk say?s?: `6`
- Yeni kullan?c? ifadeleri contextual_content i?inde: `PASS`
- `sipariş puanı gelmedi`: `var`
- `siparişten puan yansımadı`: `var`
- `alışveriş puanı hesabıma eklenmedi`: `var`
- `kampanya puanı kazanamadım`: `var`
- `siparişimden kampanya puanı gelmedi`: `var`
- `puanım siparişten sonra hesabıma yatmadı`: `var`

## System Alan S?z?nt?s?
- Kontrol edilen alanlar: `hard_negative_doc_ids, related_documents, expected_action, priority, review_notes, internal_notes, hard_negative`
- S?z?nt? say?s?: `0`
- Sonu?: `PASS`

## Riskler
- Chunk dosyas? yenilendi; DB/ingest bu a?amada yasak oldu?u i?in aktif DB hen?z yeni chunk i?eriklerini kullanmaz.
- Retrieval etkisini ?l?mek i?in sonraki izinli a?amada ingest ve benchmark gerekir.

## Genel Karar
PASS

## Sonraki ?nerilen Ad?m
?zinli sonraki a?amada yeni chunk setini ingest edip retrieval benchmark tekrar ?al??t?r?lmal?.
