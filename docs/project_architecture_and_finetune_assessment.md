# DestekAI Proje Mimarisi ve Fine-Tuning Değerlendirmesi

## 1. Yönetici özeti

DestekAI, e-ticaret müşteri destek senaryoları için çalışan bir yazılım MVP'sidir.
Sistemde Google OAuth, kullanıcı oturumları, konuşma geçmişi, RAG tabanlı kaynak
bulma, Gemini ile sorgu yeniden yazma ve cevap üretme, geri bildirim, ticket,
admin ticket yönetimi, e-posta outbox'ı ve temel gözlemlenebilirlik bulunmaktadır.

23 Haziran 2026 tarihli doğrulama:

- PostgreSQL ve pgvector Docker servisi sağlıklı.
- Alembic migration seviyesi `0003 (head)`.
- 70 bilgi tabanı dokümanı ve 609 chunk mevcut.
- 70 benzersiz subcategory bulunuyor.
- Runtime verisinde 1 kullanıcı, 6 konuşma, 2 feedback ve 1 ticket var.
- 21 backend testi başarılı.

Yazılım tarafı MVP bakımından büyük ölçüde tamamlanmıştır. Bundan sonraki ana
kalite artışı iki ayrı ekip çalışmasına bağlıdır:

1. Gerçek embedding, contextual retrieval ve reranking içeren yeni RAG katmanı.
2. Qwen3-8B + QLoRA ile eğitilecek güvenlik ve niyet classifier'ı.

Fine-tuned model son kullanıcıya cevap üretmemelidir. Modelin görevi, güvenli
orijinal kullanıcı mesajını sınıflandırarak pipeline'ın sonraki adımını
belirlemektir.

---

## 2. Mevcut sistem mimarisi

```text
Tarayıcı
   │
   ├── Google OAuth / cookie session
   │
   ▼
FastAPI
   │
   ├── Input uzunluk, HTML, Unicode ve jailbreak kontrolü
   ├── PII maskeleme
   ├── Rule-based classifier (mevcut varsayılan)
   ├── Gemini Flash-Lite query rewriting
   ├── pgvector retrieval
   ├── Passthrough reranker
   ├── Context builder
   ├── Gemini Flash-Lite answer generation
   ├── Output guard ve PII maskeleme
   └── PostgreSQL kayıtları
        ├── kullanıcı ve oturum
        ├── konuşma ve mesaj
        ├── RAG run metrikleri
        ├── feedback ve benzer çözümler
        ├── ticket ve durum geçmişi
        └── e-posta outbox
```

Mevcut temel pipeline sırası:

```text
sanitize_query
→ mask_pii
→ classifier
→ query rewrite
→ retrieval
→ reranker
→ context
→ Gemini answer
→ output guard
→ persistence
```

Bu sıra genel olarak doğrudur. Rewrite edilmiş soru classifier'a verilmemektedir.

---

## 3. Backend değerlendirmesi

### 3.1 Çalışan özellikler

- FastAPI uygulama ve health endpoint'i.
- PostgreSQL async bağlantısı ve pgvector.
- Alembic migrationları.
- Google OAuth Authorization Code akışı.
- İmzalı OAuth state kontrolü.
- Hashlenmiş session tokenları ve HttpOnly cookie.
- Kullanıcıya ait konuşma ve mesaj geçmişi.
- Rate limit kontrol noktaları.
- PII maskeleme.
- Prompt injection/jailbreak için temel regex kontrolü.
- Gemini system instruction ve user/context ayrımı.
- Structured JSON Gemini cevapları.
- Gemini 5xx retry ve güvenli fallback.
- Kaynakların ve RAG context'in mesajla saklanması.
- Olumlu/olumsuz feedback.
- Kullanıcı tarafından doğrudan ticket oluşturma.
- Admin ticket durum ve not güncelleme.
- Ticket durum geçmişi.
- SMTP başarısızlığının ticket oluşturmayı bozmaması için outbox yapısı.
- Token, maliyet, latency ve confidence bileşenlerinin `rag_runs` içinde tutulması.

