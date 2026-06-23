# DestekAI RAG MVP

FastAPI, PostgreSQL ve pgvector kullanan e-ticaret müşteri destek RAG MVP'si.

## Bileşenler

- 70 dokümandan section bazlı chunk üretimi
- `multilingual-e5-large` ile yerel embedding
- pgvector cosine similarity araması
- `/api/rag/search` retrieval endpoint'i
- `/api/chat` kaynaklı cevap endpoint'i
- İsteğe bağlı yerel Ollama LLM entegrasyonu
- Basit mesaj temizleme ve jailbreak kontrolleri
- HTML/CSS/JS sohbet arayüzü

## Kurulum

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d postgres
python -m backend.scripts.create_chunks
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

LLM olmadan sistem en uygun `standart_yanit` veya chunk içeriğini döndürür. Yerel Ollama kullanmak için:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
```

## Komutlar

```powershell
# Chunk dosyasını üret
python -m backend.scripts.create_chunks

# Tabloları oluştur
python -m backend.scripts.init_db

# Dokümanları, chunkları ve embeddingleri yükle
python -m backend.scripts.ingest

# pgvector ve tablo kayıt sayılarını kontrol et
python -m backend.scripts.db_status

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

Bu aşamada `llm_context` yalnızca önizleme amacıyla hazırlanır; LLM çağrısı yapılmaz.

`POST /api/chat`

```json
{"message": "Kartımdan para çekildi ama sipariş oluşmadı"}
```

Query rewriting, reranking, classifier, feedback, ticket ve explainability bu MVP'nin kapsamı dışındadır; servis katmanları sonradan eklenebilecek şekilde ayrılmıştır.

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
