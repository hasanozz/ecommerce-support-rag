# RAG Retrieval Failure Analysis Report

Tarih: 2026-06-26

## Kapsam

Bu rapor, calistirilmis retrieval benchmark sonucundaki 5 failure icin neden analizi yapar. Bu asamada RAG JSON, chunk, kod, DB, ingest, embedding, benchmark, test, git veya pip islemi yapilmadi.

Kullanilan kaynaklar:

- `backend/tests/fixtures/retrieval_benchmark.json`
- `output/rag_benchmark/rag_retrieval_benchmark_labels.json`
- `output/rag_benchmark/rag_retrieval_benchmark_questions.jsonl`
- `rag_documents_final/*.json`
- `rag_chunks/rag_chunks_clean.jsonl`

## Genel Skor Ozeti

| Metrik | Deger | Yorum |
| --- | ---: | --- |
| case_count | 183 | 61 doc_id x 3 soru kapsami tamam |
| top_1 | 0.7814 | Orta-iyi; ilk sirada dogru dokuman orani iyilestirilebilir |
| top_3 | 0.9727 | Guclu; sadece 5 case Top3 disinda kalmis |
| mrr | 0.8752 | Genel siralama kalitesi iyi |
| failures | 5 | Failure orani yaklasik %2.73 |

Genel yorum:

- Top3 skoru yuksek oldugu icin retrieval seti genel olarak kullanilabilir durumda.
- Failure'larin iki tanesi hic sonuc donmemis, uc tanesi yanlis dokumanlara gitmis.
- Hic sonuc donmeyen iki case, kaynak dokumanda birebir kullanici ifadesi bulunmasina ragmen bos dondugu icin threshold/aktif ingest/embedding davranisi acisindan kontrol edilmelidir.

## Failure Tablosu

