# RAG Retrieval Benchmark Readiness Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, 61 `final_safe` doc_id seti icin retrieval benchmark calistirmadan once ingest, embedding ve benchmark hazirlik durumunu statik olarak inceler.

Bu asamada DB islemi, ingest, embedding uretimi, retrieval benchmark, test, git, pip veya kod degisikligi yapilmadi.

## Ingest Script Yolu

Canonical ingest script:

```text
backend/scripts/ingest.py
```

Ingest script davranisi:

- `settings.rag_documents_final_path` kullanir.
- `settings.rag_chunks_clean_path` degiskenini okur fakat `load_final_rag_sources()` icinde legacy chunks path artik authoritative degildir.
- `load_final_rag_sources(documents_path, chunks_path)` final_safe dokumanlardan chunklari yeniden uretir.
- Embedding metni olarak `item["contextual_content"]` kullanir.
- DB'ye `Document` ve `Chunk` kayitlarini yazar.

Canonical kaynak path ayarlari:

```text
rag_documents_final_path = PROJECT_ROOT / "rag_documents_final"
rag_chunks_clean_path = PROJECT_ROOT / "rag_chunks" / "rag_chunks_clean.jsonl"
```

## DB Eski Chunk Temizligi

`backend/scripts/ingest.py` icinde:

```text
delete(Chunk)
delete(Document)
```

Sonuc:

- Ingest calistirildiginda eski `chunks` ve `documents` tablolari temizlenir.
- Eski 70 doc_id chunk setinin DB'de kalma riski, ingest basariyla tamamlanirsa dusuktur.
- `EmbeddingIngest` eski kayitlari silinmez; `is_active=False` yapilir ve yeni aktif ingest metadata kaydi eklenir.

Risk:

- Ingest calistirilmazsa DB'de eski 70 doc_id seti kalmis olabilir.
- Ingest yarida kalirsa DB transaksiyonu commit edilmeden kapanmali; yine de calistirma sonrasi `db_status.py` veya dogrudan count kontrolu onerilir.

## Embedding Modeli / Provider

Kod defaultlari:

```text
embedding_provider = "hashing"
embedding_model = "hashing-sha256-v1"
embedding_dimension = 1024
embedding_device = "cpu"
```

`.env.example` defaultlari da hashing provider gosteriyor:

```text
EMBEDDING_PROVIDER=hashing
EMBEDDING_MODEL=hashing-sha256-v1
EMBEDDING_DIMENSION=1024
EMBEDDING_DEVICE=cpu
```

Benchmark scriptinin zorunlu bekledigi ayar:

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024
```

BGE-M3 izi:

- `backend/scripts/retrieval_benchmark.py` BGE-M3'u zorunlu kiliyor.
- `backend/tests/test_retrieval_benchmark.py` BGE-M3 disindaki benchmark configlerini reddediyor.
- `backend/app/services/embedding_compatibility.py` `BAAI/bge-m3` icin 1024 dimension bekliyor.

Hazirlik sonucu:

```text
Benchmark oncesi env BGE-M3'e alinmali ve ingest ayni config ile yapilmali.
```

## Benchmark Script Yolu

Mevcut benchmark script:

```text
backend/scripts/retrieval_benchmark.py
```

Script davranisi:

- Fixture path sabit: `backend/tests/fixtures/retrieval_benchmark.json`
- Input JSON array bekliyor.
- Her case icin beklenen alanlar:
  - `query`
  - `expected_doc_id`
  - `expected_category` fixture'da var ama script tarafinda metrik icin kullanilmiyor.
- `RetrievalService.grouped_search()` cagrisi yapar.
- `candidate_limit=30`, `max_documents=3`, `max_sections=6` kullanir.

## Mevcut Benchmark Format Uyumu

Aşama 2.2 benchmark dosyasi:

```text
output/rag_benchmark/rag_retrieval_benchmark_questions.jsonl
```

Bu dosya JSONL formatindadir ve alanlari:

- `question`
- `expected_doc_id`
- `expected_category`
- `expected_subcategory`
- `question_type`
- `confusable_with`
- `notes`

Mevcut benchmark scriptinin bekledigi format:

- JSON array
- `query`
- `expected_doc_id`

Uyum sonucu:

```text
Uyumsuz. Adapter gerekir.
```

Ek bulgu:

- Mevcut fixture `backend/tests/fixtures/retrieval_benchmark.json` 24 case iceriyor.
- Bu fixture eski doc_id setinden kalmis.
- Fixture icinde 17 invalid doc_id var; ornekler:
  - `ORDER_CANCEL_001`
  - `RETURN_REQUEST_001`
  - `ACCOUNT_SECURITY_LOGIN_ISSUE_001`
  - `SHIPPING_MARKED_DELIVERED_NOT_RECEIVED_001`
  - `CAMPAIGN_POINT_COUPON_INVALID_001`

Bu fixture yeni 61 final_safe setiyle benchmark icin kullanilmamali.

## Adapter Ihtiyaci

Adapter gerekir.

Minimum adapter davranisi:

- `output/rag_benchmark/rag_retrieval_benchmark_questions.jsonl` oku.
- Her satiri benchmark case'e donustur:
  - `query = question`
  - `expected_doc_id = expected_doc_id`
  - `expected_category = expected_category`
  - `expected_subcategory = expected_subcategory`
  - `question_type = question_type`
  - `confusable_with = confusable_with`
- Ya mevcut scriptin okuyacagi JSON array fixture uretmeli ya da benchmark scriptine CLI input destegi eklenmeli.

Onerilen adapter cikti yolu:

```text
output/rag_benchmark/rag_retrieval_benchmark_cases.json
```

Ancak bu asamada adapter yazilmadi; sadece ihtiyac raporlandi.

## Metrik Destegi

Mevcut `backend/scripts/retrieval_benchmark.py` destekliyor:

- Top1
- Top3
- MRR
- `best_score`
- Top3 disi failure listesi

Mevcut script desteklemiyor:

- Category Accuracy
- Subcategory Accuracy
- `question_type` bazli metrikler
- hard-negative ayrim raporu
- `confusable_with` bazli analiz
- JSONL input
- CLI ile fixture path secimi

Sonuc:

```text
Top1/Top3/MRR icin temel script var; 2.2 benchmark setinin tum raporlama ihtiyaclari icin script veya adapter genisletmesi gerekir.
```

## Ingest System Alanlari Riski

`backend/app/rag/chunking.py` mevcut tasarim:

- `ANSWER_FIELDS`: answer-safe section alanlari.
- `SEARCH_FIELDS`: retrieval icin genis ama system/debug olmayan alanlar.
- `SYSTEM_LAYER_FIELDS`: `hard_negative_doc_ids`, `related_documents`, `expected_action`, `priority`, `review_notes`.

Ingest `load_final_rag_sources()` ile final_safe dokumanlardan chunk uretir.

Aşama 1.3 sonucuyla birlikte degerlendirme:

- `content` icinde system alan sizintisi beklenmiyor.
- `contextual_content` icinde system alan sizintisi beklenmiyor.
- RAG JSON icindeki system/debug alanlari `Document.raw_json` icinde saklanir; retrieval/Gemini context'e dogrudan girmez.

Risk:

- Kod degistirilirse whitelist tekrar bozulabilir.
- Ingest oncesi son chunk audit veya küçük static kontrol tekrar edilmelidir.

## Gerekli Env Ayarlari

Benchmark hedefi BGE-M3 ise terminalde ingest ve benchmark ayni embedding config ile calismali:

```powershell
$env:EMBEDDING_PROVIDER="sentence_transformers"
$env:EMBEDDING_MODEL="BAAI/bge-m3"
$env:EMBEDDING_DIMENSION="1024"
$env:EMBEDDING_DEVICE="cpu"
```

Gerekli DB ayari:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>:<port>/<db>"
```