### 3.2 Veritabanı

Ana tablolar:

- `users`
- `user_sessions`
- `conversations`
- `messages`
- `documents`
- `chunks`
- `rag_runs`
- `feedback`
- `similar_solutions`
- `similar_solution_impressions`
- `tickets`
- `ticket_status_history`
- `email_outbox`
- `embedding_ingests`

`rag_runs`, AI değerlendirmesi için uygun bir başlangıç sağlamaktadır:

- rewritten query
- retrieval sonuçları
- few-shot örnekleri
- model adı
- latency
- token kullanımı
- tahmini maliyet
- retrieval/reranker/classifier/composite confidence
- classification sonucu

### 3.3 Backend'in gelişime açık alanları

#### Rate limiter

Rate limiter process belleğinde tutulmaktadır. Backend yeniden başladığında
sıfırlanır ve birden fazla worker kullanıldığında workerlar ortak limit
uygulamaz. Production için Redis tabanlı dağıtık limiter gerekir.

#### Migration ve otomatik tablo oluşturma

Alembic bulunmasına rağmen `AUTO_CREATE_TABLES=true` varsayılandır. Production'da
yalnız Alembic kullanılmalı ve otomatik `create_all` kapatılmalıdır.

#### Pipeline dependency injection

`Retriever`, `Reranker` ve `Rewriter` protokolleri tanımlıdır; ancak
`SupportPipeline` somut servisleri kendi içinde oluşturmaktadır. Test edilebilirlik
ve ekiplerin bağımsız geliştirmesi için provider factory veya dependency injection
kullanılmalıdır.

#### Eski kod yolları

- Deprecated `/api/chat` endpoint'i hâlâ eski `ChatService` kullanıyor.
- `query_logs` tablosu eski RAG çekirdeğinden kalmış, yeni pipeline esas olarak
  `messages` ve `rag_runs` kullanıyor.
- README'de Ollama ve `multilingual-e5-large` varsayımları güncel kodla tam uyumlu
  değildir.

Bu eski yollar kaldırılmalı veya açıkça legacy olarak ayrılmalıdır.

#### Güvenlik kontrol sırası

`sanitize_query`, açık jailbreak mesajlarını classifier'dan önce HTTP 400 ile
reddetmektedir. Bu üretim güvenliği açısından güvenlidir; fakat fine-tuned modelin
jailbreak sınıflandırma kabiliyetini gerçek trafikte gözlemlemeyi engeller.

Önerilen yapı:

```text
normalize_input
→ deterministic security scanner
→ classifier
→ policy decision
```

Scanner, mesajı doğrudan yok etmek yerine güvenlik işaretleri üretmelidir.
Kesin engellenmesi gereken payloadlar erken reddedilebilir; diğer şüpheli
mesajlar classifier'a güvenli biçimde iletilmelidir.

#### Gözlemlenebilirlik

Metrik kolonları vardır ancak dashboard, alarm ve toplu raporlama yoktur.
Özellikle şu metrikler izlenmelidir:

- classifier fallback oranı
- invalid classifier output oranı
- retrieval boş sonuç oranı
- Gemini 429/5xx oranı
- p50/p95 pipeline latency
- kategori bazında ticket oranı
- false reject ve kullanıcı olumsuz feedback oranı

---

## 4. Frontend değerlendirmesi

Frontend framework kullanmadan HTML/CSS/JavaScript ile geliştirilmiştir.

Çalışan özellikler:

- Google login/logout.
- Kullanıcı bilgisi.
- Yeni konuşma.
- Mesaj gönderme ve AI cevabı.
- Kaynak listesi ve RAG context popup'ı.
- Sık sorulan sorular.
- Light/dark tema.
- Geçmiş konuşmalar.
- Kullanıcı ticketları.
- Admin ticket grid ve düzenleme görünümü.
- Feedback.
- Cevaptan bağımsız ticket açma.
- Benzer çözümler ve feedback.
- RAG context preview.
- Responsive kart gridleri.

Gelişime açık alanlar:

