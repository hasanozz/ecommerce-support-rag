"""Create a manual correction plan from rag_document_audit.json.

This script is read-only with respect to rag_documents.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "reports" / "rag_document_audit.json"
OUTPUT_PATH = ROOT / "data" / "reports" / "manual_fix_plan.md"


HIGH_FIXES = {
    "PAYMENT_INVOICE_MISMATCH_001": {
        "kapsam": {
            "neden": "Mevcut değer yalnızca başlığı kategoriyle birleştiren genel bir kalıp; uyuşmazlığın hangi işlemleri kapsadığını belirtmiyor.",
            "oneri": "Bu süreç, siparişte tahsil edilen ödeme tutarı ile e-arşiv veya e-fatura üzerinde görünen tutarın farklı olduğu; kampanya, kupon, puan, vergi, kargo ücreti, kısmi iade veya sipariş güncellemesi kaynaklı farkların incelendiği durumlar için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş. Kayıtta uyuşmazlığın kontrol edilmesini gerektiren durumlar `istisnalar` içine karışmış.",
            "oneri": [
                "Banka veya ödeme yöntemi üzerinden tahsil edilen tutar ile faturanın genel toplamı karşılaştırılmalıdır.",
                "Kampanya, kupon, puan, vergi ve kargo ücreti satırları ayrı ayrı kontrol edilmelidir.",
                "Kısmi iade veya sipariş değişikliği varsa güncel fatura ve ödeme kayıtları dikkate alınmalıdır.",
                "Açıklanamayan tutar farkı, yanlış vergilendirme veya birden fazla fatura bulunması halinde inceleme başlatılmalıdır.",
            ],
        },
        "adimlar": {
            "neden": "Alan boş; kullanıcıya uygulanabilir bir kontrol sırası verilmiyor.",
            "oneri": [
                "Kullanıcı sipariş detayındaki ödenen toplamı kontrol eder.",
                "İlgili e-arşiv veya e-faturayı açarak ürün, indirim, vergi ve kargo satırlarını inceler.",
                "Banka hareketindeki kesinleşmiş tahsilat tutarını kontrol eder.",
                "Kampanya, kupon, puan, kısmi iade veya sipariş değişikliği olup olmadığını karşılaştırır.",
                "Fark açıklanamıyorsa sipariş numarası, fatura ve ödeme kaydıyla destek talebi oluşturur.",
            ],
        },
        "standart_yanit": {
            "neden": "Mevcut yanıt genel bir destek şablonu; kullanıcıya hangi tutarları karşılaştıracağını söylemiyor.",
            "oneri": "Ödeme tutarı ile fatura toplamı farklı görünüyorsa ürün, indirim, kupon veya puan, vergi ve kargo ücreti satırlarını kontrol edin. Fark bu kalemlerle açıklanamıyorsa sipariş numaranız, faturanız ve banka hareketinizle destek ekibine başvurabilirsiniz.",
        },
    },
    "PAYMENT_CARD_001": {
        "kapsam": {
            "neden": "Genel kapsam kalıbı kart türlerini ve doğrulama sürecini belirtmiyor.",
            "oneri": "Bu süreç, kredi kartı, banka kartı veya sanal kartla ödeme yapan; kart bilgisi, internet alışverişi yetkisi ve gerektiğinde 3D Secure doğrulaması kullanılan siparişler için geçerlidir.",
        },
        "tanim": {
            "neden": "Tanım, amaç alanının ilk cümlesini tekrar ediyor ve kavramı bağımsız biçimde açıklamıyor.",
            "oneri": "Kartla ödeme, sipariş tutarının kredi kartı, banka kartı veya sanal kart üzerinden ödeme altyapısı ve banka doğrulaması kullanılarak tahsil edilmesidir.",
        },
        "kosullar": {
            "neden": "Alan boş; kartla ödemenin başarılı olabilmesi için gereken bilgiler kayıtta dağınık halde bulunuyor.",
            "oneri": [
                "Kart bilgileri doğru ve eksiksiz girilmelidir.",
                "Kart geçerli olmalı ve internet alışverişine açık olmalıdır.",
                "Kartın kullanılabilir limiti sipariş tutarı için yeterli olmalıdır.",
                "Banka talep ederse 3D Secure doğrulaması tamamlanmalıdır.",
                "Ödeme banka ve ödeme altyapısı tarafından onaylanmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel şablon, kart ödemesine özgü kontrol noktalarını içermiyor.",
            "oneri": "Kartla ödeme için kart numarası, son kullanma tarihi ve güvenlik kodunu kontrol edin; kartınızın internet alışverişine açık ve limitinin yeterli olduğundan emin olun. Bankanız 3D Secure doğrulaması isterse işlemi tamamlayın.",
        },
    },
    "PAYMENT_CHARGED_ORDER_NOT_CREATED_001": {
        "kapsam": {
            "neden": "Genel kalıp, provizyon ile kesin tahsilat ayrımını ve sipariş kaydı sorununu açıklamıyor.",
            "oneri": "Bu süreç, kart hareketinde ödeme veya provizyon görüldüğü halde kullanıcı hesabında sipariş kaydı, sipariş numarası ya da e-posta/SMS onayı oluşmayan işlemler için geçerlidir.",
        },
        "tanim": {
            "neden": "Tanım amaç alanının ilk cümlesini aynen tekrar ediyor.",
            "oneri": "Karttan para çekildi ancak sipariş oluşmadı durumu, ödeme kaydının bankada görünmesine rağmen sipariş oluşturma adımının tamamlanmaması veya siparişin kullanıcı hesabına yansımamasıdır.",
        },
        "kosullar": {
            "neden": "Alan boş; destek incelemesi gerektiren göstergeler `istisnalar` içinde yer alıyor.",
            "oneri": [
                "Siparişlerim bölümünde ilgili sipariş veya sipariş numarası bulunmamalıdır.",
                "E-posta veya SMS ile sipariş onayı alınmamış olmalıdır.",
                "Banka hareketindeki işlemin provizyon mu kesinleşmiş tahsilat mı olduğu kontrol edilmelidir.",
                "Aynı işlem için yeniden ödeme yapılmadan önce sistem güncellemesi beklenmelidir.",
                "Ödeme kesinleşmiş halde kalır ve sipariş oluşmazsa destek incelemesi başlatılmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, yeniden ödeme riskini ve provizyon kontrolünü belirtmiyor.",
            "oneri": "Siparişiniz görünmüyorsa aynı işlem için yeniden ödeme yapmadan önce Siparişlerim bölümünü ve e-posta/SMS onayını kontrol edin. Banka hareketindeki kaydın provizyon mu kesin tahsilat mı olduğunu inceleyin; ödeme kesinleşmişse işlem bilgileriyle destek ekibine başvurun.",
        },
    },
    "SHIPPING_MARKED_DELIVERED_NOT_RECEIVED_001": {
        "kapsam": {
            "neden": "Genel kapsam kalıbı, teslim edildi statüsü ile fiziksel teslimat arasındaki uyuşmazlığı tanımlamıyor.",
            "oneri": "Bu süreç, kargo takip kaydında gönderi teslim edildi görünmesine rağmen paketin kullanıcıya, komşuya, güvenliğe veya belirtilen teslimat noktasına ulaşmadığı durumlar için geçerlidir.",
        },
        "tanim": {
            "neden": "Tanım amaç alanının ilk cümlesini tekrar ediyor.",
            "oneri": "Teslim edildi görünüyor ancak ulaşmadı durumu, kargo sisteminde teslim kaydı bulunmasına rağmen kullanıcının paketi fiziksel olarak teslim almamış olmasıdır.",
        },
        "kosullar": {
            "neden": "Alan boş; inceleme için gerekli ön kontroller açık bir koşul listesi olarak sunulmuyor.",
            "oneri": [
                "Kargo takip kaydı teslim edildi durumunda olmalıdır.",
                "Paket kapı önü, posta kutusu veya belirlenmiş teslimat alanında bulunmamalıdır.",
                "Komşu, güvenlik, resepsiyon veya apartman görevlisine teslim edilip edilmediği kontrol edilmelidir.",
                "Teslim alan kişi, imza, fotoğraf veya konum bilgisi varsa incelenmelidir.",
                "Paket bulunamazsa kargo firması teslimat incelemesi başlatmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, kullanıcının önce yapması gereken fiziksel ve kargo kontrollerini belirtmiyor.",
            "oneri": "Gönderiniz teslim edildi görünüyorsa önce kapı önü ve ortak teslimat alanlarını, ardından komşu, güvenlik veya resepsiyonu kontrol edin. Paket bulunamazsa takip numaranızla kargo firmasından teslim alan kişi ve teslimat kanıtının incelenmesini isteyin.",
        },
    },
    "PAYMENT_DOUBLE_CHARGE_001": {
        "kapsam": {
            "neden": "Genel kalıp, mükerrer tahsilat ile geçici provizyon ayrımını kapsamıyor.",
            "oneri": "Bu süreç, tek sipariş için kart hareketlerinde aynı tutarın birden fazla kez göründüğü ve kayıtların provizyon mu yoksa kesinleşmiş mükerrer tahsilat mı olduğunun incelendiği işlemler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; gerçek çift çekimin doğrulanması için gereken kontroller belirtilmiyor.",
            "oneri": [
                "Siparişlerim bölümünde kaç sipariş oluştuğu kontrol edilmelidir.",
                "Kart hareketlerindeki kayıtların provizyon veya kesinleşmiş tahsilat durumu incelenmelidir.",
                "Aynı tutarın aynı sipariş için birden fazla kez kesinleşip kesinleşmediği doğrulanmalıdır.",
                "Geçici provizyon kaydının banka tarafından kaldırılıp kaldırılmadığı takip edilmelidir.",
                "Birden fazla kesin tahsilat doğrulanırsa ödeme kayıtları incelemeye alınmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, provizyon ve gerçek tahsilat ayrımını açıklamıyor.",
            "oneri": "Kart hareketlerinde iki kayıt görüyorsanız önce bunların provizyon mu kesinleşmiş tahsilat mı olduğunu kontrol edin ve Siparişlerim bölümünde kaç sipariş oluştuğunu doğrulayın. Aynı sipariş için birden fazla kesin tahsilat varsa banka hareketleriyle destek ekibine başvurun.",
        },
    },
    "PAYMENT_FAILED_001": {
        "kapsam": {
            "neden": "Genel kalıp, başarısız ödemenin kart, banka, doğrulama ve sistem kaynaklı kapsamını göstermiyor.",
            "oneri": "Bu süreç, kart bilgisi, limit, internet alışverişi yetkisi, 3D Secure doğrulaması, banka reddi veya geçici ödeme altyapısı sorunu nedeniyle tamamlanamayan ve sipariş oluşturulmayan ödemeler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; başarılı ödeme için gerekli ön koşullar kayıtta ayrı bir liste halinde değil.",
            "oneri": [
                "Kart bilgileri doğru olmalıdır.",
                "Kartın süresi geçmemiş ve internet alışverişine açık olması gerekir.",
                "Kullanılabilir limit sipariş tutarı için yeterli olmalıdır.",
                "3D Secure doğrulaması istenirse tamamlanmalıdır.",
                "Banka veya ödeme altyapısı işlemi onaylamalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, ödeme başarısızlığında yapılacak kontrolleri sıralamıyor.",
            "oneri": "Kart bilgilerinizi, kullanılabilir limitinizi ve kartınızın internet alışverişine açık olup olmadığını kontrol edin. 3D Secure adımını tamamladıktan sonra işlemi yeniden deneyin; hata sürerse bankanızla görüşebilir veya farklı bir ödeme yöntemi kullanabilirsiniz.",
        },
    },
    "PAYMENT_SECURITY_001": {
        "kapsam": {
            "neden": "Genel kapsam değeri ödeme verilerinin korunması ve şüpheli işlemleri içermiyor.",
            "oneri": "Bu süreç, kart ve hesap bilgilerinin şifrelenmesi, 3D Secure doğrulaması, tokenizasyon, dolandırıcılık kontrolleri ve şüpheli veya yetkisiz ödeme hareketlerinin değerlendirilmesi için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; güvenli ödeme için gerekli koşullar ve risk göstergeleri ayrıştırılmamış.",
            "oneri": [
                "Ödeme işlemi güvenli bağlantı ve yetkili ödeme altyapısı üzerinden yapılmalıdır.",
                "Banka tarafından istenen kimlik doğrulama adımları tamamlanmalıdır.",
                "Kart bilgileri üçüncü kişilerle paylaşılmamalıdır.",
                "Olağan dışı deneme sayısı, farklı konumlar veya yüksek tutar gibi riskler ek doğrulama gerektirebilir.",
                "Yetkisiz işlem şüphesinde ödeme ve hesap güvenliği incelemesi başlatılmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, güvenlik ihlali şüphesinde alınacak aksiyonu belirtmiyor.",
            "oneri": "Ödemeler güvenli bağlantı, banka doğrulaması ve yetkili ödeme altyapıları üzerinden işlenir. Bilginiz dışında bir ödeme veya şüpheli hesap hareketi görürseniz kart bilgilerinizi paylaşmadan bankanızla ve destek ekibiyle hemen iletişime geçin.",
        },
    },
    "SHIPPING_DAMAGED_DELIVERY_001": {
        "kapsam": {
            "neden": "Genel kalıp, dış ambalaj, ürün ve sonradan fark edilen hasar türlerini kapsamıyor.",
            "oneri": "Bu süreç, dış ambalajı veya ürünü kırık, ezik, yırtık, çizik, sızıntılı, eksik parçalı ya da çalışmaz durumda teslim edilen gönderiler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; hasar bildirimi için gerekli kontroller ayrı olarak verilmemiş.",
            "oneri": [
                "Paket mümkünse teslimat sırasında dışarıdan kontrol edilmelidir.",
                "Görünür hasar varsa kargo görevlisinden hasar tespit tutanağı istenmelidir.",
                "Paket ve ürün hasarı fotoğrafla belgelenmelidir.",
                "Teslim sonrası fark edilen iç hasar veya çalışmama durumu gecikmeden bildirilmelidir.",
                "İade veya değişim değerlendirmesi ürün durumu ve stok bilgisine göre yapılmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, tutanak ve görsel belge gereksinimini belirtmiyor.",
            "oneri": "Pakette görünür hasar varsa teslimat sırasında kontrol ederek kargo görevlisinden hasar tespit tutanağı isteyin ve fotoğraf çekin. Hasarı paketi açtıktan sonra fark ettiyseniz ürün ve ambalaj görselleriyle iade veya değişim talebi oluşturun.",
        },
    },
    "SHIPPING_DELIVERY_PROCESS_001": {
        "kapsam": {
            "neden": "Genel kalıp, teslimatın başlangıç ve bitiş aşamalarını açıkça sınırlamıyor.",
            "oneri": "Bu süreç, ödeme sonrası sipariş onayından ürünün depoda hazırlanması, kargo firmasına teslimi, taşınması, dağıtıma çıkarılması ve kullanıcıya teslim edilmesine kadar olan aşamalar için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; teslimatın başlayabilmesi ve takip edilebilmesi için gereken temel koşullar belirtilmiyor.",
            "oneri": [
                "Sipariş ve ödeme işlemi başarıyla tamamlanmış olmalıdır.",
                "Ürün depoda hazırlanıp paketlenmelidir.",
                "Paket kargo firmasına teslim edilerek takip numarası oluşturulmalıdır.",
                "Teslimat adresi ve iletişim bilgileri doğru olmalıdır.",
                "Hava, tatil veya operasyon yoğunluğu teslimat süresini etkileyebilir.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt teslimat aşamalarını veya takip yöntemini açıklamıyor.",
            "oneri": "Siparişiniz onaylandıktan sonra hazırlanır, kargo firmasına teslim edilir ve takip numarası oluşturulur. Güncel aşamayı Siparişlerim bölümünden izleyebilirsiniz; hareketler uzun süre güncellenmez veya tahmini süre aşılırsa destek talebi oluşturabilirsiniz.",
        },
    },
    "SHIPPING_ESTIMATED_DATE_001": {
        "kapsam": {
            "neden": "Genel kalıp, tahmini tarihin garanti olmadığını ve hangi siparişlerde güncellenebileceğini belirtmiyor.",
            "oneri": "Bu süreç, sipariş oluşturulduktan sonra depo, kargo firması, teslimat bölgesi ve operasyon koşullarına göre hesaplanan tahmini teslimat tarihi veya tarih aralığının gösterildiği siparişler için geçerlidir.",
        },
        "adimlar": {
            "neden": "Alan boş; kullanıcı tahmini tarihi nereden ve nasıl kontrol edeceğini göremiyor.",
            "oneri": [
                "Kullanıcı hesabına giriş yapar.",
                "Siparişlerim bölümünden ilgili siparişi açar.",
                "Tahmini teslimat tarihini ve güncel sipariş durumunu kontrol eder.",
                "Sipariş birden fazla pakete bölündüyse her paketin tarihini ayrı inceler.",
                "Tarih geçmiş veya sürekli ileri alınmışsa kargo hareketlerini kontrol ederek destek talebi oluşturur.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, tarihin tahmin olduğunu ve kontrol noktasını açıklamıyor.",
            "oneri": "Tahmini teslimat tarihi kesin garanti değil, mevcut depo ve kargo koşullarına göre hesaplanan bir öngörüdür. Güncel tarihi Siparişlerim bölümünden kontrol edebilirsiniz; tarih geçtiği halde hareket yoksa takip bilgileriyle destek ekibine başvurun.",
        },
    },
    "SHIPPING_LATE_DELIVERY_001": {
        "kapsam": {
            "neden": "Genel kalıp, gecikmenin neye göre belirlendiğini açıklamıyor.",
            "oneri": "Bu süreç, siparişin sistemde gösterilen tahmini teslimat tarihini aşmasına rağmen teslim edilmediği veya kargo hareketlerinin uzun süre güncellenmediği gönderiler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; normal gecikme ile inceleme gerektiren gecikme ayrıştırılmamış.",
            "oneri": [
                "Tahmini teslimat tarihi geçmiş olmalıdır.",
                "Güncel kargo hareketleri ve varsa yeni tahmini tarih kontrol edilmelidir.",
                "Adres ve iletişim bilgileri doğru olmalıdır.",
                "Kampanya yoğunluğu, hava koşulları, tatiller veya bölgesel aksaklıklar dikkate alınmalıdır.",
                "Kargo uzun süre aynı statüde kalır veya bilgi alınamazsa inceleme başlatılmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, gecikmede yapılacak kontrolleri ve destek eşiğini belirtmiyor.",
            "oneri": "Tahmini teslimat tarihi geçtiyse kargo hareketlerini, güncellenen teslimat tarihini ve adres bilgilerinizi kontrol edin. Gönderi uzun süre aynı durumda kalıyorsa veya kargo firması bilgi veremiyorsa takip numaranızla destek ekibine başvurabilirsiniz.",
        },
    },
    "SHIPPING_REDELIVERY_001": {
        "kapsam": {
            "neden": "Genel kalıp, ilk teslimat denemesinin başarısız olması koşulunu belirtmiyor.",
            "oneri": "Bu süreç, ilk teslimat denemesi başarısız olan, teslim edilemedi durumuna geçen veya şubeye dönen paketin yeniden dağıtıma çıkarılması mümkün olan gönderiler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; yeniden teslimatın hangi şartlarda mümkün olduğu belirtilmiyor.",
            "oneri": [
                "İlk teslimat denemesi başarısız olmuş veya paket şubeye dönmüş olmalıdır.",
                "Paket göndericiye iade sürecine alınmamış olmalıdır.",
                "Adres ve telefon bilgileri doğru ve teslimata uygun olmalıdır.",
                "Kargo firması gönderi için yeniden dağıtım planı oluşturabilmelidir.",
                "Yeniden teslimat seçeneği yoksa şubeden teslim alma veya destek süreci değerlendirilmelidir.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, yeniden dağıtımın nasıl kontrol edileceğini açıklamıyor.",
            "oneri": "İlk teslimat başarısız olduysa kargo takip durumunu ve yeniden dağıtım planını kontrol edin; adres ve telefon bilgilerinizin doğru olduğundan emin olun. Yeniden teslimat görünmüyorsa kargo firmasıyla veya destek ekibiyle iletişime geçin.",
        },
    },
    "SHIPPING_UNDELIVERED_001": {
        "kapsam": {
            "neden": "Genel kalıp, başarısız teslimatın nedenlerini ve sonraki seçenekleri göstermiyor.",
            "oneri": "Bu süreç, alıcının adreste bulunmaması, adres veya iletişim bilgisinin hatalı olması, adrese erişilememesi ya da operasyonel nedenlerle teslimat denemesinin tamamlanamadığı gönderiler için geçerlidir.",
        },
        "kosullar": {
            "neden": "Alan boş; teslim edilemedi statüsünün doğrulanması ve sonraki işlem koşulları ayrıştırılmamış.",
            "oneri": [
                "Kargo firması teslimat denemesi yapmış ve gönderiyi teslim edilemedi olarak işaretlemiş olmalıdır.",
                "Adres, kapı numarası ve telefon bilgileri kontrol edilmelidir.",
                "Paketin şubede mi yoksa yeniden dağıtım planında mı olduğu incelenmelidir.",
                "Göndericiye iade başlamadan yeniden teslimat veya şubeden teslim seçeneği değerlendirilmelidir.",
                "Teslimat denemesi yapılmadan statü güncellendiyse destek incelemesi başlatılmalıdır.",
            ],
        },
        "standart_yanit": {
            "neden": "Genel yanıt, kullanıcının takip etmesi gereken yeniden teslimat ve şube seçeneklerini belirtmiyor.",
            "oneri": "Gönderiniz teslim edilemedi görünüyorsa adres ve telefon bilgilerinizi kontrol ederek paketin yeniden dağıtıma mı çıkacağını yoksa şubeden mi alınacağını takip edin. Teslimat denemesi yapılmadıysa veya durum güncellenmiyorsa takip numaranızla destek ekibine başvurun.",
        },
    },
}


REASON_EXPLANATIONS = {
    "kosullar alanı boş": "İşlemin hangi şartlarda geçerli olduğu veya ne zaman inceleme gerektiği belirtilmiyor.",
    "adimlar alanı boş": "Kullanıcının izleyeceği uygulanabilir işlem sırası bulunmuyor.",
    "kapsam: GENERIC_SCOPE_TEMPLATE": "Kapsam, başlık ve kategoriye dayalı genel bir kalıp; somut durum sınırlarını açıklamıyor.",
    "standart_yanit: GENERIC_STANDARD_ANSWER": "Yanıt, konuya özgü bilgi vermeyen genel destek şablonu.",
    "tanim: SAME_AS_PURPOSE_FIRST_SENTENCE": "Tanım, amaç alanının ilk cümlesini tekrar ediyor.",
    "genel_bilgiler: SAME_AS_DEFINITION": "Genel bilgiler, tanımla aynı; ek açıklama sağlamıyor.",
}


def suggestion_for_reason(reason: str) -> str:
    if reason == "kosullar alanı boş":
        return "Kaynak metindeki yapılabilir/yapılamaz durumları ve inceleme eşiklerini `kosullar` listesine taşı."
    if reason == "adimlar alanı boş":
        return "Kullanıcının ekrandan veya destek üzerinden izleyeceği sıralı adımları ekle."
    if reason.startswith("kapsam:"):
        return "Genel şablonu, işlemin geçerli olduğu sipariş/ürün/kullanıcı ve durum sınırlarıyla değiştir."
    if reason.startswith("standart_yanit:"):
        return "Konuya özgü ilk kontrolü, beklenen sonucu ve gerekiyorsa destek yönlendirmesini içeren kısa yanıt yaz."
    if reason.startswith("tanim:"):
        return "Amaçtan bağımsız, kavramın ne olduğunu tek cümlede tanımla."
    if reason.startswith("genel_bilgiler:"):
        return "Tanımı tekrarlamak yerine işleyişi, önemli ayrımları ve kullanıcıya etkisini açıkla."
    return "Alanı kaynak içerikle karşılaştırıp konuya özgü hale getir."


def render_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [f"  - {item}" for item in value]
    return [f"> {value}"]


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    records = audit["weak_or_repetitive_documents"]["records"]
    high = [record for record in records if record["review_level"] == "HIGH"]
    medium = [record for record in records if record["review_level"] == "MEDIUM"]

    assert len(high) == 13, f"Beklenen 13 HIGH kayıt yerine {len(high)} bulundu"
    assert set(record["id"] for record in high) == set(HIGH_FIXES)

    lines = [
        "# RAG Dokümanları Manuel Düzeltme Planı",
        "",
        "## Kapsam",
        "",
        "- Kaynak denetim: `data/reports/rag_document_audit.json`",
        "- Manuel inceleme önerilen toplam kayıt: **35**",
        "- Yüksek öncelik: **13**",
        "- Orta öncelik: **22**",
        "- Bu plan `data/processed/rag_documents.jsonl` dosyasını değiştirmez.",
        "- Öneri metinleri mevcut kayıt içeriğine dayanır; yeni süre, limit veya politika eklenmemiştir.",
        "",
        "## Uygulama sırası",
        "",
        "1. Boş `kosullar` ve `adimlar` alanlarını tamamla.",
        "2. Genel `kapsam` kalıplarını somut durum sınırlarıyla değiştir.",
        "3. Genel `standart_yanit` kalıplarını konuya özgü aksiyonlarla değiştir.",
        "4. `amac` cümlesini tekrar eden `tanim` alanlarını bağımsız tanımlara dönüştür.",
        "5. Düzeltme sonrasında şema, ID ve referans denetimini yeniden çalıştır.",
        "",
        "## Yüksek öncelikli 13 doküman",
        "",
    ]

    for index, record in enumerate(high, start=1):
        fixes = HIGH_FIXES[record["id"]]
        lines.extend(
            [
                f"### {index}. {record['title']} — `{record['id']}`",
                "",
                f"- Öncelik: **HIGH**",
                f"- Denetim puanı: **{record['severity_score']}**",
                f"- Kategori: `{record['category']}`",
                f"- Sorunlu alanlar: {', '.join(f'`{field}`' for field in fixes)}",
                "",
            ]
        )
        for field, detail in fixes.items():
            lines.extend(
                [
                    f"#### `{field}`",
                    "",
                    f"**Neden sorunlu:** {detail['neden']}",
                    "",
                    "**Önerilen metin:**",
                    "",
                ]
            )
            lines.extend(render_value(detail["oneri"]))
            lines.append("")

    lines.extend(
        [
            "## Orta öncelikli 22 doküman",
            "",
            "Bu kayıtlar yüksek öncelikli gruptan sonra ele alınmalıdır. Aşağıdaki öneriler alan düzeyinde yapılacak değişikliğin yönünü belirtir.",
            "",
            "| Sıra | Puan | ID | Başlık | Sorunlu alanlar ve önerilen işlem |",
            "|---:|---:|---|---|---|",
        ]
    )
    for index, record in enumerate(medium, start=1):
        actions = []
        for reason in record["reasons"]:
            field = reason.split(" ", 1)[0].split(":", 1)[0]
            explanation = REASON_EXPLANATIONS.get(reason, reason)
            action = suggestion_for_reason(reason)
            actions.append(f"`{field}`: {explanation} Öneri: {action}")
        lines.append(
            f"| {index} | {record['severity_score']} | `{record['id']}` | {record['title']} | {' '.join(actions)} |"
        )

    lines.extend(
        [
            "",
            "## Tamamlama ölçütleri",
            "",
            "- Yüksek öncelikli kayıtlarda boş `kosullar` veya `adimlar` alanı kalmamalı.",
            "- `kapsam` alanı yalnızca başlık ve kategori tekrarından oluşmamalı.",
            "- `standart_yanit`, kullanıcıya konuya özgü en az bir somut kontrol veya aksiyon vermeli.",
            "- `tanim`, `amac` alanının ilk cümlesinin birebir kopyası olmamalı.",
            "- Yeni metinler kaynakta bulunmayan kesin süre, ücret, garanti veya politika içermemeli.",
            "- Düzeltme sonrasında JSONL satırları, şema, enumlar, ID/subcategory benzersizliği ve ilgili doküman referansları yeniden doğrulanmalı.",
            "",
        ]
    )

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"FIX_PLAN_OK high={len(high)} medium={len(medium)} output={OUTPUT_PATH}")


if __name__ == "__main__":
    main()
