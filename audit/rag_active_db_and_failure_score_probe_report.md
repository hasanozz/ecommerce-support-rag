# RAG Active DB and Failure Score Probe Report

## Kapsam
Aktif DB 61 final_safe dokuman ve 366 chunk seti icin read-only dogrulandi. 5 failure query icin threshold oncesi ilk 30 chunk adayi incelendi. SECRETS_FILE icerigi yazdirilmadi.

## Kullanilan Ayarlar
- Embedding provider: `sentence_transformers`
- Embedding model: `BAAI/bge-m3`
- Embedding dimension: `1024`
- Embedding device: `cpu`
- Retrieval threshold referansi: `0.55`

## Aktif DB Dogrulamasi
- Document count: `61`
- Chunk count: `366`
- Unique doc_id count: `61`
- Kaynak doc_id count: `61`
- Her doc_id 6 chunk: `PASS`
- Missing source doc_id: `0`
- Extra old doc_id: `0`
- Active DB decision: `ACTIVE_DB_OK`

## Failure Raw Score Tablosu
| Query | Expected doc_id | Expected top30? | Best raw score | 0.55 durumu | Expected rank | Top doc | Diagnosis |
|---|---|---:|---:|---|---:|---|---|
| Şifremi unuttum. | `PASSWORD_RESET_001` | `True` | `0.524280` | `below` | `1` | `PASSWORD_RESET_001` | `THRESHOLD_ISSUE` |
| Ben bu siparişi vermedim. | `UNAUTHORIZED_ORDER_PAYMENT_001` | `True` | `0.535762` | `below` | `2` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | `THRESHOLD_ISSUE` |
| İadem neden reddedildi? | `IADE_REDDI_NEDENLERI_001` | `True` | `0.508167` | `below` | `1` | `IADE_REDDI_NEDENLERI_001` | `THRESHOLD_ISSUE` |
| Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | `KAMPANYA_KULLANIMI_001` | `True` | `0.609950` | `above_or_equal` | `5` | `KUPON_KODU_KULLANIMI_001` | `BENCHMARK_QUERY_WEAK` |
| Siparişimden puan gelmedi. | `PUAN_KAZANMA_001` | `True` | `0.571987` | `above_or_equal` | `5` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | `SEMANTIC_OVERLAP` |

## Top 10 Doc Score Ozeti
### Şifremi unuttum.
Expected: `PASSWORD_RESET_001`

| Rank | doc_id | score | chunk_id | section |
|---:|---|---:|---|---|
| 1 | `PASSWORD_RESET_001` | `0.524280` | `PASSWORD_RESET_001__ISTISNALAR` | `istisnalar` |
| 2 | `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.460776` | `UNAUTHORIZED_ORDER_PAYMENT_001__DESTEK_GEREKTIREN_DURUMLAR` | `destek_gerektiren_durumlar` |
| 3 | `ACCOUNT_LOGIN_ISSUE_001` | `0.449279` | `ACCOUNT_LOGIN_ISSUE_001__KOSULLAR` | `kosullar` |
| 4 | `PERSONAL_DATA_SECURITY_001` | `0.444199` | `PERSONAL_DATA_SECURITY_001__STANDART_YANIT` | `standart_yanit` |
| 5 | `SUSPICIOUS_LOGIN_ALERT_001` | `0.435109` | `SUSPICIOUS_LOGIN_ALERT_001__KOSULLAR` | `kosullar` |

### Ben bu siparişi vermedim.
Expected: `UNAUTHORIZED_ORDER_PAYMENT_001`

| Rank | doc_id | score | chunk_id | section |
|---:|---|---:|---|---|
| 1 | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | `0.557503` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001__TANIM` | `tanim` |
| 2 | `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `UNAUTHORIZED_ORDER_PAYMENT_001__DESTEK_GEREKTIREN_DURUMLAR` | `destek_gerektiren_durumlar` |
| 3 | `SIPARIS_ORDER_CANCEL_001` | `0.513779` | `SIPARIS_ORDER_CANCEL_001__ISTISNALAR` | `istisnalar` |
| 4 | `PAYMENT_FAILED_001` | `0.507108` | `PAYMENT_FAILED_001__ADIMLAR` | `adimlar` |
| 5 | `SHIPPING_DELIVERY_FAILED_001` | `0.506972` | `SHIPPING_DELIVERY_FAILED_001__TANIM` | `tanim` |

