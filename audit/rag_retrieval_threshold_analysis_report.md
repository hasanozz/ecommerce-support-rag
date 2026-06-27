# RAG Retrieval Threshold Analysis Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, retrieval benchmark sonucunda bos donen exact-match sorgular ve yanlis eslesmeler icin threshold, top_k ve score filtering etkisini statik olarak analiz eder.

Bu asamada kod, RAG JSON, chunk, DB, ingest, embedding, benchmark, test, git veya pip islemi yapilmadi.

## Mevcut Retrieval Threshold / Top_k Ayarlari

`backend/app/services/retrieval.py` icindeki akis:

- `grouped_search()` DB'den once chunk adaylarini alir.
- `search(session, query, limit=candidate_limit)` cagrilir.
- Benchmark tarafinda `candidate_limit=30` oldugu icin DB'den en fazla 30 chunk adayi cekilir.
- Chunklar doc_id bazinda gruplanir.
- Her doc icin `best_score = max(chunk.score)` hesaplanir.
- Sonra doc bazinda `best_score >= min_score` filtresi uygulanir.
- Sonuc en fazla `max_documents=3` dokuman olarak doner.

Score hesabi:

```text
score = 1.0 - cosine_distance
```

Minimum score secimi:

```text
if embedding_provider == "hashing":
    minimum_score = hashing_min_retrieval_score
else:
    minimum_score = min_retrieval_score
```

Config defaultlari:

| Ayar | Deger |
| --- | ---: |
| `search_limit` | 10 |
| `min_retrieval_score` | 0.55 |
| `hashing_min_retrieval_score` | 0.30 |
| `embedding_provider` default | `hashing` |
| `embedding_model` default | `hashing-sha256-v1` |
| `embedding_dimension` | 1024 |

Not:

- `search_limit` benchmarkte fiilen kullanilmiyor; benchmark `candidate_limit=30` veriyor.
- BGE-M3 benchmark akisi icin `embedding_provider=sentence_transformers` oldugundan beklenen min score `0.55`.

## Benchmark Script Ayarlari

`backend/scripts/retrieval_benchmark.py` icindeki ayarlar:

| Ayar | Deger |
| --- | ---: |
| fixture | `backend/tests/fixtures/retrieval_benchmark.json` |
| expected provider | `sentence_transformers` |
| expected model | `BAAI/bge-m3` |
| expected dimension | 1024 |
| `candidate_limit` | 30 |
| `max_documents` | 3 |
| `max_sections` | 6 |

Benchmark script metrikleri:

- Top1
- Top3
- MRR
- `best_score` sadece sonuc varsa raporlanir.

## Bos Donen Sorgular Icin Muhtemel Sebep

Bos donen iki sorgu:

- `Şifremi unuttum.` -> expected `PASSWORD_RESET_001`
- `İadem neden reddedildi?` -> expected `IADE_REDDI_NEDENLERI_001`

Dosya seviyesinde bulgu:

- Her iki expected doc_id icin `rag_chunks_clean.jsonl` icinde 6 chunk var.
- Her iki query de beklenen dokumanin `kullanici_ifadeleri` alaninda birebir var.
- Query terimleri beklenen dokumanin `contextual_content` alaninda var.

Bu nedenle dosya seviyesinde en olasi sebepler:

1. `RETRIEVAL_THRESHOLD_ISSUE`
   - DB'den aday chunk gelmis olabilir, fakat doc `best_score < 0.55` oldugu icin `group_chunks()` sonrasi elenmis olabilir.
   - Kisa querylerde BGE-M3 cosine score eşiği 0.55'i gecemeyebilir.

2. `ACTIVE_DB_OR_INGEST_MISMATCH`
   - Dosyada chunk var ama DB'nin aktif ingest seti eski veya farkli olabilir.
   - Benchmark DB'den okudugu icin dosya coverage tek basina runtime coverage garantisi degildir.

3. `TOP_K_CANDIDATE_MISS`
   - DB'den sadece ilk 30 chunk adayi aliniyor.
   - Beklenen doc chunklari ilk 30 chunk icine girmediyse grouped result hic olusmaz.
   - Exact-match ifadelerde bu daha dusuk olasilik, ancak aktif embedding/index uyumsuzsa mumkun.

Benchmark script top3 oncesi filtre uyguluyor mu?

```text
Evet. Top3 listesi olusmadan once group_chunks() icinde min_score filtresi uygulanir.
```

## 5 Failure Query-source Coverage Tablosu