- Frontend state ve DOM üretimi tek büyük `app.js` dosyasındadır.
- Bileşen, router ve API client ayrımı bulunmamaktadır.
- Otomatik frontend testleri yoktur.
- Erişilebilirlik testi ve klavye odağı yönetimi sınırlıdır.
- Modal açıldığında focus trap uygulanmamaktadır.
- Mobil sidebar kodunun bir bölümü eski CSS yapısından kalmıştır.
- Runtime hata raporlama/telemetri yoktur.

MVP için mevcut yaklaşım yeterlidir. Özellik sayısı artarsa frontend'i küçük
modüllere ayırmak veya bir component framework'e geçirmek mantıklıdır; şu anda
zorunlu değildir.

---

## 5. Mevcut RAG değerlendirmesi

### 5.1 Veri

Mevcut bilgi tabanı:

| Kategori | Doküman |
|---|---:|
| HESAP_GUVENLIK | 13 |
| IADE | 12 |
| KAMPANYA_PUAN | 11 |
| KARGO_TESLIMAT | 11 |
| ODEME | 11 |
| SIPARIS | 12 |
| Toplam | 70 |

Her dokümanın subcategory değeri benzersizdir. Mevcut veri, classifier
subcategory taksonomisi için başlangıç kaynağı olarak kullanılabilir; ancak
70 subcategory'nin tamamını doğrudan ilk fine-tune sürümünde öğrenmek veri
yetersizliğine yol açabilir.

### 5.2 Chunking

Chunking section bazlıdır:

- amaç
- kapsam
- tanım
- genel bilgiler
- koşullar
- adımlar
- istisnalar
- süreç
- standart yanıt

Kısa amaç/kapsam/tanım bölümleri birleştirilebilir; uzun metinler 1600 karakter
civarında bölünür. Contextual content içinde kategori, alt kategori, doküman,
bölüm ve içerik bulunur.

### 5.3 Retrieval

Mevcut geliştirme verisi `hashing-sha256-v1` ile embed edilmiştir. Bu yalnız
altyapı testi içindir; semantik retrieval kalitesi düşüktür.

Mevcut retrieval:

- pgvector cosine distance
- ilk 30 chunk
- doküman bazında gruplama
- en fazla 3 doküman
- doküman başına en fazla 6 bölüm
- hashing için ayrı düşük threshold

Reranker şu anda `PassthroughReranker` durumundadır. Contextual retrieval TODO
olarak işaretlenmiştir.

### 5.4 RAG geliştiricisinin değiştireceği noktalar

Yeni RAG mümkün olduğunca aşağıdaki sözleşmeleri korumalıdır:

```text
Retriever.grouped_search(...)
Reranker.rerank(...)
ContextBuilder.build(...)
GroupedDocument
```

Chat pipeline'ın beklediği doküman sonucu:

```json
{
  "doc_id": "...",
  "title": "...",
  "category": "...",
  "subcategory": "...",
  "best_score": 0.82,
  "matched_sections": [],
  "combined_context": "..."
}
```

Önerilen RAG iyileştirmeleri:

1. `bge-m3`, `multilingual-e5-large` veya ekip tarafından doğrulanan gerçek
   multilingual embedding.
2. `vector(1024)` uyumluluk kontrolünün korunması.
3. Yeni dataset ile tam re-ingest.
4. Hybrid lexical + vector retrieval.
5. Category filtresinin yalnız classifier yeterince güvenliyse uygulanması.
6. Cross-encoder reranker.
7. Query rewriting değerlendirmesi.
8. Contextual retrieval.
9. Offline golden query test seti.
10. Recall@k, MRR, nDCG ve answer-groundedness ölçümü.

`/api/rag/search` debug endpoint'i korunmalıdır. Production'da admin veya teknik
rol ile sınırlandırılmalıdır.

---

## 6. Fine-tuned classifier için önerilen görev

Qwen modeli bir sohbet veya cevap modeli olarak kullanılmamalıdır. Görevi:

```text
Güvenli orijinal kullanıcı mesajı
→ güvenlik sınıfı
→ konu kategorisi
→ alt kategori
→ öncelik
→ beklenen aksiyon
```

