# RAG Quality Phase A Validation Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, ana projedeki RAG dokumanlari ile staging `final_safe` kaynaklarinin uyumunu, doc_id ve chunk coverage durumunu, chunk metadata alanlarini ve Gemini answer context tarafina system/backend alanlarinin sizip sizmadigini kontrol eder.

Kontrol sirasinda JSON dosyalari, chunk dosyalari, kod, DB, ingest, benchmark ve test calistirma islemlerine dokunulmadi. Yalnizca okuma ve bu audit raporunu olusturma islemi yapildi.

## Kontrol Edilen Ana Proje RAG Klasoru

Ana proje RAG dokuman klasoru:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\rag_documents_final
```

Ana proje RAG dosyalari:

| Dosya | Doc sayisi |
| --- | ---: |
| `hesap_guvenlik_final_safe.json` | 13 |
| `iade_final_safe.json` | 9 |
| `kampanya_puan_final_safe.json` | 11 |
| `kargo_teslimat_final_safe.json` | 11 |
| `odemeler_final_safe.json` | 8 |
| `siparis_final_safe.json` | 9 |

## Kontrol Edilen Staging Final Safe Dosyalari

Staging kaynak klasoru:

```text
C:\Users\lenovo\Desktop\Yeni klasör\output\rag_documents_final_safe
```

Kontrol edilen dosyalar:

| Dosya | Doc sayisi | Ana proje ile birebir ayni mi? |
| --- | ---: | --- |
| `hesap_guvenlik_final_safe.json` | 13 | Evet |
| `iade_final_safe.json` | 9 | Evet |
| `kampanya_puan_final_safe.json` | 11 | Evet |
| `kargo_teslimat_final_safe.json` | 11 | Evet |
| `odemeler_final_safe.json` | 8 | Evet |
| `siparis_final_safe.json` | 9 | Evet |

## Doc_id Sayilari

| Kaynak | Toplam doc_id | Unique doc_id | 61 mi? |
| --- | ---: | ---: | --- |
| Ana proje `rag_documents_final` | 61 | 61 | Evet |
| Staging `final_safe` | 61 | 61 | Evet |

## Eksik Doc_id Listesi

Staging `final_safe` icinde olup ana projede bulunmayan doc_id yok.

```text
Yok
```

## Fazla Doc_id Listesi

Ana projede olup staging `final_safe` icinde bulunmayan doc_id yok.

```text
Yok
```

## Degismis Doc_id / Icerik Farki Ozeti

Ana proje ve staging arasinda ortak doc_id sayisi: 61.

Degismis doc_id / icerik farki sonucu:

```text
Yok
```

Dosya bazinda normalize JSON karsilastirmasi sonucunda ana proje `rag_documents_final` altindaki 6 `*_final_safe.json` dosyasi staging `final_safe` dosyalariyla birebir aynidir.

## Duplicate Doc_id Sonucu

| Kaynak | Sonuc |
| --- | --- |
| Ana proje RAG JSON dosyalari | Duplicate doc_id yok |
| Staging `final_safe` JSON dosyalari | Duplicate doc_id yok |
| `rag_chunks_clean.jsonl` | Duplicate `chunk_id` yok |

## Chunk Kaynagi

Ana projede bulunan chunk dosyasi:

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\rag_chunks\rag_chunks_clean.jsonl
```

Chunk uretim/okuma kodu olarak incelenen ana dosyalar:

- `backend/app/rag/chunking.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/gemini_prompts.py`

## Chunk Toplam Sayisi

| Chunk dosyasi | Toplam chunk | Unique chunk_id | Unique doc_id |
| --- | ---: | ---: | ---: |
| `rag_chunks_clean.jsonl` | 411 | 411 | 70 |

## Chunk Coverage Sonucu

Ana proje RAG JSON doc_id setine gore chunk coverage:

```text
FAIL
```

Detay:

- Ana proje RAG JSON doc_id sayisi: 61.
- Chunk dosyasindaki unique doc_id sayisi: 70.
- Ana proje doc_id setinden chunk bulunmayan doc_id sayisi: 51.
- Chunk dosyasinda olup ana proje RAG JSON setinde olmayan eski/fazla doc_id sayisi: 60.
- Ana proje doc_id seti icin minimum chunk/doc: 0.

