# RAG Threshold Dry-Run Comparison Report

## Kapsam
183 benchmark query icin benchmark scripti calistirilmadan read-only DB + embedding dry-run yapildi. Candidate limit `30`, max_documents `3` olarak simule edildi. SECRETS_FILE icerigi yazdirilmadi.

## Aktif DB
- Documents: `61`
- Chunks: `366`
- Unique doc_id: `61`

## Threshold Karsilastirmasi
| Threshold | Top1 | Top3 | MRR | Failure | Empty | Low-score false positive | Onceki 5 failure Top3 | Onceki 5 failure Top1 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.55 | 0.7814 | 0.9727 | 0.8752 | 5 | 2 | 0 | 0/5 | 0/5 |
| 0.53 | 0.7814 | 0.9781 | 0.8780 | 4 | 2 | 9 | 1/5 | 0/5 |
| 0.52 | 0.7869 | 0.9836 | 0.8834 | 3 | 1 | 13 | 2/5 | 1/5 |
| 0.51 | 0.7869 | 0.9836 | 0.8834 | 3 | 1 | 17 | 2/5 | 1/5 |
| 0.50 | 0.7923 | 0.9891 | 0.8889 | 2 | 0 | 18 | 3/5 | 2/5 |
| 0.48 | 0.7923 | 0.9891 | 0.8889 | 2 | 0 | 20 | 3/5 | 2/5 |

## Onceki 5 Failure Durumu
### Threshold 0.55
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `fail` | `` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `fail` | `` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

### Threshold 0.53
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `fail` | `` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `top3` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, UNAUTHORIZED_ORDER_PAYMENT_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `fail` | `` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

### Threshold 0.52
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `top1` | `PASSWORD_RESET_001` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `top3` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, UNAUTHORIZED_ORDER_PAYMENT_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `fail` | `` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

### Threshold 0.51
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `top1` | `PASSWORD_RESET_001` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `top3` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, UNAUTHORIZED_ORDER_PAYMENT_001, SIPARIS_ORDER_CANCEL_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `fail` | `` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

### Threshold 0.50
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `top1` | `PASSWORD_RESET_001` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `top3` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, UNAUTHORIZED_ORDER_PAYMENT_001, SIPARIS_ORDER_CANCEL_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `top1` | `IADE_REDDI_NEDENLERI_001` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

### Threshold 0.48
| Expected doc_id | Best raw score | Raw rank | Status | Ranked doc_ids |
|---|---:|---:|---|---|
| `PASSWORD_RESET_001` | `0.524280` | `1` | `top1` | `PASSWORD_RESET_001` |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `0.535762` | `2` | `top3` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, UNAUTHORIZED_ORDER_PAYMENT_001, SIPARIS_ORDER_CANCEL_001` |
| `IADE_REDDI_NEDENLERI_001` | `0.508167` | `1` | `top1` | `IADE_REDDI_NEDENLERI_001` |
| `KAMPANYA_KULLANIMI_001` | `0.609950` | `5` | `fail` | `KUPON_KODU_KULLANIMI_001, KAMPANYALARIN_BIRLESTIRILMESI_001, KAMPANYA_KOSULLARI_001` |
| `PUAN_KAZANMA_001` | `0.571987` | `5` | `fail` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001, PAYMENT_FAILED_001, IADE_SONRASI_PUAN_DURUMU_001` |

## Risk Analizi
- Threshold dusurmek empty result sayisini azaltir; ozellikle kisa exact-match sorgular icin fayda saglar.
- Threshold 0.50 ve 0.48 seviyelerinde dusuk skorlu yanlis pozitiflerin acilma riski artar.
- KAMPANYA_KULLANIMI_001 failure'i threshold kaynakli degil; query rakip kupon dokumanini acikca tetikliyor.
- PUAN_KAZANMA_001 failure'i threshold kaynakli degil; expected doc threshold ustunde ama rakip odeme/iade dokumanlari daha yuksek skor aliyor.

## Oneri
- En iyi metrik threshold adayi: `0.50`
- Pratik onerilen threshold: `0.52`
- 0.52, exact-match bos sonuc riskini azaltirken 0.50/0.48 kadar dusuk skorlu genisleme yaratmadigi icin daha kontrollu adaydir.
- Sadece kisa query icin ozel threshold teknik olarak dusunulebilir, ancak bu asamada config/kod degisikligi yapmadan once 0.52 genel threshold adayi staging benchmark ile dogrulanmalidir.

## Genel Karar
WARNING

## Sonraki Onerilen Adim
Kod/config degistirmeden once 0.52 threshold adayini staging ortamda benchmark scriptiyle dogrula; ardindan KAMPANYA benchmark query'sini ve PUAN_KAZANMA search_text/kullanici_ifadelerini ayri ele al.