Model şu işleri yapmamalıdır:

- Kullanıcıya cevap üretmek.
- Sorguyu rewrite etmek.
- RAG araması yapmak.
- Ticketı doğrudan oluşturmak.
- Gemini veya backend güvenlik kontrollerinin yerine geçmek.

### 6.1 Önerilen çıktı sözleşmesi

Mevcut sözleşmeye `security_label` eklenmelidir:

```json
{
  "category": "SIPARIS",
  "subcategory": "SIPARIS_IPTALI",
  "security_label": "SAFE",
  "priority": "MEDIUM",
  "expected_action": "RAG_ANSWER",
  "confidence": null,
  "model_version": "qwen3-8b-qlora-classifier-v1"
}
```

Önerilen security enum:

```text
SAFE
PROMPT_INJECTION
JAILBREAK
SECRET_REQUEST
OUT_OF_SCOPE
ABUSIVE
PII_RISK
```

`PII_RISK`, kart/kimlik/telefon/e-posta gibi bilgileri içeren ancak konu olarak
geçerli destek mesajlarını belirtir. Böyle bir mesaj otomatik reddedilmek yerine
maskelenerek işlenebilir.

### 6.2 Category ve subcategory stratejisi

Category enum mevcut altı iş alanı ve genel destek olarak korunmalıdır:

```text
SIPARIS
IADE
ODEME
KARGO_TESLIMAT
HESAP_GUVENLIK
KAMPANYA_PUAN
GENEL_DESTEK
```

Mevcut bilgi tabanında 70 subcategory vardır. İlk model için iki seçenek bulunur:

#### Önerilen: hiyerarşik iki aşamalı sınıflandırma

Tek model tek JSON üretebilir ancak eğitim ve değerlendirme iki seviyede yapılır:

1. Category.
2. Category içindeki subcategory.

Bu yaklaşım 70 sınıflı düz classification'a göre daha kararlıdır.

#### Alternatif: subcategory'yi ilk sürümde sınırlamak

Yeterli örnek yoksa yalnız yüksek hacimli subcategory'ler eğitilir, diğerleri
`OTHER` veya boş bırakılır. Yanlış ve yüksek confidence'lı subcategory üretmekten
daha güvenlidir.

### 6.3 Confidence

Modelin ürettiği metinsel `0.93` değeri doğrudan güvenilir kabul edilmemelidir.

Önerilen v1:

- Model JSON içinde confidence üretmesin veya `null` üretsin.
- Offline validation sonucunda category/security için calibration yapılır.
- Inference runtime token logprob sağlıyorsa ayrı confidence katmanı hesaplanır.
- Composite confidence ancak kalibre edilmiş classifier confidence ile beslenir.

---

## 7. Fine-tuning verisi

### 7.1 Veri kaynakları

- 70 dokümanın title/category/subcategory alanları.
- Her dokümandaki amaç, tanım, koşullar, adımlar ve standart yanıt.
- RAG audit ve manuel düzeltme raporları.
- Gerçek kullanıcı soruları; yalnız anonimleştirilmiş ve izinli olanlar.
- Sentetik Türkçe paraphrase örnekleri.
- Güvenlik/adversarial örnekleri.
- Belirsiz ve eksik kullanıcı mesajları.

Bilgi tabanı metinlerini doğrudan kullanıcı sorusu gibi kullanmak yeterli değildir.
Her subcategory için gerçek kullanıcı diline benzeyen soru varyasyonları gerekir.

### 7.2 Örnek türleri

Her iş sınıfı için:

- düzgün Türkçe
- günlük konuşma dili
- yazım hatası
- kısa mesaj
- uzun açıklama
- birden fazla niyet
- eksik bağlam
- olumsuz duygu
- acil durum
- yanlış kategoriye benzeyen zor negatif

Güvenlik için:

- doğrudan jailbreak
- dolaylı prompt injection
- sistem promptu isteme
- API key/secret isteme
- destek sorusu içine gömülmüş talimat
- RAG dokümanı gibi gösterilen saldırı
- encoding/boşluk/Unicode varyasyonları
- Türkçe ve İngilizce karışık saldırılar

