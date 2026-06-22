"""Apply a narrowly scoped quick cleanup to current MEDIUM audit records."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSONL_PATH = ROOT / "data" / "processed" / "rag_documents.jsonl"
AUDIT_PATH = ROOT / "data" / "reports" / "rag_document_audit.json"

FIXES = {
    "ACCOUNT_SECURITY_PERSONAL_DATA_001": {
        "standart_yanit": (
            "Kişisel verileriniz hesap, sipariş, teslimat, destek ve güvenlik süreçlerinin "
            "yürütülmesi amacıyla korunarak işlenir. Hesabınızda tanımadığınız bir değişiklik "
            "veya veri güvenliği şüphesi görürseniz hesap güvenliği kontrollerini yaparak "
            "destek ekibine başvurabilirsiniz."
        ),
    },
    "RETURN_CAMPAIGN_PRODUCT_001": {
        "adimlar": [
            "Kullanıcı hesabına giriş yapar ve Siparişlerim bölümünden ilgili siparişi açar.",
            "İade etmek istediği kampanyalı ürünü seçerek iade talebi oluşturur.",
            "Sistem ürünün gerçek ödeme tutarını, kullanılan indirim, kupon ve puanları kontrol eder.",
            "Kısmi iadede kampanya koşulları yeniden değerlendirilir ve iade tutarı buna göre hesaplanır.",
            "Talep onaylandıktan sonra kullanıcıya iade gönderimi ve tutar bilgileri gösterilir.",
        ],
    },
    "ACCOUNT_SECURITY_CREATE_001": {
        "tanim": (
            "Hesap oluşturma, kullanıcının kimlik ve iletişim bilgileriyle NovaCart üzerinde "
            "kişisel bir üyelik kaydı açması ve hesabını doğrulamaya hazırlamasıdır."
        ),
        "genel_bilgiler": (
            "Hesap oluşturulduktan sonra kullanıcı sipariş verebilir, siparişlerini takip "
            "edebilir ve hesabına özel işlemleri yönetebilir. Her e-posta adresi ve telefon "
            "numarası yalnızca bir hesapta kullanılabilir; üyeliğin tamamlanması için gerekli "
            "bilgiler ile kullanım şartlarının onaylanması gerekir."
        ),
        "standart_yanit": (
            "Hesap oluşturmak için Kayıt Ol ekranında ad, soyad, e-posta, telefon ve şifre "
            "bilgilerinizi girip gerekli onayları tamamlayın. Kayıt sonrasında gönderilen "
            "e-posta doğrulamasını tamamlayarak hesabınızı aktif hale getirebilirsiniz."
        ),
    },
    "PAYMENT_BANK_TRANSFER_001": {
        "standart_yanit": (
            "Havale veya EFT ile ödeme için ödeme ekranında gösterilen banka hesabına sipariş "
            "tutarını gönderin ve isteniyorsa açıklama alanına sipariş numaranızı yazın. "
            "Sipariş, transfer sistem tarafından doğrulandıktan sonra onaylanır."
        ),
    },
    "PAYMENT_CASH_ON_DELIVERY_001": {
        "standart_yanit": (
            "Siparişinizde kapıda ödeme seçeneği sunuluyorsa ödeme adımında bu yöntemi seçebilirsiniz. "
            "Ödeme, kargo teslimatı sırasında tahsil edilir ve işlem tamamlandıktan sonra paket teslim edilir."
        ),
    },
    "PAYMENT_COUPON_POINT_001": {
        "standart_yanit": (
            "Ödeme ekranında kupon kodunuzu girin veya puan kullanma seçeneğini etkinleştirin. "
            "Sistem uygunluk koşullarını kontrol ederek indirimi toplam tutara yansıtır; güncellenen "
            "tutarı kontrol ettikten sonra ödemeyi tamamlayabilirsiniz."
        ),
    },
    "PAYMENT_INSTALLMENT_001": {
        "standart_yanit": (
            "Kart bilgilerinizi girdikten sonra kartınıza ve siparişinize uygun taksit seçenekleri "
            "ödeme ekranında gösterilir. İstediğiniz seçeneği seçerek banka onayından sonra "
            "siparişinizi tamamlayabilirsiniz."
        ),
    },
    "PAYMENT_REFUND_001": {
        "standart_yanit": (
            "Para iadesi onaylandıktan sonra işlem ödeme yaptığınız yöntem üzerinden başlatılır. "
            "İade durumunu sipariş detayından takip edebilir; ödeme kaydınızla uyuşmayan bir durum "
            "varsa sipariş numaranızla destek ekibine başvurabilirsiniz."
        ),
    },
    "SHIPPING_BRANCH_PICKUP_001": {
        "standart_yanit": (
            "Gönderiniz şubede bekliyor durumuna geçtiğinde bilgilendirmeyi ve şube bilgilerini "
            "kontrol edin. Paketinizi, kargo firmasının istediği kimlik veya teslim bilgileriyle "
            "ilgili şubeden teslim alabilirsiniz."
        ),
    },
    "SHIPPING_CARRIER_CHANGE_001": {
        "standart_yanit": (
            "Kargo firması sipariş sırasında seçilebilir veya sistem tarafından atanabilir. "
            "Değişiklik yalnızca lojistik süreç başlamadan önce mümkün olabilir; sipariş kargoya "
            "verildiyse mevcut firma ve takip bilgileri üzerinden süreç devam eder."
        ),
    },
    "SHIPPING_MULTIPLE_PACKAGES_001": {
        "standart_yanit": (
            "Siparişiniz ürünlerin depo veya hazırlık durumuna göre birden fazla pakete bölünebilir. "
            "Her paket için ayrı takip numarası ve teslimat durumu oluşabileceğinden paketleri "
            "Siparişlerim bölümünden ayrı ayrı takip edebilirsiniz."
        ),
    },
    "SHIPPING_TRACKING_001": {
        "standart_yanit": (
            "Siparişiniz kargoya verildikten sonra oluşan takip numarasını Siparişlerim bölümünden "
            "görüntüleyebilirsiniz. Bu numarayla transfer, şube, dağıtım ve teslimat hareketlerini "
            "kargo takip ekranından izleyebilirsiniz."
        ),
    },
    "ACCOUNT_SECURITY_DELETE_001": {
        "tanim": (
            "Hesap silme, kullanıcının hesabına erişimi kalıcı olarak kapatan ve hesaba bağlı aktif "
            "kullanım özelliklerini sonlandıran güvenlik doğrulamalı hesap yönetimi işlemidir."
        ),
        "standart_yanit": (
            "Hesabınızı silmek için Hesabım bölümündeki hesap yönetimi ekranından silme talebi "
            "başlatıp güvenlik doğrulamasını tamamlayın. İşlemi onaylamadan önce bekleyen sipariş, "
            "iade, puan ve kupon durumlarınızı kontrol edin."
        ),
    },
    "ACCOUNT_SECURITY_EMAIL_CHANGE_001": {
        "tanim": (
            "E-posta değiştirme, hesapta giriş, bildirim ve güvenlik doğrulaması için kullanılan "
            "kayıtlı e-posta adresinin yeni ve erişilebilir bir adresle güncellenmesidir."
        ),
        "standart_yanit": (
            "E-posta adresinizi Hesap Ayarları içindeki e-posta bilgileri bölümünden güncelleyebilirsiniz. "
            "Yeni adres başka bir hesapta kullanılmamalı ve değişikliğin tamamlanması için gönderilen "
            "doğrulama bağlantısı onaylanmalıdır."
        ),
    },
    "ACCOUNT_SECURITY_LOGIN_ISSUE_001": {
        "tanim": (
            "Giriş yapamama, kayıtlı e-posta veya telefon bilgisi, şifre, hesap doğrulaması, güvenlik "
            "kısıtlaması ya da geçici sistem sorunu nedeniyle kullanıcının hesabına erişememesidir."
        ),
        "standart_yanit": (
            "E-posta veya telefon bilginizi ve şifrenizi kontrol edin; hesabınız doğrulanmadıysa "
            "doğrulamayı tamamlayın. Şifrenizi hatırlamıyorsanız Şifremi Unuttum seçeneğini kullanın; "
            "hesap kilitli veya askıdaysa destek ekibine başvurun."
        ),
    },
    "ACCOUNT_SECURITY_PASSWORD_RESET_001": {
        "tanim": (
            "Şifre sıfırlama, hesabın kayıtlı e-posta adresine gönderilen kişiye özel bağlantı "
            "üzerinden eski şifrenin geçersiz kılınarak yeni bir şifre belirlenmesidir."
        ),
        "standart_yanit": (
            "Giriş ekranındaki Şifremi Unuttum seçeneğine kayıtlı e-posta adresinizi girin ve "
            "gönderilen bağlantıdan yeni şifrenizi oluşturun. E-posta görünmüyorsa spam klasörünü "
            "kontrol edin; bağlantı çalışmıyorsa yeni sıfırlama talebi oluşturun."
        ),
    },
    "ACCOUNT_SECURITY_PHONE_CHANGE_001": {
        "tanim": (
            "Telefon numarası değiştirme, hesapta iletişim ve güvenlik doğrulaması için kullanılan "
            "kayıtlı numaranın kullanıcıya ait yeni bir numarayla güncellenmesidir."
        ),
        "standart_yanit": (
            "Telefon numaranızı Hesap Ayarları içindeki telefon bilgileri bölümünden değiştirebilirsiniz. "
            "Mevcut güvenlik kontrolünü tamamladıktan sonra yeni numaraya gönderilen SMS kodunu girerek "
            "değişikliği doğrulayın."
        ),
    },
    "ACCOUNT_SECURITY_SUSPICIOUS_LOGIN_001": {
        "tanim": (
            "Şüpheli giriş bildirimi, hesabın alışılmış cihaz, konum veya giriş davranışından farklı "
            "bir erişim denemesi tespit edildiğinde kullanıcıya gönderilen güvenlik uyarısıdır."
        ),
        "standart_yanit": (
            "Bildirilen giriş size aitse cihaz ve konum bilgisini kontrol ederek işlemi doğrulayabilirsiniz. "
            "Giriş size ait değilse şifrenizi hemen değiştirin, tanımadığınız oturumları kapatın ve "
            "iki aşamalı doğrulamayı etkinleştirin."
        ),
    },
    "ACCOUNT_SECURITY_VERIFY_001": {
        "tanim": (
            "Hesap doğrulama, kayıt sırasında girilen e-posta adresinin kullanıcıya ait olduğunu "
            "doğrulama bağlantısı üzerinden teyit ederek hesabı aktif hale getiren işlemdir."
        ),
        "standart_yanit": (
            "Kayıtlı e-posta adresinize gönderilen doğrulama bağlantısını açarak hesabınızı aktif "
            "hale getirebilirsiniz. Mesaj gelmediyse spam klasörünü kontrol edin; bağlantı geçersizse "
            "yeni doğrulama e-postası talep edin."
        ),
    },
}

LIST_FIELDS = {"kosullar", "adimlar", "istisnalar", "ilgili_dokumanlar"}


def load_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate(rows: list[dict]) -> None:
    assert len(rows) == 70
    assert len({row["id"] for row in rows}) == 70
    assert len({row["subcategory"] for row in rows}) == 70
    ids = {row["id"] for row in rows}
    assert all(ref in ids for row in rows for ref in row["ilgili_dokumanlar"])
    for row in rows:
        for field, value in row.items():
            assert isinstance(value, list if field in LIST_FIELDS else str)


def main() -> None:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    medium_ids = {
        row["id"]
        for row in audit["weak_or_repetitive_documents"]["records"]
        if row["review_level"] == "MEDIUM"
    }
    assert set(FIXES).issubset(medium_ids)

    before = load_rows()
    validate(before)
    after = deepcopy(before)
    by_id = {row["id"]: row for row in after}

    planned = set()
    for record_id, fields in FIXES.items():
        for field, value in fields.items():
            assert field in {"tanim", "genel_bilgiler", "standart_yanit", "adimlar"}
            assert isinstance(value, list if field == "adimlar" else str)
            assert value not in ("", [])
            by_id[record_id][field] = value
            planned.add((record_id, field))

    actual = set()
    before_by_id = {row["id"]: row for row in before}
    after_by_id = {row["id"]: row for row in after}
    for record_id, old in before_by_id.items():
        new = after_by_id[record_id]
        for field in old:
            if old[field] != new[field]:
                actual.add((record_id, field))
    assert actual == planned

    # Personal data security is informational; no artificial steps are added.
    assert after_by_id["ACCOUNT_SECURITY_PERSONAL_DATA_001"]["adimlar"] == []
    # No scope or condition cleanup is authorized in this pass.
    assert all(
        before_by_id[record_id]["kapsam"] == after_by_id[record_id]["kapsam"]
        and before_by_id[record_id]["kosullar"] == after_by_id[record_id]["kosullar"]
        for record_id in before_by_id
    )

    validate(after)
    with JSONL_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in after:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    persisted = load_rows()
    validate(persisted)
    assert persisted == after
    counts = {
        field: sum(1 for _, changed_field in planned if changed_field == field)
        for field in ("tanim", "genel_bilgiler", "standart_yanit", "adimlar")
    }
    print(
        f"MEDIUM_QUICK_CLEANUP_OK records={len(FIXES)} fields={len(planned)} "
        f"counts={counts}"
    )


if __name__ == "__main__":
    main()
