# Backend, Frontend ve AI Entegrasyon Yol Haritası

## Uygulanan değişiklikler

- Mesaj akışı `güvenlik temizliği → classifier → rewrite → retrieval → reranker → context → Gemini → output kontrolü` sırasına getirildi.
- Varsayılan classifier `rule_based` yapıldı. Gemini adapterı eklendi; Qwen 8B + QLoRA adapterı gerçek model hazır olana kadar güvenli stub olarak bırakıldı.
- Confidence; retrieval, opsiyonel reranker ve classifier skorlarından hesaplanıyor. Classifier skoru yoksa birleşik skor `null` kalıyor.
- `rag_runs` token, maliyet, latency, skor bileşenleri ve classification sonucuyla genişletildi.
- Similar solution gösterimleri ayrı impression tablosuna alındı.
- Embedding ingest metadata ve zorunlu model/config/PostgreSQL boyut kontrolü eklendi.
- `/api/rag/search` LLM çağrısından bağımsız debug/context preview endpoint’i olarak korundu.
- Frontend; tema, sık sorulan sorular, context preview, feedback modalı, ticket ve admin akışlarıyla güncellendi.

## Secret mimarisi

Backend proje dizinindeki `.env` dosyasını otomatik okumaz. Başlangıçta
`SECRETS_FILE` environment variable zorunludur ve repo dışındaki secret dosyasının
mutlak yolunu göstermelidir.

İsteğe bağlı repo dışı dosya:

```powershell
$env:SECRETS_FILE = "C:/Users/hasanozz/Desktop/teknopark-ai/project_secrets/.env.local"
uvicorn backend.app.main:app --reload
```

`SECRETS_FILE` yoksa, dosya bulunamazsa veya proje dizini içindeyse uygulama
başlamaz. Google OAuth, Gemini ve session/IP secret değerleri bütün ortamlarda
zorunludur. `SESSION_SECRET` ile `IP_HASH_SECRET` en az 32 karakter olmalıdır.
Normal Gemini çağrıları `GEMINI_MODEL`, açıkça dev model istenen çağrılar
`GEMINI_MODEL_DEV` kullanır.

Mevcut geliştirme pipeline'ında rewrite ve final cevap çağrıları kapasitesi daha
uygun olan `GEMINI_MODEL_DEV` ile çalışır. Promptlar gerçek Gemini
`systemInstruction` alanı ile güvenilmeyen user/context verisi ayrılarak gönderilir.
Normal mesaj akışı iki Gemini çağrısı yapar; rewrite tek deneme, final cevap geçici
5xx hatasında en fazla iki denemedir. `429` quota hatası hemen fallback'e geçer.

Repoda yalnızca `.env.example` tutulur. Mevcut yerel `.env` içindeki değerler kullanıcı tarafından OS environment’a veya repo dışı dosyaya taşındıktan sonra proje dizinindeki dosya silinmelidir. Codex gerçek secret dosyasını okumaz, oluşturmaz veya taşımaz.

## Frontend–backend endpoint eşleşmeleri

| İşlev | Endpoint |
|---|---|
| Google giriş | `GET /auth/google/login` |
| Kullanıcı bilgisi | `GET /auth/me` |
| Çıkış | `POST /auth/logout` |
| Konuşma oluşturma/listeleme | `POST/GET /api/conversations` |
| Konuşma detayı | `GET /api/conversations/{id}` |
| Mesaj gönderme | `POST /api/conversations/{id}/messages` |
| Ana cevap feedback | `POST /api/messages/{id}/feedback` |
| Benzer çözüm feedback | `POST /api/similar-solutions/{id}/feedback` |
| Kullanıcı ticketları | `GET /api/tickets` |
| Admin ticketları | `GET /api/admin/tickets` |
| Admin ticket güncelleme | `PATCH /api/admin/tickets/{id}` |
| RAG debug/context | `POST /api/rag/search` |

Olumsuz ana cevap feedback’i her priority seviyesinde kullanıcıya ticket seçeneği sunar. `ticket_recommended` yalnızca `HIGH` ve `URGENT` için `true` olur. Benzer çözüm feedback’i ticket açmaz.

## Classifier ve fine-tuning sözleşmesi

