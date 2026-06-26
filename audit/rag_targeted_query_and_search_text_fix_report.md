# RAG Targeted Query and Search Text Fix Report

## Kapsam
A?ama 2.6A kapsam?nda sadece hedefli iki veri d?zeltmesi yap?ld?: bir benchmark query g?ncellendi ve `PUAN_KAZANMA_001` kullan?c? ifadeleri g??lendirildi.

## Benchmark Query G?ncellemesi
- Eski query: `Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum.`
- Yeni query: `Kupon kodu girmeden, sepetteki kampanyanın hangi ürünlere uygulandığını öğrenmek istiyorum.`

| Dosya | De?i?en kay?t say?s? |
|---|---:|
| `output/rag_benchmark/rag_retrieval_benchmark_questions.jsonl` | 1 |
| `output/rag_benchmark/rag_retrieval_benchmark_adapter.jsonl` | 1 |
| `output/rag_benchmark/rag_retrieval_benchmark_labels.json` | 1 |
| `backend/tests/fixtures/retrieval_benchmark.json` | 1 |

## PUAN_KAZANMA_001 Kullan?c? ?fadeleri
- G?ncellenen dosya: `rag_documents_final/kampanya_puan_final_safe.json`
- Eklenen ifade say?s?: `6`
- sipariş puanı gelmedi
- siparişten puan yansımadı
- alışveriş puanı hesabıma eklenmedi
- kampanya puanı kazanamadım
- siparişimden kampanya puanı gelmedi
- puanım siparişten sonra hesabıma yatmadı

## Do?rulama
- JSON/JSONL parse: `PASS`
- Eski query kalan kay?t: `0`
- Yeni query kay?tlar?: questions `1`, adapter `1`, labels `1`, fixture `1`
- Duplicate query: `PASS`
- Same query different expected_doc_id conflict: `PASS`
- RAG doc_id count: `61`
- Duplicate doc_id: `PASS`
- PUAN_KAZANMA_001 eksik yeni ifade: `0`
- Unicode replacement karakteri: `0`

## Riskler
- `rag_documents_final/kampanya_puan_final_safe.json` de?i?ti; chunk regenerate bu a?amada ?zellikle yasak oldu?u i?in mevcut DB/chunk seti bu yeni kullan?c? ifadelerini hen?z yans?tmaz.
- Bu de?i?iklikten sonra retrieval etkisini ?l?mek i?in ileride kontroll? chunk regenerate + ingest + benchmark gerekir.

## Genel Karar
PASS

## Sonraki ?nerilen Ad?m
Bu hedefli veri d?zeltmelerinden sonra izinli a?amada chunk regenerate, ingest ve benchmark tekrar ?al??t?r?larak `KAMPANYA_KULLANIMI_001` ve `PUAN_KAZANMA_001` etkisi ?l??lmelidir.