| Query | Expected doc_id | Chunk var mi? | Exact kullanici ifadesi var mi? | Contextual terim coverage | Content terim coverage | Ranked result | Muhtemel sebep |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Şifremi unuttum. | `PASSWORD_RESET_001` | 6 chunk | Evet | Tam | Tam | Bos | Threshold veya aktif DB/ingest uyumsuzlugu |
| Ben bu siparişi vermedim. | `UNAUTHORIZED_ORDER_PAYMENT_001` | 6 chunk | Evet | Tam | Kismi | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Semantic overlap + score siralamasi |
| İadem neden reddedildi? | `IADE_REDDI_NEDENLERI_001` | 6 chunk | Evet | Tam | Kismi | Bos | Threshold veya aktif DB/ingest uyumsuzlugu |
| Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | `KAMPANYA_KULLANIMI_001` | 6 chunk | Hayir | Kismi | Kismi | `KUPON_KODU_KULLANIMI_001`, `KAMPANYALARIN_BIRLESTIRILMESI_001`, `KAMPANYA_KOSULLARI_001` | Benchmark query zayif; confusable title baskin |
| Siparişimden puan gelmedi. | `PUAN_KAZANMA_001` | 6 chunk | Evet | Tam | Kismi | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001`, `PAYMENT_FAILED_001`, `IADE_SONRASI_PUAN_DURUMU_001` | Semantic overlap; content tarafinda puan disi terimler zayif |

## Failure Bazli Karar

| Expected doc_id | Karar | Threshold degissin mi? | Search_text degissin mi? | Benchmark query degissin mi? |
| --- | --- | --- | --- | --- |
| `PASSWORD_RESET_001` | `RETRIEVAL_THRESHOLD_ISSUE` | Hemen degil; once aktif DB ve per-case score gorulmeli | Hayir | Hayir |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `DOC_SEMANTIC_OVERLAP` | Hayir | Gerekirse evet | Hayir |
| `IADE_REDDI_NEDENLERI_001` | `RETRIEVAL_THRESHOLD_ISSUE` | Hemen degil; once aktif DB ve per-case score gorulmeli | Hayir | Hayir |
| `KAMPANYA_KULLANIMI_001` | `BENCHMARK_QUERY_WEAK` | Hayir | Hayir | Evet |
| `PUAN_KAZANMA_001` | `DOC_SEMANTIC_OVERLAP` | Hayir | Gerekirse evet | Opsiyonel |

## Threshold Degisikligi Oneriliyor mu?

Kisa cevap:

```text
Simdilik hayir.
```

Gerekce:

- Top3 skoru zaten yuksek: `0.9727`.
- Failure sayisi dusuk: 5/183.
- Bos donen iki exact-match sorgu threshold kaynakli olabilir, ancak per-case score verilmedigi icin global threshold dusurmek su an erken.
- Global `min_retrieval_score` dusurmek yanlis pozitifleri artirabilir.

Onerilen onceki kontrol:

- DB'nin aktif ingest setinin 61 doc / 366 chunk oldugu dogrulanmali.
- Bos donen iki query icin ham aday skorlar veya min_score oncesi grouped result incelenmeli.
- Eger beklenen dokuman skorları 0.55'in hemen altindaysa kontrollu threshold denemesi dusunulebilir.

## Search_text Degisikligi Oneriliyor mu?

Hemen zorunlu degil.

Neden:

- `PASSWORD_RESET_001`, `IADE_REDDI_NEDENLERI_001`, `UNAUTHORIZED_ORDER_PAYMENT_001`, `PUAN_KAZANMA_001` icin ilgili kullanici ifadeleri zaten kaynak dokumanda var.
- `contextual_content` bu ifadeleri tasiyor.
- Bu nedenle once aktif DB/embedding ve threshold etkisi ayrilmali.

Gerekirse guclendirilecek doc_id listesi:

- `UNAUTHORIZED_ORDER_PAYMENT_001`
  - yetkisiz sipariş
  - ben bu siparişi vermedim
  - bana ait olmayan sipariş
  - bilgim dışında sipariş oluşturuldu
- `PUAN_KAZANMA_001`
  - sipariş puanı
  - siparişten puan gelmedi
  - alışveriş puanı hesabıma eklenmedi
  - kampanya puanı kazanamadım

## Benchmark Query Degisikligi Oneriliyor mu?

Evet, bir case icin net onerilir.

Degistirilmesi onerilen query:

```text
Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum.
```

Sebep:

- Query confusable doc title'ini en basta ve tam haliyle tasiyor.
- Embedding retrieval `değil` negasyonunu mantiksal dislama olarak ele almaz.

Onerilen query:

```text
Kupon kodu girmeden, sepetteki kampanyanın hangi ürünlere uygulandığını öğrenmek istiyorum.
```

Opsiyonel netlestirme:

```text
Siparişimden puan gelmedi.
```

yerine:

```text
Siparişimden kampanya puanı hesabıma eklenmedi.
```

Ancak bu ikinci degisiklik zorunlu degil; mevcut soru dogal kullanici dilidir.

## Genel Karar

WARNING

Gerekce:

- Retrieval kodunda Top3 oncesi min_score filtresi var.
- Benchmark BGE-M3 icin default `min_retrieval_score=0.55` kullaniyor.
- Bos donen iki exact-match query dosya seviyesinde beklenen dokumanla uyumlu; bu threshold veya aktif DB/ingest uyumsuzlugu kontrolu gerektiriyor.
- Global threshold degisikligi icin henuz yeterli per-case score kaniti yok.
- Bir benchmark query zayif ve duzeltilmeli.