Classifier rewrite edilmiş soru almaz. Girdi önce uzunluk, HTML/script, kontrol karakteri, Unicode ve boşluk normalizasyonundan geçer:

- Rule-based ve ileride local Qwen provider: güvenli orijinal metin.
- Gemini gibi dış providerlar: PII maskeli metin.

Çıktı:

```json
{
  "category": "ODEME",
  "subcategory": "",
  "priority": "HIGH",
  "expected_action": "RAG_ANSWER",
  "confidence": 0.82,
  "provider": "rule_based"
}
```

`CLASSIFIER_PROVIDER=rule_based` varsayılandır. `qwen` seçilir fakat model hazır değilse adapter hata üretir ve servis rule-based fallback kullanır. Gerçek model geldiğinde yalnız `QwenClassifier` adapterı değiştirilecektir.

## RAG sözleşmesi

Servis sınırları:

- `Retriever`: pgvector adaylarını bulur ve doküman bazında gruplar.
- `Reranker`: gruplanmış dokümanları yeniden sıralar; mevcut adapter passthrough’dur.
- `Rewriter`: classifier sonrasında canonical soru üretir.
- `ContextBuilder`: en fazla üç dokümanı LLM context’ine dönüştürür.
- `ClassifierProvider`: ham niyeti güvenli orijinal metinden sınıflandırır.

`/api/rag/search` Gemini çağırmadan şu temel yapıyı döndürür:

```json
{
  "query": "...",
  "grouped_results": [
    {
      "doc_id": "...",
      "title": "...",
      "category": "...",
      "subcategory": "...",
      "best_score": 0.82,
      "retrieval_score": 0.82,
      "reranker_score": null,
      "matched_sections": [],
      "combined_context": "..."
    }
  ],
  "llm_context": "...",
  "reranker_enabled": false
}
```

## Confidence ve metrikler

Reranker varsa:

```text
0.50 * retrieval_score + 0.30 * reranker_score + 0.20 * classifier_confidence
```

Reranker yoksa:

```text
0.70 * retrieval_score + 0.30 * classifier_confidence
```

`rag_runs` şu gözlem alanlarını saklar:

- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `estimated_cost`, `latency_ms`
- `retrieval_score`, `reranker_score`
- `classifier_confidence`, `composite_confidence`
- `classification_result`, ham `token_usage`

Maliyet ancak modelin token kullanım bilgisi ile prompt/completion fiyat ayarları birlikte mevcutsa hesaplanır.

## Embedding ingest

Ingest başlamadan modelden test vektörü üretilir; config boyutu ve PostgreSQL `chunks.embedding` ile `similar_solutions.embedding` boyutları karşılaştırılır. Herhangi bir uyumsuzlukta mevcut veriler silinmeden işlem durur.

`bge-m3` zorunlu olarak `vector(1024)` kullanır. Başarılı ingest sonrasında provider, model, dimension, dataset checksum, doküman/chunk sayısı ve ingest sürümü `embedding_ingests` tablosunda aktif metadata olarak saklanır. Retrieval çalışan ayarlarla aktif metadata uyuşmuyorsa durur.

Kurulum sırası:

```powershell
alembic upgrade head
python -m backend.scripts.ingest
```

## Similar solutions

Her gösterim `similar_solution_impressions` tablosuna `(similar_solution_id, assistant_message_id, user_id)` unique kısıtıyla kaydedilir. Böylece aynı cevapta aynı kullanıcıya tekrar render edilmesi sayacı şişirmez.

Yayın/few-shot eşikleri:

- En az 10 benzersiz impression
- En az 5 olumlu feedback
- En az `%80` başarı oranı

## Kalan işler ve riskler

- Gerçek Qwen runtime ve QLoRA adapterı bağlanmalı.
- Gerçek reranker providerı ve reranker skoru kalibrasyonu eklenmeli.
- Gemini model fiyatları deployment ortamında güncel değerlerle konfigüre edilmeli.
- Production’da RAG debug endpoint’i kaldırılmadan admin/teknik rol ile sınırlandırılmalı.
- Impression sayılarının yüksek trafikte raporlanması için ileride özet/materialized view düşünülebilir.
- Alembic migration uygulanmadan yeni model alanları mevcut veritabanında bulunmaz.
