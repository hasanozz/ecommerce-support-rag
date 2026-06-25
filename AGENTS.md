# Codex Kullanım Kuralları

## 1. Proje Özeti

Bu proje, e-ticaret müşteri destek sistemi geliştirme projesidir.

Sistem şu bileşenlerden oluşur:

- FastAPI backend
- PostgreSQL + pgvector
- RAG tabanlı doküman arama
- Gemini API ile cevap üretimi
- Google OAuth ile kullanıcı girişi
- Konuşma geçmişi
- Feedback sistemi
- Ticket sistemi
- Admin ticket paneli
- İleride eklenecek fine-tuned classifier modeli

Amaç, kullanıcının destek sorusunu alıp ilgili dokümanlardan kaynaklı, güvenli ve açıklanabilir cevap üretmektir.

---

## 2. Codex’in Rolü

Codex bu projede yardımcı geliştirici gibi davranmalıdır.

Codex:

- Mevcut mimariye uymalıdır.
- Önce ne anladığını açıklamalıdır.
- Sonra dosya dosya uygulama planı çıkarmalıdır.
- Gri alanları ve varsayımlarını belirtmelidir.
- Kullanıcının onayı olmadan büyük refactor, dosya silme veya taşıma yapmamalıdır.
- Commit atmamalıdır.

---

## 3. Çalışma Kuralı

Her görevde önce şu formatta cevap ver:

```text
## Ne Anladım?
...

## Varsayımlar
...

## Gri Alanlar
...

## Uygulama Planı
- dosya/yol: yapılacak işlem

## Riskler
...

## Onay Gereken Noktalar
...