| # | Query | Expected doc_id | Ranked doc_ids | Failure type | Kisa neden |
| ---: | --- | --- | --- | --- | --- |
| 1 | Şifremi unuttum. | `PASSWORD_RESET_001` | Yok | `RETRIEVAL_THRESHOLD_ISSUE` | Beklenen dokumanda query birebir var; buna ragmen sonuc yok |
| 2 | Ben bu siparişi vermedim. | `UNAUTHORIZED_ORDER_PAYMENT_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | `DOC_SEMANTIC_OVERLAP` | Siparis/odeme terimleri odeme dokumaniyla anlamsal cakismis |
| 3 | İadem neden reddedildi? | `IADE_REDDI_NEDENLERI_001` | Yok | `RETRIEVAL_THRESHOLD_ISSUE` | Beklenen dokumanda query birebir var; buna ragmen sonuc yok |
| 4 | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | `KAMPANYA_KULLANIMI_001` | `KUPON_KODU_KULLANIMI_001`, `KAMPANYALARIN_BIRLESTIRILMESI_001`, `KAMPANYA_KOSULLARI_001` | `BENCHMARK_QUERY_WEAK` | Query confusable doc adini bastirarak basliyor; embedding negasyonu anlayamayabilir |
| 5 | Siparişimden puan gelmedi. | `PUAN_KAZANMA_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001`, `PAYMENT_FAILED_001`, `IADE_SONRASI_PUAN_DURUMU_001` | `DOC_SEMANTIC_OVERLAP` | “siparis/gelmedi” odeme-siparis problemleriyle, “puan” iade sonrasi puanla cakismis |

## Tekil Failure Analizi

### 1. PASSWORD_RESET_001

Query:

```text
Şifremi unuttum.
```

Beklenen dokuman:

- `PASSWORD_RESET_001`
- Title: `Şifre Sıfırlama`
- Category: `HESAP_GUVENLIK`
- Subcategory: `SIFRE_SIFIRLAMA`

Kaynak bulgu:

- `kullanici_ifadeleri` icinde `Şifremi unuttum.` birebir var.
- Yeni chunk/context tarafinda query terimleri beklenen dokumanda bulunuyor.
- Ranked sonuc listesi bos.

Siniflandirma:

```text
RETRIEVAL_THRESHOLD_ISSUE
```

Oneri:

- Benchmark query degistirilmemeli; soru dogal ve dogru.
- Search_text/kullanici_ifadeleri icin ek zorunlu degisiklik yok; ifade zaten var.
- Ingest/aktif embedding config ve retrieval score threshold etkisi ayrica kontrol edilmeli.

### 2. UNAUTHORIZED_ORDER_PAYMENT_001

Query:

```text
Ben bu siparişi vermedim.
```

Beklenen dokuman:

- `UNAUTHORIZED_ORDER_PAYMENT_001`
- Title: `Yetkisiz Sipariş / Ödeme Bildirimi`

Donen dokuman:

- `PAYMENT_CHARGED_ORDER_NOT_CREATED_001`
- Title: `Karttan Para Çekildi Ama Sipariş Oluşmadı`

Kaynak bulgu:

- Beklenen dokumanda query birebir `kullanici_ifadeleri` icinde var.
- Donen dokuman siparis/odeme terimleri nedeniyle anlamsal olarak yakin ama senaryo farkli.
- Beklenen dokuman hesap guvenligi/yetkisiz islem, donen dokuman odeme-siparis olusmama senaryosu.

Siniflandirma:

```text
DOC_SEMANTIC_OVERLAP
```

Oneri:

- Benchmark query degistirilmemeli; kullanici agzina uygun ve net.
- Search_text tarafinda `UNAUTHORIZED_ORDER_PAYMENT_001` icin “ben bu siparişi vermedim”, “bana ait olmayan sipariş”, “yetkisiz sipariş oluşturulmuş” ifadeleri daha guclu tutulmali. Kaynakta zaten mevcut oldugu icin once aktif ingest/embedding setinin guncelligi kontrol edilmeli.
- Donen `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` ile semantic overlap kabul edilmeli ama beklenen ayrim iyilestirilmeli.

### 3. IADE_REDDI_NEDENLERI_001

Query:

```text
İadem neden reddedildi?
```

Beklenen dokuman:

- `IADE_REDDI_NEDENLERI_001`
- Title: `İade Reddi`

Kaynak bulgu:

- `kullanici_ifadeleri` icinde `İadem neden reddedildi?` birebir var.
- Ranked sonuc listesi bos.

Siniflandirma:

```text
RETRIEVAL_THRESHOLD_ISSUE
```

Oneri:

- Benchmark query degistirilmemeli.
- Search_text/kullanici_ifadeleri icin ek zorunlu degisiklik yok; ifade zaten var.
- Threshold ve aktif ingest/embedding uyumu kontrol edilmeli.

### 4. KAMPANYA_KULLANIMI_001

Query:

```text
Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum.
```

Beklenen dokuman:

- `KAMPANYA_KULLANIMI_001`

Donen dokumanlar:

- `KUPON_KODU_KULLANIMI_001`
- `KAMPANYALARIN_BIRLESTIRILMESI_001`
- `KAMPANYA_KOSULLARI_001`

Kaynak bulgu:

- Query, confusable dokuman adini (`Kupon Kodu Kullanımı`) en basta ve acik sekilde iceriyor.
- Embedding tabanli retrieval negasyon/“değil” ifadesini kesin mantik olarak islemeyebilir.
- Bu, benchmark sorusunun retrieval icin fazla sentetik ve confusable terimi fazla baskin tasidigi bir ornek.

Siniflandirma:

```text
BENCHMARK_QUERY_WEAK
```

Oneri:

- Benchmark query duzeltilmeli.
- Daha dogal hard-negative soru onerisi:

```text
Kupon kodu girmeden, sepetteki kampanyanın hangi ürünlere uygulandığını öğrenmek istiyorum.
```

- Search_text degisikligi zorunlu degil.

### 5. PUAN_KAZANMA_001

Query:

```text
Siparişimden puan gelmedi.
```

Beklenen dokuman:

- `PUAN_KAZANMA_001`

Donen dokumanlar:

- `PAYMENT_CHARGED_ORDER_NOT_CREATED_001`
- `PAYMENT_FAILED_001`
- `IADE_SONRASI_PUAN_DURUMU_001`

Kaynak bulgu:

- Beklenen dokumanda query birebir `kullanici_ifadeleri` icinde var.
- `sipariş` + `gelmedi` terimleri odeme/siparis olusmama dokumaniyla cakismis.
- `puan` terimi iade sonrasi puan dokumaniyla cakismis.

Siniflandirma:

```text
DOC_SEMANTIC_OVERLAP
```

Oneri:

- Benchmark query kabul edilebilir; dogal kullanici dili.
- Search_text tarafinda `PUAN_KAZANMA_001` icin “sipariş puanı kazanma”, “siparişten puan yansımadı”, “alışveriş puanı gelmedi” varyasyonlari guclendirilebilir.
- Eger sadece benchmark stabilitesi hedeflenirse query daha net hale getirilebilir:

```text
Siparişimden kampanya puanı hesabıma eklenmedi.
```

## Failure Type Dagilimi

| Failure type | Sayi |
| --- | ---: |
| `RETRIEVAL_THRESHOLD_ISSUE` | 2 |
| `DOC_SEMANTIC_OVERLAP` | 2 |
| `BENCHMARK_QUERY_WEAK` | 1 |
| `SEARCH_TEXT_WEAK` | 0 |
| `METADATA_WEAK` | 0 |

En baskin sebepler:

- `RETRIEVAL_THRESHOLD_ISSUE`
- `DOC_SEMANTIC_OVERLAP`

## Search_text Iyilestirme Onerileri

Zorunlu degil ama faydali olabilecek doc_id listesi:

- `UNAUTHORIZED_ORDER_PAYMENT_001`
  - “ben bu siparişi vermedim”
  - “bana ait olmayan sipariş”
  - “yetkisiz sipariş oluşturulmuş”
- `PUAN_KAZANMA_001`
  - “sipariş puanı gelmedi”
  - “siparişten puan yansımadı”
  - “alışveriş puanı hesabıma eklenmedi”

Not:

- Bu ifadelerin bir kismi kaynakta zaten var. Bu nedenle once aktif DB ingest ve embedding setinin 61 final_safe kaynakla guncel oldugu dogrulanmalidir.

## Benchmark Query Duzeltme Onerileri

Duzeltilmesi onerilen benchmark query:

| Mevcut query | Beklenen doc_id | Onerilen query |
| --- | --- | --- |
| Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | `KAMPANYA_KULLANIMI_001` | Kupon kodu girmeden, sepetteki kampanyanın hangi ürünlere uygulandığını öğrenmek istiyorum. |

Opsiyonel netlestirme:

| Mevcut query | Beklenen doc_id | Onerilen query |
| --- | --- | --- |
| Siparişimden puan gelmedi. | `PUAN_KAZANMA_001` | Siparişimden kampanya puanı hesabıma eklenmedi. |

## Karisan Doc_id Ciftleri

Best score degerleri benchmark sonucu icinde bu mesajda verilmedigi icin `best_score` alanlari `verilmedi` olarak raporlandi.

| expected_doc_id | returned_doc_id | query | best_score | Muhtemel sebep |
| --- | --- | --- | --- | --- |
| `UNAUTHORIZED_ORDER_PAYMENT_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Ben bu siparişi vermedim. | verilmedi | Siparis/odeme anlamsal overlap |
| `KAMPANYA_KULLANIMI_001` | `KUPON_KODU_KULLANIMI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Query confusable doc adini baskin tasiyor |
| `KAMPANYA_KULLANIMI_001` | `KAMPANYALARIN_BIRLESTIRILMESI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Kampanya genel terimi overlap |
| `KAMPANYA_KULLANIMI_001` | `KAMPANYA_KOSULLARI_001` | Kupon Kodu Kullanımı değil, Kampanya Kullanımı konusunda destek istiyorum. | verilmedi | Kampanya genel terimi overlap |
| `PUAN_KAZANMA_001` | `PAYMENT_CHARGED_ORDER_NOT_CREATED_001` | Siparişimden puan gelmedi. | verilmedi | “sipariş/gelmedi” odeme-siparis problemine kaymis |
| `PUAN_KAZANMA_001` | `PAYMENT_FAILED_001` | Siparişimden puan gelmedi. | verilmedi | Siparis/odeme semantik kayma |
| `PUAN_KAZANMA_001` | `IADE_SONRASI_PUAN_DURUMU_001` | Siparişimden puan gelmedi. | verilmedi | Puan senaryolari overlap |

## Genel Karar

WARNING

Gerekce:

- Top3 skoru yuksek ve failure sayisi dusuk.
- Ancak iki exact-match kullanici ifadesinde hic sonuc donmemesi threshold/aktif ingest/embedding kontrolu gerektirir.
- Bir benchmark hard-negative sorgusu sentetik “X değil Y” formu nedeniyle zayif.
- Search_text degisikligi dusunulebilir ama once aktif DB/embedding setinin guncel oldugu dogrulanmalidir.
