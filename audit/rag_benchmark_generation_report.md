# RAG Benchmark Generation Report

Tarih: 2026-06-26

## Kapsam

61 `final_safe` doc_id icin retrieval benchmark soru seti olusturuldu. Her doc_id icin 1 `direct`, 1 `natural`, 1 `hard_negative` soru uretildi. Fine-tune dosyalari kullanilmadi; DB, ingest, embedding, benchmark, test, git ve pip islemleri calistirilmadi.

## Cikti Dosyasi

```text
C:\Users\lenovo\Desktop\teknocampus proje\ecommerce-support-rag\output\rag_benchmark\rag_retrieval_benchmark_questions.jsonl
```

## Toplam Soru Sayisi

| Metrik | Deger |
| --- | ---: |
| Toplam soru | 183 |
| Beklenen minimum | 183 |
| JSONL parse hatasi | 0 |
| UTF-8/mojibake suspect | 0 |

## Doc_id Coverage

| Metrik | Deger |
| --- | ---: |
| Kaynak doc_id | 61 |
| Soru uretilen doc_id | 61 |
| Eksik doc_id | 0 |
| Type eksigi olan doc_id/type | 0 |

Eksik doc_id listesi:

```text
Yok
```

## Question Type Dagilimi

| Type | Sayi |
| --- | ---: |
| direct | 61 |
| natural | 61 |
| hard_negative | 61 |

## Category Dagilimi

- `HESAP_GUVENLIK`: 39
- `IADE`: 27
- `KAMPANYA_PUAN`: 33
- `KARGO_TESLIMAT`: 33
- `ODEME`: 24
- `SIPARIS`: 27

## Label Dogrulamasi

| Kontrol | Sonuc |
| --- | ---: |
| expected_doc_id invalid | 0 |
| expected_category mismatch | 0 |
| expected_subcategory mismatch | 0 |

## Duplicate / Conflict Sonucu

| Kontrol | Sonuc |
| --- | ---: |
| Duplicate normalized question | 0 |
| Same question different label conflict | 0 |

## Hard-negative Coverage Sonucu

Zorunlu hard-negative ciftleri kapsanan sayi: 10 / 10

Eksik cift listesi:

```text
Yok
```

Kapsanan zorunlu ciftler:

```text
PAYMENT_FAILED_001 <-> PAYMENT_CHARGED_ORDER_NOT_CREATED_001
SIPARIS_ORDER_CANCEL_001 <-> IADE_TALEBI_OLUSTURMA_001
KUPON_GECERSIZ_HATASI_001 <-> MINIMUM_SEPET_TUTARI_001
SHIPPING_DELIVERED_NOT_RECEIVED_001 <-> SHIPPING_DELIVERY_FAILED_001
ACCOUNT_LOGIN_ISSUE_001 <-> PASSWORD_RESET_001
SHIPPING_TRACKING_001 <-> SIPARIS_ORDER_TRACKING_001
PAYMENT_REFUND_001 <-> IADE_UCRETININ_HESABA_GECMESI_001
IADE_SONRASI_PUAN_DURUMU_001 <-> PAYMENT_REFUND_001
SHIPPING_DELAYED_DELIVERY_001 <-> SHIPPING_DELIVERED_NOT_RECEIVED_001
SUSPICIOUS_LOGIN_ALERT_001 <-> UNAUTHORIZED_ORDER_PAYMENT_001
```

## Genel Karar

PASS

## Notlar

- Sorular Turkce ve kullanici agziyla yazildi.
- JSONL UTF-8 olarak yazildi; `ensure_ascii=False` kullanildi.
- Her satir yalnizca retrieval olcumu icin soru ve expected label icerir; cevap uretilmedi.
- `confusable_with` alani hard-negative sorularda beklenen dokumanla karisabilecek doc_id bilgisini tasir.
