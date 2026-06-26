# RAG Retrieval Benchmark Fixture Report

Tarih: 2026-06-26

## Kapsam

`output/rag_benchmark/rag_retrieval_benchmark_adapter.jsonl` dosyasi, mevcut `backend/scripts/retrieval_benchmark.py` scriptinin sabit fixture olarak okuyacagi JSON array formatina donusturuldu. Kod, orijinal benchmark JSONL, adapter JSONL, labels JSON, RAG JSON ve chunk dosyalari degistirilmedi. DB, ingest, embedding, benchmark, test, git ve pip islemleri calistirilmadi.

## Backup Dosyasi

Mevcut fixture icin backup olusturuldu:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\backend\tests\fixtures\retrieval_benchmark.backup_before_61_final_safe.json
```

Backup var mi: Evet

## Yeni Fixture Dosyasi

Yeni fixture dosyasi:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\backend\tests\fixtures\retrieval_benchmark.json
```

Scriptin bekledigi JSON array formati:

```json
[
  {"query": "...", "expected_doc_id": "...", "expected_category": "..."}
]
```

## Case Sayisi

| Kontrol | Sonuc |
| --- | ---: |
| Adapter satir sayisi | 183 |
| Fixture case sayisi | 183 |
| Beklenen case sayisi | 183 |

## Alan Dogrulama Sonucu

| Kontrol | Sonuc |
| --- | --- |
| Fixture JSON parse | PASS |
| JSON array mi | Evet |
| Eksik `query` / `expected_doc_id` / `expected_category` | 0 |
| Adapter parse hatasi | 0 |
| Kaynak adapter ile sira ve icerik birebir korundu mu | Evet |

Parse hata detayi:

```text
Yok
```

## expected_doc_id Dogrulama Sonucu

| Kontrol | Sonuc |
| --- | ---: |
| expected_doc_id invalid | 0 |
| expected_category mismatch | 0 |

Invalid doc_id listesi:

```text
Yok
```

## Duplicate / Conflict Sonucu

| Kontrol | Sonuc |
| --- | ---: |
| Duplicate normalized query | 0 |
| Same query different expected_doc_id conflict | 0 |

Conflict listesi:

```text
Yok
```

## Retrieval Benchmark Calistirmak Icin Onerilen Komut

Bu asamada calistirilmadi. Hazirlik tamamlandiktan sonra, BGE-M3 env ve ingest tamam ise mevcut script su komutla yeni fixture'i okuyabilir:

```powershell
$env:EMBEDDING_PROVIDER="sentence_transformers"
$env:EMBEDDING_MODEL="BAAI/bge-m3"
$env:EMBEDDING_DIMENSION="1024"
$env:EMBEDDING_DEVICE="cpu"
python -m backend.scripts.retrieval_benchmark
```

Not: Benchmark calistirmadan once DB'nin yeni 61 doc_id / 366 chunk setiyle ingest edilmis olmasi gerekir.

## Genel Karar

PASS

Gerekce:

- Fixture JSON parse ediliyor.
- Fixture JSON array formatinda.
- Case sayisi 183.
- Zorunlu alanlar her case icin mevcut.
- expected_doc_id invalid yok.
- Duplicate/conflict yok.
- Adapter ile sira ve icerik birebir korundu.