Bu sonuc, RAG JSON dosyalarinin staging `final_safe` setine guncellendigini fakat mevcut chunk dosyasinin hala eski doc_id setinden kaldigini gosteriyor.

## Chunk Olmayan Doc_id Listesi

Ana proje `rag_documents_final` icinde olup `rag_chunks_clean.jsonl` icinde bulunmayan doc_id listesi:

```text
ACCOUNT_CREATE_001
ACCOUNT_DELETE_001
ACCOUNT_EMAIL_CHANGE_001
ACCOUNT_LOGIN_ISSUE_001
ACCOUNT_PHONE_CHANGE_001
ACCOUNT_SUSPENSION_001
ACCOUNT_VERIFY_001
IADE_IADE_SARTLARI_001
IADE_KARGO_SURECI_001
IADE_KODU_ALMA_001
IADE_KULLANILMIS_URUN_001
IADE_KUSURLU_HASARLI_URUN_001
IADE_REDDI_NEDENLERI_001
IADE_SONRASI_PUAN_DURUMU_001
IADE_TALEBI_OLUSTURMA_001
IADE_UCRETININ_HESABA_GECMESI_001
IADE_URUN_INCELEME_001
KAMPANYALARIN_BIRLESTIRILMESI_001
KAMPANYA_KOSULLARI_001
KAMPANYA_KULLANIMI_001
KATEGORIYE_OZEL_KAMPANYALAR_001
KUPON_GECERSIZ_HATASI_001
KUPON_KODU_KULLANIMI_001
MINIMUM_SEPET_TUTARI_001
PASSWORD_RESET_001
PAYMENT_AUTHORIZATION_PENDING_001
PAYMENT_CARD_PAYMENT_001
PAYMENT_COUPON_POINT_PAYMENT_001
PERSONAL_DATA_SECURITY_001
PUAN_KAZANMA_001
PUAN_KULLANMA_001
SESSION_MANAGEMENT_001
SHIPPING_ADDRESS_REDELIVERY_001
SHIPPING_DELAYED_DELIVERY_001
SHIPPING_DELIVERED_NOT_RECEIVED_001
SHIPPING_DELIVERY_FAILED_001
SHIPPING_ESTIMATED_DELIVERY_001
SHIPPING_MULTI_PACKAGE_DELIVERY_001
SIPARIS_ADDRESS_CHANGE_001
SIPARIS_CONTENT_CHANGE_001
SIPARIS_MISSING_ITEM_001
SIPARIS_ORDER_CANCEL_001
SIPARIS_ORDER_CREATE_001
SIPARIS_ORDER_SPLIT_001
SIPARIS_ORDER_STATUS_001
SIPARIS_ORDER_TRACKING_001
SIPARIS_WRONG_ITEM_001
SURESI_DOLAN_KUPON_PUAN_001
SUSPICIOUS_LOGIN_ALERT_001
TWO_FACTOR_AUTH_001
UNAUTHORIZED_ORDER_PAYMENT_001
```

Chunk dosyasinda olup ana proje RAG JSON setinde olmayan eski doc_id ornekleri:

```text
ACCOUNT_SECURITY_CREATE_001
ACCOUNT_SECURITY_DELETE_001
ACCOUNT_SECURITY_EMAIL_CHANGE_001
ACCOUNT_SECURITY_LOGIN_ISSUE_001
ACCOUNT_SECURITY_PASSWORD_RESET_001
CAMPAIGN_POINT_CAMPAIGN_USE_001
ORDER_CREATE_001
PAYMENT_CARD_001
RETURN_CONDITIONS_001
SHIPPING_ESTIMATED_DATE_001
```

## Metadata Coverage Sonucu

Chunk metadata alan varligi:

- `doc_id`: Tum chunk kayitlarinda var.
- `category`: Tum chunk kayitlarinda var.
- `subcategory`: Tum chunk kayitlarinda var.

Ana proje JSON doc_id setiyle eslesen chunklar uzerindeki metadata uyumu:

- Eksik metadata alani: 0.
- `category` mismatch: 0.
- `subcategory` mismatch: 5 chunk.