### 7.3 Dataset formatı

Önerilen JSONL:

```json
{
  "id": "train_000001",
  "text": "Siparişimi iptal etmek istiyorum.",
  "label": {
    "category": "SIPARIS",
    "subcategory": "SIPARIS_IPTALI",
    "security_label": "SAFE",
    "priority": "MEDIUM",
    "expected_action": "RAG_ANSWER"
  },
  "group_id": "siparis_iptali_template_01",
  "source": "human",
  "language": "tr"
}
```

`group_id`, aynı template/paraphrase ailesinin train ve test'e dağılmasını
engellemek için zorunlu olmalıdır.

### 7.4 Split

```text
Train: %80
Validation: %10
Test: %10
```

Split satır bazında rastgele değil, `group_id` bazında yapılmalıdır. Ayrıca ayrı
bir adversarial security test seti tutulmalıdır.

### 7.5 Veri miktarı

70 subcategory için birkaç örnek yeterli değildir. Hedef olarak:

- Category başına en az 500-1000 çeşitli soru.
- Aktif subcategory başına tercihen en az 100-200 kaliteli varyasyon.
- Güvenlik sınıfı başına yüzlerce çeşitli örnek.
- SAFE örneklerle güvenlik örnekleri arasında kontrollü denge.

Bu sayılar mutlak kural değildir; kalite ve zor negatif çeşitliliği ham sayıdan
daha önemlidir.

---

## 8. Qwen3-8B + QLoRA değerlendirmesi

### Güçlü tarafları

- Türkçe sınıflandırma için yeterli dil kapasitesi.
- QLoRA ile eğitim belleği azaltılabilir.
- Adapter artifact'ı küçük ve versiyonlanabilir.
- Structured JSON üretimi için instruction-tuning yaklaşımına uygundur.

### Riskleri

- 8B model yalnız classification için operasyonel olarak ağırdır.
- Colab GPU türüne göre eğitim yavaş veya bellek sınırına yakın olabilir.
- Local CPU inference kullanıcı deneyimi için yetersiz kalabilir.
- Generative JSON classifier, klasik classification head kadar deterministik
  olmayabilir.
- Model confidence değeri kalibrasyonsuz güvenilir değildir.

### Önerilen başlangıç ayarları

```text
Base: Qwen/Qwen3-8B
Quantization: 4-bit NF4
Compute dtype: bf16 destekleniyorsa bf16, aksi halde fp16
LoRA rank: 16
LoRA alpha: 32
LoRA dropout: 0.05
Sequence length: 512
Per-device batch: 1
Gradient accumulation: 16
Learning rate: 1e-4
Epoch: 2
Warmup ratio: 0.05
Evaluation: her epoch ve belirli step aralıkları
Early stopping: validation macro-F1
Thinking mode: kapalı
```

İlk deneyden sonra rank 32 ve üçüncü epoch yalnız validation sonuçlarına göre
denenmelidir.

---

## 9. Colab eğitim ve test akışı

### Eğitim notebook bölümleri

1. GPU ve CUDA kontrolü.
2. Paketlerin sabit sürümlerle kurulması.
3. Dataset yükleme ve schema doğrulama.
4. Duplicate/group leakage kontrolü.
5. Label dağılım raporu.
6. Qwen tokenizer/chat template hazırlığı.
7. 4-bit base model yükleme.
8. QLoRA adapter konfigürasyonu.
9. SFT eğitimi.
10. Validation değerlendirmesi.
11. Adapter ve tokenizer kaydı.
12. Holdout test.
13. Adversarial güvenlik testi.
14. Hata analizi raporu.

### Colab inference testi

```text
Base model 4-bit yüklenir
→ LoRA adapter bağlanır
→ thinking kapatılır
→ temperature=0
→ max_new_tokens düşük tutulur
→ JSON parse edilir
→ enum/schema validation yapılır
→ geçersiz çıktı başarısız sayılır
```

Ölçümler:

