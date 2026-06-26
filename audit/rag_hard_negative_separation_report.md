# RAG Hard-negative Separation Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, zorunlu hard-negative ciftlerinin benchmark seti icinde kapsanip kapsanmadigini ve verilen Top3 failure listesinde bu ciftlerden failure olup olmadigini analiz eder.

Bu asamada RAG JSON, chunk, kod, DB, ingest, embedding, benchmark, test, git veya pip islemi yapilmadi.

## Zorunlu 10 Hard-negative Cift Coverage

| # | Hard-negative cift | Coverage | Failure |
| ---: | --- | --- | --- |
| 1 | `PAYMENT_FAILED_001` ↔ `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Var | Yok |
| 2 | `SIPARIS_ORDER_CANCEL_001` ↔ `IADE_TALEBI_OLUSTURMA_001` | Var | Yok |
| 3 | `KUPON_GECERSIZ_HATASI_001` ↔ `MINIMUM_SEPET_TUTARI_001` | Var | Yok |
| 4 | `SHIPPING_DELIVERED_NOT_RECEIVED_001` ↔ `SHIPPING_DELIVERY_FAILED_001` | Var | Yok |
| 5 | `ACCOUNT_LOGIN_ISSUE_001` ↔ `PASSWORD_RESET_001` | Var | Yok |
| 6 | `SHIPPING_TRACKING_001` ↔ `SIPARIS_ORDER_TRACKING_001` | Var | Yok |
| 7 | `PAYMENT_REFUND_001` ↔ `IADE_UCRETININ_HESABA_GECMESI_001` | Var | Yok |
| 8 | `IADE_SONRASI_PUAN_DURUMU_001` ↔ `PAYMENT_REFUND_001` | Var | Yok |
| 9 | `SHIPPING_DELAYED_DELIVERY_001` ↔ `SHIPPING_DELIVERED_NOT_RECEIVED_001` | Var | Yok |
| 10 | `SUSPICIOUS_LOGIN_ALERT_001` ↔ `UNAUTHORIZED_ORDER_PAYMENT_001` | Var | Yok |

Coverage sonucu:

```text
10 / 10 PASS
```

## Failure Olan Hard-negative Ciftler

Zorunlu 10 hard-negative cift icinde verilen Top3 failure listesine dusen case yok.

```text
Yok
```

## Basarili Ayrilan Hard-negative Ciftler

Verilen failure listesine gore zorunlu ciftlerin tamami Top3 seviyesinde basarili ayrilmis kabul edilir:

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

Not:

- Bu rapor sadece verilen Top3 failure listesine dayanir.
- Top1 seviyesinde ayrim hatasi olup olmadigi, tam benchmark per-case sonucu verilmedigi icin bu raporda kesin analiz edilemez.

## Zorunlu Liste Disi Hard-negative Failure

Verilen failure listesinde bir hard-negative query failure'i var; ancak bu cift zorunlu 10 cift listesinde degil:

| Query | Expected | Returned | Sebep |
| --- | --- | --- | --- |
| Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | `KAMPANYA_KULLANIMI_001` | `KUPON_KODU_KULLANIMI_001`, `KAMPANYALARIN_BIRLESTIRILMESI_001`, `KAMPANYA_KOSULLARI_001` | Query confusable doc adini baskin tasiyor; benchmark query zayif |

Oneri:

- Bu hard-negative query daha dogal ve daha az “X değil Y” formunda yazilmali.
- Onerilen yeni query:

```text
Kupon kodu girmeden, sepetteki kampanyanın hangi ürünlere uygulandığını öğrenmek istiyorum.
```

## Karisan Doc_id Ciftleri

Best score degerleri benchmark sonucu icinde bu mesajda verilmedigi icin `best_score` alanlari `verilmedi` olarak raporlandi.

| expected_doc_id | returned_doc_id | query | best_score | Muhtemel sebep |
| --- | --- | --- | --- | --- |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Ben bu siparişi vermedim. | verilmedi | Siparis/odeme anlamsal overlap |
| `KAMPANYA_KULLANIMI_001` | `KUPON_KODU_KULLANIMI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Hard-negative query confusable doc adini baskin tasiyor |
| `KAMPANYA_KULLANIMI_001` | `KAMPANYALARIN_BIRLESTIRILMESI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Kampanya genel terimi overlap |
| `KAMPANYA_KULLANIMI_001` | `KAMPANYA_KOSULLARI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Kampanya genel terimi overlap |
| `PUAN_KAZANMA_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Siparişimden puan gelmedi. | verilmedi | “sipariş/gelmedi” odeme-siparis problemine kaymis |
| `PUAN_KAZANMA_001` | `PAYMENT_FAILED_001` | Siparişimden puan gelmedi. | verilmedi | Siparis/odeme semantik kayma |
| `PUAN_KAZANMA_001` | `IADE_SONRASI_PUAN_DURUMU_001` | Siparişimden puan gelmedi. | verilmedi | Puan senaryolari overlap |

## Genel Karar

WARNING

Gerekce:

- Zorunlu 10 hard-negative ciftin coverage'i tam.
- Zorunlu ciftlerden Top3 failure yok.
- Ancak zorunlu liste disinda bir hard-negative query failure'i var.
- Hard-negative ayrimi genel olarak iyi, fakat benchmark query yaziminda “X değil Y” formu bazi ciftlerde yaniltici olabilir.
