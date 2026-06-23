from backend.app.services.privacy import mask_pii


def test_masks_common_personal_data():
    masked, findings = mask_pii(
        "Mailim test@example.com telefonum 0555 111 22 33 kart 4111 1111 1111 1111"
    )
    assert "test@example.com" not in masked
    assert "0555" not in masked
    assert "4111" not in masked
    assert {"E-POSTA", "TELEFON", "KART/NUMARA"}.issubset(findings)