- category macro-F1
- subcategory macro-F1
- security macro-F1
- jailbreak/prompt-injection recall
- false SAFE oranı
- priority macro-F1
- expected action accuracy
- valid JSON oranı
- enum/schema başarı oranı
- p50/p95 inference süresi
- GPU bellek kullanımı

Security için en kritik metrik false SAFE oranıdır.

---

## 10. Production entegrasyonu

### Önerilen dağıtım

Qwen modeli ana FastAPI process'ine yüklenmemelidir. Ayrı servis:

```text
DestekAI Backend ──HTTP──> Qwen Classifier Service
```

Model servisi örnek API:

```http
POST /v1/classify
```

Request:

```json
{
  "request_id": "uuid",
  "text": "Siparişimi nasıl iptal edebilirim?",
  "security_flags": [],
  "taxonomy_version": "2026-06-23"
}
```

Response:

```json
{
  "category": "SIPARIS",
  "subcategory": "SIPARIS_IPTALI",
  "security_label": "SAFE",
  "priority": "MEDIUM",
  "expected_action": "RAG_ANSWER",
  "confidence": null,
  "model_version": "qwen3-8b-qlora-classifier-v1",
  "latency_ms": 185
}
```

Backend config:

```env
CLASSIFIER_PROVIDER=qwen
QWEN_CLASSIFIER_URL=http://classifier:8100
QWEN_CLASSIFIER_TIMEOUT_SECONDS=5
```

`QwenClassifier` stub, bu endpoint'i çağıran adapter ile değiştirilir.

Fallback:

```text
Qwen timeout / HTTP error / invalid JSON / enum hatası
→ rule-based classifier
→ rag_runs içinde fallback reason
```

Classifier servisi internal network dışında yayınlanmamalıdır.

---

## 11. Fine-tune sonrası pipeline

Önerilen nihai akış:

```text
1. Mesaj uzunluğu doğrulanır.
2. HTML/script ve kontrol karakterleri temizlenir.
3. Unicode/boşluk normalizasyonu yapılır.
4. Deterministic scanner security_flags üretir.
5. PII tespiti yapılır.
6. Qwen güvenli orijinal metin + security_flags ile çağrılır.
7. Qwen çıktısı Pydantic/JSON Schema ile doğrulanır.
8. security_label güvenli değilse policy engine karar verir.
9. ASK_CLARIFICATION ise RAG/Gemini çağrılmaz.
10. RAG_ANSWER ise Gemini rewrite çalışır.
11. Canonical soru RAG'a gider.
12. Reranked context Gemini answer modeline gider.
13. Output guard ve PII kontrolü uygulanır.
14. Mesaj, kaynaklar, model sürümü ve metrikler kaydedilir.
```

`CREATE_TICKET`, kullanıcının onayı olmadan ticket oluşturmamalıdır. Yalnız
`ticket_recommended=true` üretmelidir.

---

## 12. Fine-tuning öncesi gerekli backend değişiklikleri

1. `ClassificationResult` içine `security_label` ve `model_version` eklenmesi.
2. Classifier response için Pydantic model ve enum doğrulaması.
3. `QWEN_CLASSIFIER_URL` ve timeout ayarları.
4. HTTP tabanlı gerçek `QwenClassifier` adapterı.
5. Fallback reason ve classifier latency'nin `rag_runs` içinde saklanması.
6. `sanitize_query` fonksiyonunun normalizasyon ve policy kararlarına ayrılması.
7. Security scanner flaglerinin classifier'a iletilmesi.
8. Model taxonomy version alanı.
9. Shadow mode desteği.

Shadow mode:

```text
Rule-based karar production sonucunu belirler
Qwen aynı mesajı paralel sınıflandırır
Sonuçlar yalnız karşılaştırma için kaydedilir
```

Model doğrudan aktif edilmeden önce bu mod kullanılmalıdır.

---

## 13. Rollout önerisi

### Aşama 1 — Offline

- Dataset ve etiketleme kılavuzu.
- Colab eğitimi.
- Holdout ve adversarial test.
- Model card ve artifact checksum.

