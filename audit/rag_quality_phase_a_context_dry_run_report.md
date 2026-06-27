# RAG Quality Phase A.2 Context Dry-Run Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, yeni 61 `final_safe` doc_id setinden uretilen `rag_chunks/rag_chunks_clean.jsonl` dosyasinin retrieval ve Gemini answer context hattinda statik/dry-run seviyesinde kullanilabilirligini kontrol eder.

Kurallara uygun olarak JSON, chunk ve kod dosyalari degistirilmedi. DB, ingest, embedding, benchmark, test, git ve pip islemleri calistirilmadi. Sadece okuma, dry-run analiz ve bu audit raporu olusturma islemi yapildi.

## Canonical Chunk Path Dogrulamasi

`backend/app/config.py` icinde canonical RAG path degerleri:

```text
rag_documents_final_path = PROJECT_ROOT / "rag_documents_final"
rag_chunks_clean_path = PROJECT_ROOT / "rag_chunks" / "rag_chunks_clean.jsonl"
```

Sonuc:

```text
PASS - Canonical chunk path rag_chunks/rag_chunks_clean.jsonl olarak tanimli.
```

## Retrieval Tarafinda Kullanilan Chunk Alanlari

`backend/app/services/retrieval.py` icinde `RetrievedChunk` su alanlari tasiyor:

- `chunk_id`
- `doc_id`
- `title`
- `category`
- `subcategory`
- `section`
- `content`
- `contextual_content`
- `score`

DB retrieval sirasinda:

- Query embedding `embed_query(query)` ile uretiliyor.
- Benzerlik siralamasi `Chunk.embedding` uzerinden yapiliyor.
- DB'den donen chunk kaydinda hem `chunk.content` hem `chunk.contextual_content` okunuyor.

`group_chunks()` icinde Gemini answer context'e gidecek `combined_context` uretiminde kullanilan alan:

```text
chunk.content
```

`contextual_content`, `RetrievedChunk` icinde tasiniyor fakat `combined_context` icine eklenmiyor.

## Embedding / Search Tarafi

`backend/scripts/ingest.py` incelendiginde embedding uretiminde kullanilan alan:

```text
item["contextual_content"]
```

Ilgili akis:

- `load_final_rag_sources(documents_path, chunks_path)` final_safe dokumanlardan chunklari uretir.
- `embedding_service.embed_documents([item["contextual_content"] for item in batch])` ile embedding metni `contextual_content` uzerinden uretilir.
- `Chunk(**chunk, embedding=embedding)` ile DB'ye hem `content` hem `contextual_content` yazilacak sekilde hazirlanir.

Sonuc:

```text
Search/embedding tarafi contextual_content kullanacak sekilde tasarlanmis.
```

## Gemini Context Tarafi

`backend/app/services/retrieval.py`:

- `group_chunks()` secilen section iceriklerini `chunk.content` ile toplar.
- `combined_context` formatinda `Doküman`, `Kategori` ve section bloklari olusturur.

`backend/app/services/ai_contracts.py`:

- `ContextBuilder.build()` ilk 3 `GroupedDocument.combined_context` degerini `====================` ayraci ile birlestirir.

`backend/app/services/pipeline.py`:

- `llm_context = self.context_builder.build(grouped)`
- Gemini answer cagrisina `llm_context` verilir.

`backend/app/services/gemini_prompts.py`:

- `llm_context`, prompt icinde `<KNOWLEDGE_BASE_CONTEXT>` bolumune yerlestirilir.
- `AVAILABLE_SOURCES` ayrica `doc_id` ve `title` listesini tasir.

Sonuc:

```text
Gemini answer context tarafi chunk.content kullaniyor; contextual_content answer context'e dogrudan girmiyor.
```

## Dry-Run Combined Context Ornekleri

Dry-run, `rag_chunks/rag_chunks_clean.jsonl` icindeki yeni chunklar kullanilarak `retrieval.py` icindeki `group_chunks()` mantigiyle simule edildi. Her hedef doc_id icin 6 chunk bulundu ve 6 answer section kullanildi.

Kontrol edilen doc_id listesi:

- `PAYMENT_CHARGED_ORDER_NOT_CREATED_001`
- `SIPARIS_ORDER_CANCEL_001`
- `SHIPPING_TRACKING_001`
- `IADE_TALEBI_OLUSTURMA_001`
- `PASSWORD_RESET_001`

Ortak section sirasi:

```text
tanim
kosullar
adimlar
istisnalar
destek_gerektiren_durumlar
standart_yanit
```

Ozet tablo:

| doc_id | Title | Category | Chunk | Context uzunlugu | System hit |
| --- | --- | --- | ---: | ---: | --- |
| `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Karttan Para Cekildi Ama Siparis Olusmadi | `ODEME` | 6 | 2017 | Yok |
| `SIPARIS_ORDER_CANCEL_001` | Siparis Iptali | `SIPARIS` | 6 | 1444 | Yok |
| `SHIPPING_TRACKING_001` | Kargo Takip Islemi | `KARGO_TESLIMAT` | 6 | 1436 | Yok |
| `IADE_TALEBI_OLUSTURMA_001` | Iade Talebi Olusturma | `IADE` | 6 | 1253 | Yok |
| `PASSWORD_RESET_001` | Sifre Sifirlama | `HESAP_GUVENLIK` | 6 | 1802 | Yok |

Ornek context iskeleti:

```text
Doküman: <title>

Kategori: <category label>

Tanım:
<chunk.content>

Koşullar:
<chunk.content>

Adımlar:
<chunk.content>

İstisnalar:
<chunk.content>

