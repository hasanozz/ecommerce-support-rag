# RAG Retrieval Benchmark Adapter Report

Tarih: 2026-06-26

## Kapsam

A?ama 2.2 ile uretilen 183 soruluk benchmark JSONL dosyasi, mevcut `backend/scripts/retrieval_benchmark.py` scriptinin bekledigi minimum case alanlarina donusturuldu. Orijinal benchmark dosyasi, RAG JSON, chunk dosyasi ve kod degistirilmedi. DB, ingest, embedding, benchmark, test, git ve pip islemleri calistirilmadi.

## retrieval_benchmark.py Beklenen Input Formati

Script yolu:

```text
backend/scripts/retrieval_benchmark.py
```

Koddan cikarilan beklenti:

- Sabit fixture path: `backend/tests/fixtures/retrieval_benchmark.json`
- Fixture formati: JSON array
- Her case icin zorunlu alanlar:
  - `query`
  - `expected_doc_id`
- Fixture'da `expected_category` bulunuyor ama mevcut script bu alani metrik hesaplamada kullanmiyor.

Script metrikleri:

- Top1
- Top3
- MRR
- best_score
- Top3 disi failures

## Adapter Formati

Adapter dosyasi:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\output\rag_benchmark\rag_retrieval_benchmark_adapter.jsonl
```

Adapter JSONL alanlari:

- `query`: kaynak `question`
- `expected_doc_id`: kaynak `expected_doc_id`
- `expected_category`: kaynak `expected_category`

Not:

- Kullanici istegi uzerine adapter dosyasi JSONL olarak olusturuldu.
- Mevcut script ise sabit JSON array fixture okuyor. Bu nedenle adapter JSONL dosyasi dogrudan script tarafindan okunamaz; calistirma oncesi ya JSON array fixture uretilmeli/kopyalanmali ya da script CLI/input destegiyle genisletilmelidir.

## Labels JSON Icerigi

Labels dosyasi:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\output\rag_benchmark\rag_retrieval_benchmark_labels.json
```

Labels JSON, adapter sirasiyla birebir eslesen `labels` listesi icerir. Korunan alanlar:

- `case_id`
- `query`
- `expected_doc_id`
- `expected_category`
- `expected_subcategory`
- `question_type`
- `confusable_with`
- `notes`

## Sayimlar

| Metrik | Deger |
| --- | ---: |
| Kaynak soru sayisi | 183 |
| Adapter satir sayisi | 183 |
| Labels case sayisi | 183 |
| Kaynak JSONL parse hatasi | 0 |
| Adapter JSONL parse hatasi | 0 |

## Validation Sonuclari

| Kontrol | Sonuc |
| --- | ---: |
| expected_doc_id invalid | 0 |
| Duplicate normalized question | 0 |
| Same question different expected_doc_id conflict | 0 |
| Kaynak 183 soru adapter'da ayni sirayla korundu mu | Evet |
| Metadata kaybi | 0 |
| expected_category mismatch | 0 |
| expected_subcategory mismatch | 0 |

## Korunan Alanlar

Adapter icinde korunan minimum script alanlari:

- `question` -> `query`
- `expected_doc_id`
- `expected_category`

Labels JSON icinde korunan ek alanlar:

- `expected_subcategory`
- `question_type`
- `confusable_with`
- `notes`

Metadata kaybi:

```text
Yok
```

## Benchmark Calistirmak Icin Onerilen Komut

Bu asamada calistirilmadi.

Mevcut script hic degistirilmeden calistirilirse sabit eski fixture'i okur:

```powershell
python -m backend.scripts.retrieval_benchmark
```

Bu adapter'i kullanmak icin sonraki asamada iki yoldan biri gerekir:

1. JSONL adapter'dan scriptin bekledigi JSON array fixture olusturmak ve `backend/tests/fixtures/retrieval_benchmark.json` yerine gecici olarak bunu kullanmak.
2. `retrieval_benchmark.py` icin CLI `--fixture` ve JSONL okuma destegi eklemek.

Onerilen sonraki hedef format:

```json
[
  {"query": "...", "expected_doc_id": "...", "expected_category": "..."}
]
```

## Genel Karar

WARNING

Gerekce:

- Adapter JSONL parse edilebilir ve 183 satirdir.
- expected_doc_id invalid yok.
- Duplicate/conflict yok.
- Kaynak sorular ayni sirayla korunmustur.
- Ek metadata `labels.json` icinde kayipsiz korunmustur.
- Ancak mevcut `retrieval_benchmark.py` sabit JSON array fixture okudugu icin JSONL adapter dosyasi tek basina dogrudan calistirma uyumu saglamaz.