### Aşama 2 — Local entegrasyon

- Ayrı classifier servisi.
- Backend adapterı.
- Contract ve timeout testleri.
- RAG/Gemini çağrısı olmadan classifier endpoint testleri.

### Aşama 3 — Shadow mode

- Qwen karar vermez, yalnız ölçülür.
- Rule-based/Gemini sonuçlarıyla karşılaştırılır.
- False SAFE ve yanlış kategori örnekleri incelenir.

### Aşama 4 — Kademeli aktivasyon

- Önce yalnız category routing.
- Sonra subcategory.
- Sonra priority ve ticket recommendation.
- Security REJECT kararı en son ve yüksek eşikle aktif edilir.

### Aşama 5 — Sürekli iyileştirme

- Kullanıcı feedback ve ticket sonuçlarından etiketlenmiş veri üretme.
- Yanlış sınıflandırmaların insan incelemesi.
- Dataset/model/taxonomy versiyonlama.
- Periyodik yeniden eğitim.

---

## 14. Kabul kriterleri

Model production kararına katılmadan önce:

- JSON validity en az `%99.5`.
- Category macro-F1 hedefi en az `0.90`.
- Security attack recall hedefi en az `0.97`.
- False SAFE oranı ekipçe belirlenen düşük eşiğin altında.
- Belirsiz sorularda `ASK_CLARIFICATION` davranışı doğrulanmış.
- Model timeoutunda backend kesintisiz rule-based fallback yapıyor.
- Model servisi kapalıyken chat çalışmaya devam ediyor.
- Model versiyonu her `rag_runs` kaydında izleniyor.
- P95 classifier latency kullanıcı deneyimini bozmayacak seviyede.
- RAG ve Gemini classifier hatasından bağımsız çalışabiliyor.

Bu eşikler başlangıç hedefidir; test setinin kalitesi ve gerçek trafik sonucu ile
kalibre edilmelidir.

---

## 15. Önceliklendirilmiş öneriler

### Hemen

1. Mevcut çalışma ağacını mantıklı commitlere bölmek.
2. README'yi güncel hashing/RAG/Gemini durumuyla eşitlemek.
3. Fine-tune taxonomy ve `security_label` sözleşmesini ekipçe kilitlemek.
4. Dataset etiketleme kılavuzunu yazmak.

### RAG geliştiricisi tesliminde

1. `GroupedDocument` sözleşmesini koruyarak adapter bağlamak.
2. Gerçek embedding ile re-ingest.
3. Offline retrieval test setiyle threshold kalibrasyonu.
4. Passthrough reranker'ı değiştirmek.

### Fine-tune geliştiricisi tesliminde

1. Adapter artifact + tokenizer + model card almak.
2. Colab evaluation raporu istemek.
3. Ayrı inference servisi oluşturmak.
4. Backend'i önce shadow mode ile bağlamak.

### Production öncesi

1. Redis rate limiter.
2. `AUTO_CREATE_TABLES=false`.
3. Debug RAG endpoint için admin yetkisi.
4. SMTP worker ve retry/backoff.
5. Frontend smoke/E2E testleri.
6. Merkezi log, metrik ve alarm.

---

## Sonuç

Mevcut proje, yeni RAG ve fine-tuned classifier'ın bağlanabileceği işlevsel bir
MVP temelidir. En önemli avantaj, kullanıcı/konuşma/ticket akışının ve AI
pipeline gözlemlenebilirliğinin şimdiden bulunmasıdır.

En büyük kısa vadeli riskler:

- geçici hashing retrieval kalitesi,
- gerçek reranker olmaması,
- Qwen adapterının stub olması,
- classifier güvenlik sözleşmesinde `security_label` bulunmaması,
- in-memory rate limit,
- commit edilmemiş geniş çalışma ağacı.

Qwen3-8B + QLoRA kullanılabilir bir seçimdir; ancak model yalnız sınıflandırma
servisi olarak konumlandırılmalı, önce shadow mode'da ölçülmeli ve tek güvenlik
katmanı olarak kullanılmamalıdır.