Destek Gerektiren Durumlar:
<chunk.content>

Standart Yanıt:
<chunk.content>
```

## Doc_id / Title / Category Yeterliligi

`combined_context` icinde:

- `title`: Var, `Doküman: <title>` satirinda tasiniyor.
- `category`: Var, insan okunur kategori etiketiyle tasiniyor.
- `doc_id`: `combined_context` icinde yok.

Ancak `pipeline.py` ayni anda `available_sources = [{"doc_id": item.doc_id, "title": item.title} ...]` olusturuyor ve `gemini_prompts.py` bunu `<AVAILABLE_SOURCES>` icinde Gemini promptuna veriyor. `cited_doc_ids` kurallari da sadece `AVAILABLE_SOURCES` icindeki doc_id degerlerinin kullanilmasini istiyor.

Degerlendirme:

```text
Answer metni icin title/category yeterli. Citation icin doc_id combined_context yerine AVAILABLE_SOURCES uzerinden saglaniyor.
```

## System Alan Sizintisi Sonucu

Kontrol edilen system/backend alanlari:

- `hard_negative_doc_ids`
- `related_documents`
- `expected_action`
- `priority`
- `review_notes`
- `internal_notes`
- `hard_negative`

Kontrol edilen yerler:

- 5 dry-run `combined_context` ornegi
- `chunk.content`
- `chunk.contextual_content`
- varsa `search_text`
- varsa `answer_context`

Sonuc:

```text
PASS - System/backend alan sizintisi yok.
```

Detay:

- Dry-run `combined_context` orneklerinde system alan adlari gecmedi.
- Yeni chunk dosyasinda `search_text` ve `answer_context` alanlari yok.
- `contextual_content` genis search metni tasiyor ama system/debug alanlarini tasimiyor.
- `content` sadece answer-safe section metinlerini tasiyor.

## Content / Contextual_content Ayrimi Degerlendirmesi

Mevcut ayrim:

- `contextual_content`: Search/embedding icin genis metin. `SEARCH_FIELDS` ile `title`, `category`, `subcategory`, `amac`, `kapsam`, `tanim`, `kullanici_ifadeleri`, `kosullar`, `adimlar`, `istisnalar`, `destek_gerektiren_durumlar`, `standart_yanit`, `sik_yapilan_hatalar` alanlarini iceriyor.
- `content`: Gemini answer context icin dar metin. `ANSWER_FIELDS` ile `tanim`, `kosullar`, `adimlar`, `istisnalar`, `destek_gerektiren_durumlar`, `standart_yanit` alanlarini iceriyor.

Guculu taraflar:

- Search tarafinda kullanici ifadeleri, amac, kapsam ve sik yapilan hatalar gibi retrieval kalitesini artirabilecek alanlar var.
- Answer tarafinda system/debug alanlari yok.
- Answer context daha kontrollu ve policy/procedure cevap alanlariyla sinirli.

Kalite notu:

- `final_document_to_chunks()` icinde `content`, `build_answer_section()` ile zaten section etiketi eklenmis olarak uretiliyor.
- `retrieval.py` icindeki `group_chunks()` ayni section etiketi tekrar ekliyor.
- Bu nedenle dry-run contextlerde `Tanım:\nTanım:`, `Koşullar:\nKoşullar:` gibi tekrarlar olusuyor.
- Bu durum system sizintisi veya coverage hatasi degil; fakat prompt temizligi ve cevap kalitesi acisindan iyilestirme adayi.

Degerlendirme:

```text
content/contextual_content ayrimi genel olarak uygun. Section etiketi tekrari nedeniyle kalite karari PASS yerine WARNING verildi.
```

## Riskler

- Bu audit DB durumunu dogrulamaz; DB'de eski chunklar varsa runtime hala eski veriyi kullanabilir.
- Yeni chunk dosyasi dogru olsa bile ingest/embedding yapilmadigi icin arama indexinin guncel oldugu garanti edilmez.
- Section etiketi tekrarinin Gemini cevap kalitesini az da olsa etkileme riski var.
- `combined_context` icinde doc_id yok; citation icin `AVAILABLE_SOURCES` akisi dogru calismaya devam etmelidir.
- `contextual_content` cok genis oldugu icin embedding kalitesi iyi olabilir, ancak uzunluk ve agirliklandirma davranisi ileride benchmark ile olculmelidir.

## Genel Karar

WARNING

Gerekce:

- Canonical chunk path dogru.
- Retrieval DB kaydinda `content` ve `contextual_content` alanlarini tasiyor.
- Embedding/search tasarimi `contextual_content` kullaniyor.
- Gemini answer context `content` kullaniyor.
- 5 dry-run ornekte system/backend alan sizintisi yok.
- Title/category answer context icinde var; doc_id citation icin `AVAILABLE_SOURCES` ile saglaniyor.
- Ancak `content` ve `retrieval.py` ikisi de section etiketi ekledigi icin dry-run contextlerde tekrarli section basliklari var.

## Sonraki Onerilen Adim

Aşama 1.3 icin iki secenek degerlendirilmeli:

1. Kod degisikligi yapmadan devam edilecekse, mevcut `WARNING` kabul edilip onay sonrasi ingest/embedding asamasi planlanabilir.
2. Prompt temizligi iyilestirilecekse, kod degisikligi icin ayri onay alinarak ya `final_document_to_chunks()` content alanindan section etiketi kaldirilmali ya da `retrieval.py` `group_chunks()` section etiketi tekrarini engellemelidir.

Her iki durumda da DB/ingest asamasindan once kullanicidan ayrica onay alinmalidir.