Tespit edilen `subcategory` mismatch kayitlari:

| chunk_id | Chunk subcategory | Ana proje subcategory |
| --- | --- | --- |
| `SHIPPING_CARRIER_CHANGE_001__amac_tanim__001` | `KARGO_FIRMASI_SECIMI_DEGISIKLIGI` | `KARGO_FIRMASI_DEGISIKLIGI` |
| `SHIPPING_CARRIER_CHANGE_001__kosullar__001` | `KARGO_FIRMASI_SECIMI_DEGISIKLIGI` | `KARGO_FIRMASI_DEGISIKLIGI` |
| `SHIPPING_CARRIER_CHANGE_001__kosullar__002` | `KARGO_FIRMASI_SECIMI_DEGISIKLIGI` | `KARGO_FIRMASI_DEGISIKLIGI` |
| `SHIPPING_CARRIER_CHANGE_001__adimlar__001` | `KARGO_FIRMASI_SECIMI_DEGISIKLIGI` | `KARGO_FIRMASI_DEGISIKLIGI` |
| `SHIPPING_CARRIER_CHANGE_001__standart_yanit__001` | `KARGO_FIRMASI_SECIMI_DEGISIKLIGI` | `KARGO_FIRMASI_DEGISIKLIGI` |

Not: Chunk dosyasi eski doc_id setini tasidigi icin metadata coverage genel karari chunk regeneration gerektirir.

## Search Text / Answer Context Ayrimi

Dosya seviyesinde mevcut `rag_chunks_clean.jsonl` icinde su alanlar yok:

- `search_text`
- `answer_context`
- `contextual_content`

Kod seviyesinde ayrim mevcut:

- `backend/app/rag/chunking.py` icinde `SEARCH_FIELDS` ve `ANSWER_FIELDS` ayrilmis.
- `build_search_text(document)` arama/embedding tarafinda kullanilacak genis metni olusturuyor.
- `final_document_to_chunks(document)` sadece `ANSWER_FIELDS` alanlarindan chunk `content` olusturuyor.
- `ANSWER_FIELDS`: `tanim`, `kosullar`, `adimlar`, `istisnalar`, `destek_gerektiren_durumlar`, `standart_yanit`.
- `SYSTEM_LAYER_FIELDS`: `hard_negative_doc_ids`, `related_documents`, `expected_action`, `priority`, `review_notes`.
- `backend/app/services/retrieval.py` icinde Gemini context'e giden `GroupedDocument.combined_context`, retrieval sonucundaki `chunk.content` alanlarindan olusuyor.
- `backend/app/services/gemini_prompts.py` icinde bu veri `KNOWLEDGE_BASE_CONTEXT` olarak Gemini answer promptuna veriliyor.

Ornek beklenen answer context parcasi kod akisi bazinda su sekildedir:

```text
Doküman: <title>
Kategori: <category label>

Tanım:
<answer-safe content>

Koşullar:
<answer-safe content>
```

Bu yapida system/backend alan adlari answer context'e dogrudan eklenmemelidir.

## System Alan Sizintisi Sonucu

Kontrol edilen system/backend alanlari:

- `hard_negative_doc_ids`
- `related_documents`
- `expected_action`
- `priority`
- `review_notes`
- `internal_notes`
- `hard_negative`

Ana proje RAG JSON dosyalarinda top-level alan durumu:

| Alan | Bulundugu dokuman sayisi |
| --- | ---: |
| `hard_negative_doc_ids` | 61 |
| `related_documents` | 61 |
| `expected_action` | 61 |
| `priority` | 61 |
| `review_notes` | 61 |
| `internal_notes` | 0 |
| `hard_negative` | 0 |

Staging `final_safe` dosyalarinda ayni top-level system/debug alanlari ayni sekilde mevcuttur.

Content/answer-safe alanlarda sizinti:

- Ana proje `tanim`, `kosullar`, `adimlar`, `istisnalar`, `destek_gerektiren_durumlar`, `standart_yanit` ve search tarafinda kullanilan diger metin alanlarinda bu system alan adlari gecmedi.
- Staging metin alanlarinda bu system alan adlari gecmedi.
- `rag_chunks_clean.jsonl` icinde `content`, `search_text`, `answer_context`, `contextual_content` veya diger chunk JSON alanlarinda bu system alan adlari gecmedi.

