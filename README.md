# DestekAI RAG MVP

FastAPI, PostgreSQL ve pgvector kullanan, Google OAuth ile kullanıcı geçmişi,
feedback ve ticket yönetimi sağlayan e-ticaret müşteri destek RAG MVP'si.

## Bileşenler

- `rag_documents_final/*.json` ve `rag_chunks/rag_chunks_clean.jsonl` kaynaklı RAG ingest
- `multilingual-e5-large` ile yerel embedding
- pgvector cosine similarity araması
- `/api/rag/search` retrieval endpoint'i
- `/api/chat` legacy/deprecated cevap endpoint'i
- Basit mesaj temizleme ve jailbreak kontrolleri
- Google OAuth ve güvenli cookie session
- Çok mesajlı konuşma geçmişi
- Feedback, ticket ve admin ticket yönetimi
- Gemini query rewriting ve cevap üretimi için opsiyonel entegrasyon
- PII maskeleme, rate limit ve LLM output kontrolü
- HTML/CSS/JS sohbet arayüzü

## Kurulum

```powershell
$env:SECRETS_FILE="C:\Users\hasanozz\Desktop\teknopark-ai\project_secrets\.env.local"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d postgres
alembic upgrade head
python -m backend.scripts.ingest
uvicorn backend.app.main:app --reload
```

Arayüz: `http://localhost:8000`  
API dokümantasyonu: `http://localhost:8000/docs`

## Yapılandırma

Varsayılan embedding:

```env
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDING_DIMENSION=1024
```

Model indirmeden geliştirme testi yapmak için:

```env
EMBEDDING_PROVIDER=hashing
```

Gemini kullanmak için:

```env
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MODEL_DEV=gemini-2.5-flash-lite
GEMINI_API_KEY=...
```

API anahtarını frontend'e veya Git'e koymayın. Repo dışı secret dosyası Git
tarafından ignore edilir; ekipte her geliştirici kendi secret değerlerini
tanımlar. Production ortamında platform secret/environment variable sistemi
kullanılmalıdır.

## Google OAuth

Google Cloud Console'da bir OAuth Web Application oluşturun ve redirect URI
olarak şunu ekleyin:

```text
http://localhost:8000/auth/google/callback
```

`SECRETS_FILE` ile gösterilen repo dışı `.env.local`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MODEL_DEV=gemini-2.5-flash-lite
SESSION_SECRET=uzun-rastgele-deger
IP_HASH_SECRET=farkli-uzun-rastgele-deger
ADMIN_EMAILS=["admin@example.com"]
```

OAuth tüm korumalı API'lerde zorunludur. Admin listesine eklenen e-posta
ticket durumlarını güncelleyebilir.

## Komutlar

```powershell
# DEPRECATED: Eski data/processed chunk üretim akışı.
# Yeni ingest kaynağı rag_documents_final/ ve rag_chunks/rag_chunks_clean.jsonl dosyalarıdır.
python -m backend.scripts.create_chunks

# Tabloları oluştur
alembic upgrade head

# Ebrar RAG kaynaklarından dokümanları, chunkları ve embeddingleri yükle
python -m backend.scripts.ingest

# pgvector ve tablo kayıt sayılarını kontrol et
python -m backend.scripts.db_status

# Bekleyen SMTP e-postalarını gönder
python -m backend.scripts.process_email_outbox

# Test
pytest backend/tests
```

## Veritabanını görüntüleme

PostgreSQL terminalini açmak için:

```powershell
docker compose exec postgres psql -U postgres -d destekai
```

`psql` içinde kullanılabilecek temel komutlar:

```sql
\dt
\d documents
\d chunks
\d query_logs
SELECT count(*) FROM documents;
SELECT count(*) FROM chunks;
SELECT * FROM query_logs ORDER BY created_at DESC LIMIT 10;
\q
```

Grafik arayüz için DBeaver veya VS Code PostgreSQL eklentisi kullanılabilir:

```text
Host: localhost
Port: 5432
Database: destekai
User: postgres
Password: postgres
```

Tablo modelleri `backend/app/models/`, bağlantı ve session yönetimi
`backend/app/database.py`, veri yükleme işlemi ise `backend/scripts/ingest.py`
altındadır.

## SMTP

Ticket oluşturma e-posta hatası nedeniyle başarısız olmaz. Bildirim önce
`email_outbox` tablosuna yazılır. Demo için Gmail SMTP kullanılabilir:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=demo@example.com
SMTP_PASSWORD=uygulama-parolasi
SMTP_FROM_EMAIL=demo@example.com
SMTP_USE_TLS=true
```

Normal Gmail şifresi yerine uygulama parolası kullanılmalıdır.

## Endpoint'ler

`POST /api/rag/search`

```json
{"query": "Kartımdan para çekildi ama sipariş oluşmadı", "limit": 10}
```

Yanıt aynı dokümana ait chunkları birleştirir ve en fazla üç doküman döndürür:

```json
{
  "query": "...",
  "grouped_results": [
    {
      "doc_id": "...",
      "title": "...",
      "category": "ODEME",
      "subcategory": "...",
      "best_score": 0.67,
      "matched_sections": ["tanim", "kapsam", "kosullar"],
      "combined_context": "Doküman: ..."
    }
  ],
  "llm_context": "..."
}
```

`/api/rag/search` düşük seviyeli RAG inceleme endpointidir. Kullanıcı sohbeti
için konuşma endpointleri kullanılmalıdır.

Yeni kullanıcı akışı için temel endpointler:

```text
GET  /auth/google/login
GET  /auth/google/callback
GET  /auth/me
POST /auth/logout

POST /api/conversations
GET  /api/conversations
GET  /api/conversations/{id}
POST /api/conversations/{id}/messages

POST /api/messages/{id}/feedback
POST /api/similar-solutions/{id}/feedback

GET   /api/tickets
GET   /api/tickets/{id}
GET   /api/admin/tickets
PATCH /api/admin/tickets/{id}
```

Query rewriting, Gemini cevap üretimi, classifier, feedback ve ticket akışı backend
MVP'ye eklenmiştir. Reranking halen RAG geliştiricisinin servis sözleşmesi içinde
geliştirilecek alandır. Fine-tuning, gelişmiş explainability ve ayrı destek
personeli rolleri MVP kapsamı dışındadır.

## Proje Yapısı

```
ecommerce-support-rag/
│
├── backend/                    ← FastAPI sunucusu
├── frontend/                   ← HTML/CSS/JS arayüzü
├── scripts/                    ← Yardımcı betikler
│
├── rag_documents_final/        ← ✓ Tek gerçek RAG bilgi kaynağı
│   ├── siparis.json
│   ├── iade.json
│   ├── odemeler.json
│   ├── kargo_teslimat.json
│   ├── hesap_guvenlik.json
│   └── kampanya_puan.json
│
├── rag_chunks/                 ← Chunk dosyaları (gelecek)
├── embeddings/                 ← Embedding vektörleri (gelecek)
├── logs/                       ← Uygulama günlükleri (gelecek)
│
├── archive/                    ← İşlem geçmişi
│   ├── rag_documents/          ← İlk çıkarma (archive)
│   ├── rag_documents_structured/
│   └── rag_documents_clean/
│
├── data/                       ← Diğer veri dosyaları
├── docker-compose.yml
├── README.md
└── requirements.txt
```

### Kaynaklar

- `rag_documents_final/`: Kategorilere ayrılmış nihai RAG dokümanları. Tüm sistem bu klasördeki JSON dosyalarını okur.
- `archive/`: İşlem aşamaları ve deneme çalışmaları. Referans amacıyla saklanır.