Not:

- `.env.example` hashing default veriyor; benchmark scripti hashing configini reddeder.
- BGE-M3 modeli local cache'te yoksa ilk calistirmada model indirme gerekebilir.
- Bu asamada model indirme veya pip install yapilmadi.

## Onerilen Guvenli Calistirma Sirasi

Bu asamada calistirilmadi; sadece oneridir.

1. Ortam ayarlarini BGE-M3'e al.
2. DB migration hazirligini kontrol et.
3. Ingest calistir.
4. DB status veya count kontrolu yap.
5. 2.2 JSONL icin adapter/cases dosyasi olustur.
6. Benchmark scriptini adapter cikti dosyasi ile calistiracak sekilde hazirla veya scripti CLI input destekleyecek sekilde genislet.
7. Benchmark calistir.
8. Top1, Top3, MRR, Category Accuracy, Subcategory Accuracy ve hard-negative ayrim raporunu uret.

## Terminalde Calistirilacak Onerilen Komutlar

Bu komutlar bu asamada calistirilmadi.

```powershell
$env:EMBEDDING_PROVIDER="sentence_transformers"
$env:EMBEDDING_MODEL="BAAI/bge-m3"
$env:EMBEDDING_DIMENSION="1024"
$env:EMBEDDING_DEVICE="cpu"

alembic upgrade head
python -m backend.scripts.ingest
python -m backend.scripts.db_status
```

Benchmark icin mevcut durumda once adapter gerekir. Adapter sonrasi olasi komut sekli:

```powershell
python -m backend.scripts.retrieval_benchmark
```

Fakat mevcut script sabit fixture okudugu icin bu komut, adapter/script guncellemesi yapilmadan 2.2 JSONL dosyasini kullanmaz.

## Riskler

- DB'de eski chunk kalmasi: Ingest calismadan benchmark yapilirsa eski 70 doc_id seti kullanilabilir.
- Embedding provider yanlis olmasi: Default hashing; benchmark script BGE-M3 bekliyor.
- Benchmark format mismatch: 2.2 dosyasi JSONL `question`, script JSON array `query` bekliyor.
- Eski fixture kullanimi: Mevcut fixture eski doc_id setinden kalmis ve 61 final_safe ile uyumsuz.
- Ingest'in system alanlari yanlis islemesi: Mevcut whitelist guvenli gorunuyor, ama degisikliklerde tekrar kontrol edilmeli.
- Benchmark eski doc_id setini kullanmasi: `DEFAULT_FIXTURE` degistirilmezse veya adapter baglanmazsa bu risk yuksek.
- BGE-M3 runtime gereksinimi: `sentence_transformers` modeli ve model cache/network hazir olmali.

## Genel Karar

NEEDS_ADAPTER

Gerekce:

- Ingest script var ve 61 final_safe akisi icin uygun.
- Ingest eski `chunks/documents` kayitlarini temizleyecek sekilde yazilmis.
- Benchmark script var ancak mevcut 2.2 JSONL formatiyla uyumlu degil.
- Mevcut benchmark fixture eski doc_id setinden kalmis.
- Script sadece Top1/Top3/MRR verir; category/subcategory ve hard-negative ayrim raporu icin genisletme gerekir.