Gemini answer context sonucu:

```text
Mevcut chunk dosyasi ve kod akisi uzerinden system alan sizintisi bulgusu yok.
```

Ancak onemli not:

- Top-level system/debug alanlari ana proje RAG JSON dosyalarinda 61 dokumanin tamaminda duruyor.
- Kodda `ANSWER_FIELDS` bu alanlari answer chunk content disinda birakacak sekilde tasarlanmis.
- Buna ragmen mevcut chunk dosyasi yeni final_safe doc_id setinden uretilmedigi icin runtime DB/chunk durumu dosya bazinda tutarli degil.

## Bu Alanlar Sadece Metadata/Debug Tarafinda Kaliyor mu?

Kod tasarimina gore:

- `hard_negative_doc_ids`, `related_documents`, `expected_action`, `priority`, `review_notes` alanlari `SYSTEM_LAYER_FIELDS` olarak ayrilmis.
- `final_document_to_chunks()` answer chunk `content` uretirken bu alanlari kullanmiyor.
- `build_search_text()` de bu alanlari `SEARCH_FIELDS` icine almiyor.
- Gemini `KNOWLEDGE_BASE_CONTEXT`, `retrieval.py` tarafinda chunk `content` alanindan olusturuldugu icin system alanlarinin answer context'e girmemesi beklenir.

Fiili dosya durumuna gore:

- Mevcut `rag_chunks_clean.jsonl` icinde system alanlari yok.
- Dolayisiyla mevcut dosya/kod auditinde system alanlari answer context'e sizmiyor.

## Riskler

- Ana RAG JSON dosyalari staging ile birebir uyumlu olsa da chunk dosyasi eski 70 doc_id setinden kalmis.
- 61 final_safe doc_id icin 51 doc_id'nin hic chunk'i yok; retrieval bu dokumanlari bulamaz.
- Chunk dosyasinda ana proje RAG JSON setinde olmayan 60 eski doc_id var; retrieval eski/yanlis kaynaklardan cevap uretebilir.
- `SHIPPING_CARRIER_CHANGE_001` icin 5 chunk'ta `subcategory` eski degerle kalmis.
- System/debug alanlari top-level olarak RAG JSON icinde mevcut; kodda filtreleme var, fakat yeni chunk uretimi sirasinda bu whitelist korunmazsa Gemini context'e sizinti riski olusur.
- Bu audit DB okumaz; DB'de hangi chunklarin yuklu oldugu ayrica kontrol edilmedi.

## Genel Karar

FAIL

Gerekce:

- RAG JSON uyumu: PASS.
- Doc_id sayisi: PASS, ana proje ve staging 61.
- Duplicate doc_id: PASS.
- System alan sizintisi: PASS, mevcut dosya/kod auditinde sizinti yok.
- Chunk coverage: FAIL, mevcut chunk dosyasi final_safe 61 doc_id setiyle uyumsuz.
- Metadata coverage: WARNING/FAIL, alanlar var ama eski chunk seti ve 5 subcategory mismatch var.

## Sonraki Onerilen Adim

Aşama 2'de ingest veya DB islemi yapmadan once, mevcut final_safe 61 dokumanlik setten chunk dosyasi kontrollu sekilde yeniden uretilmeli ve yeniden audit edilmelidir.

Onerilen sira:

1. `backend/app/rag/chunking.py` icindeki `ANSWER_FIELDS`, `SEARCH_FIELDS` ve `SYSTEM_LAYER_FIELDS` whitelist mantigi korunarak yeni chunk seti uretilsin.
2. Yeni chunk dosyasinda 61/61 doc_id coverage, 0 extra doc_id, 0 duplicate chunk_id ve 0 metadata mismatch dogrulansin.
3. System/debug alanlarinin `content`, `contextual_content`, `search_text` veya answer context'e girmedigi tekrar kontrol edilsin.
4. Bu kontroller PASS olduktan sonra ayrica onayla ingest/DB asamasina gecilsin.