### İadem neden reddedildi?
Expected: `IADE_REDDI_NEDENLERI_001`

| Rank | doc_id | score | chunk_id | section |
|---:|---|---:|---|---|
| 1 | `IADE_REDDI_NEDENLERI_001` | `0.508167` | `IADE_REDDI_NEDENLERI_001__STANDART_YANIT` | `standart_yanit` |
| 2 | `SHIPPING_DELIVERY_FAILED_001` | `0.352161` | `SHIPPING_DELIVERY_FAILED_001__STANDART_YANIT` | `standart_yanit` |
| 3 | `PAYMENT_FAILED_001` | `0.348621` | `PAYMENT_FAILED_001__ISTISNALAR` | `istisnalar` |
| 4 | `IADE_TALEBI_OLUSTURMA_001` | `0.334620` | `IADE_TALEBI_OLUSTURMA_001__ISTISNALAR` | `istisnalar` |
| 5 | `PAYMENT_REFUND_001` | `0.326671` | `PAYMENT_REFUND_001__ADIMLAR` | `adimlar` |

### Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum.
Expected: `KAMPANYA_KULLANIMI_001`

| Rank | doc_id | score | chunk_id | section |
|---:|---|---:|---|---|
| 1 | `KUPON_KODU_KULLANIMI_001` | `0.646234` | `KUPON_KODU_KULLANIMI_001__TANIM` | `tanim` |
| 2 | `KAMPANYALARIN_BIRLESTIRILMESI_001` | `0.619814` | `KAMPANYALARIN_BIRLESTIRILMESI_001__TANIM` | `tanim` |
| 3 | `KAMPANYA_KOSULLARI_001` | `0.617151` | `KAMPANYA_KOSULLARI_001__TANIM` | `tanim` |
| 4 | `KUPON_GECERSIZ_HATASI_001` | `0.612511` | `KUPON_GECERSIZ_HATASI_001__ISTISNALAR` | `istisnalar` |
| 5 | `KAMPANYA_KULLANIMI_001` | `0.609950` | `KAMPANYA_KULLANIMI_001__ISTISNALAR` | `istisnalar` |

### Siparişimden puan gelmedi.
Expected: `PUAN_KAZANMA_001`

| Rank | doc_id | score | chunk_id | section |
|---:|---|---:|---|---|
| 1 | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | `0.625235` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001__TANIM` | `tanim` |
| 2 | `PAYMENT_FAILED_001` | `0.584028` | `PAYMENT_FAILED_001__KOSULLAR` | `kosullar` |
| 3 | `IADE_SONRASI_PUAN_DURUMU_001` | `0.578141` | `IADE_SONRASI_PUAN_DURUMU_001__ADIMLAR` | `adimlar` |
| 4 | `SHIPPING_DELIVERY_FAILED_001` | `0.572523` | `SHIPPING_DELIVERY_FAILED_001__ADIMLAR` | `adimlar` |
| 5 | `PUAN_KAZANMA_001` | `0.571987` | `PUAN_KAZANMA_001__ADIMLAR` | `adimlar` |

## Yorum
- En az bir failure icin expected doc top30 adaylarinda var ama 0.55 threshold altinda kaliyor; threshold etkisi vardir.
- En az bir failure icin expected doc threshold ustunde olsa bile rakip dokumanlar daha yuksek skor aliyor; semantik cakisma var.
- En az bir failure query, beklenen dokumani olcerken rakip dokuman adini da acikca kullandigi icin benchmark query zayifligi tasiyor.

## Genel Karar
ACTIVE_DB_OK

## Sonraki Onerilen Adim
Raw score bulgularina gore yalnizca threshold kaynakli case varsa threshold ayari degerlendirilmeli; top30 miss veya semantik cakisma olan case'lerde once benchmark query ve search_text/kullanici_ifadeleri netlestirilmelidir.
