Kod yazma. Mevcut projeyi incele ve ürün çözümleme + ürün cevap kalitesi için uygulanabilir kısa plan çıkar.

Problem:
Ürün sorularında sistem bazen yanlış ürünü seçiyor. Bunun nedeni product_name extraction ve fuzzy match’in fazla gevşek çalışması. Örnek ürün isimlerine özel hard-code istemiyorum. Çözüm ürün bazlı değil, genel mimari olmalı.

Hedef:
1. Ürün detay sayfasından Copilot’a Sor'a basıldığında frontend/backend akışında hidden product_id kullanılmalı.
   - product_id varsa metinden ürün tahmini yapılmamalı.
   - router veya fuzzy match product_id’yi ezmemeli.
   - chat ekranında görünmemeli ama product_id hidden bir şekilde gitmeli akışa.

2. Serbest chat mesajlarında product_id yoksa daha güvenli ürün çözümleme planı çıkar.
   - exact name / alias / ürün tipi-kategori eşleşmesi düşün.
   - tek ürüne güven yoksa yanlış ürün seçme.
   - kategori/genel ürün tipi sorularında birden fazla ilgili ürünü döndürme mantığını değerlendir.
   - fuzzy sadece kontrollü son adım olmalı.
   - hard-coded ürün ismi veya özel fallback yazma.

3. Router’a ürün kataloğu ezberletme.
   - router intent/category için kalsın.
   - ürün kimliği ayrı resolver katmanında çözülsün.
   - router_db_lookup_plan.json mevcut rolüyle değerlendirilsin; gerekirse nasıl kullanılacağı açıklansın.

4. Ürün cevap formatını intent’e göre düzelt.
   - Spesifik soru: sadece istenen bilgi + kısa bağlam.
   - Genel ürün bilgisi: açıklama, teknik özellikler, fiyat, stok, iade, garanti, puan/yorum özeti.
   - Sipariş/iade/kargo sorusu: sadece ilgili ürün/sipariş bağlamı.
   - “Hesabınızda bu ürüne ait sipariş kaydı görünmüyor” cümlesi sadece hesap/sipariş/iade/kargo gerektiren sorularda çıksın.

5. Yorumlar için ölçeklenebilir plan öner.
   - Tüm yorumları modele basma.
   - Puan dağılımı, iyi/kötü yorum sayısı, puan gruplarından örnekler, olumlu/olumsuz özet gibi bir yapı düşün.

6. Trace/debug planı çıkar.
   - product_id source
   - candidate products
   - selected product
   - confidence/reason
   - selected/dropped orders
   - answer mode

İncele:
- frontend Copilot product click payload
- backend pipeline.py
- classifier/router kullanımı
- product_context.py / data_resolver
- evidence_fetcher.py
- commerce_answer.py
- compact_context.py
- router_db_lookup_plan.json

Plan şunları içersin:
- Hangi dosyalara dokunulacak?
- Sıralı patch adımları
- Riskler
- Minimum zorunlu testler

Not:
Büyük refactor önerme. DB seed/model/fine-tune değiştirmeden önce backend/frontend akışını düzeltmeye odaklan.