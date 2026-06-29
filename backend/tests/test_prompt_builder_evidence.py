from backend.app.services.gemini_prompts import (
    ANSWER_SYSTEM_INSTRUCTION,
    build_answer_user_prompt,
)


def evidence_pack():
    return {
        "product_evidence": [
            {
                "source": "PRODUCT_CATALOG",
                "entity_type": "PRODUCT",
                "entity_id": 15,
                "purpose": "PRODUCT_CAPACITY",
                "data": {"capacity_ml": 120},
                "provenance": {"source": "PRODUCT_CATALOG", "record_id": 15},
            }
        ],
        "order_evidence": [],
        "payment_evidence": [],
        "coupon_evidence": [],
        "cart_evidence": [],
        "return_evidence": [],
        "review_evidence": [],
        "missing_evidence": [
            {
                "source": "ORDER_LEDGER",
                "entity_type": "ORDER",
                "purpose": "ORDER_STATUS",
                "reason": "ORDER_ID_MISSING",
            }
        ],
        "warnings": ["EVIDENCE_FETCHER_ERROR:RuntimeError"],
    }


def prompt(**overrides):
    values = {
        "canonical_query": "Çay bardağının doğrulanmış hacmi nedir?",
        "conversation_history": ["USER: Çay bardağı kaç ml?"],
        "customer_context": "legacy customer context",
        "product_context": "legacy product context",
        "llm_context": "İade politikası prosedür metni",
        "few_shots": [],
        "available_sources": [{"doc_id": "POLICY_1", "title": "İade"}],
        "original_user_message": "çay bardağı kaç ml?",
        "resolved_entities": {"product_id": 15},
        "evidence_pack": evidence_pack(),
        "answer_scope": {
            "evidence_only": True,
            "requested_purposes": ["PRODUCT_CAPACITY"],
            "actions_performed": False,
        },
    }
    values.update(overrides)
    return build_answer_user_prompt(**values)


def test_prompt_contains_structured_evidence_pack():
    result = prompt()

    assert "<EVIDENCE_PACK>" in result
    assert '"product_evidence"' in result
    assert '"capacity_ml": 120' in result


def test_prompt_contains_original_and_rewritten_messages():
    result = prompt()

    assert "<ORIGINAL_USER_MESSAGE>" in result
    assert "çay bardağı kaç ml?" in result
    assert "<REWRITTEN_MESSAGE>" in result
    assert "Çay bardağının doğrulanmış hacmi nedir?" in result


def test_prompt_contains_resolved_entities_and_missing_evidence():
    result = prompt()

    assert "<RESOLVED_ENTITIES>" in result
    assert '"product_id": 15' in result
    assert "<MISSING_EVIDENCE>" in result
    assert "ORDER_ID_MISSING" in result


def test_db_evidence_and_support_policy_are_separate():
    result = prompt()

    assert "<EVIDENCE_PACK>" in result
    assert "<SUPPORT_POLICY_CONTEXT>" in result
    assert "<KNOWLEDGE_BASE_CONTEXT>" in result
    assert "<LEGACY_CONTEXT>" in result


def test_unsafe_evidence_warning_details_are_removed():
    pack = evidence_pack()
    pack["warnings"].append("traceback: database password=secret")

    result = prompt(evidence_pack=pack)

    assert "EVIDENCE_FETCHER_ERROR:RuntimeError" in result
    assert "database password" not in result
    assert "traceback" not in result.casefold()


def test_prompt_explicitly_forbids_guessing_without_evidence():
    result = prompt()

    assert "evidence yoksa tahmin yapma" in result.casefold()
    assert "başka ürün, sipariş veya kupon" in result.casefold()


def test_prompt_forbids_unperformed_action_claims():
    result = prompt()

    assert "gerçekleştirilmemiş işlem iddia etme" in result.casefold()
    assert "backend gerçekten bir işlem yapmadıkça" in ANSWER_SYSTEM_INSTRUCTION.casefold()


def test_answer_scope_is_visible_to_model():
    result = prompt()

    assert "<ANSWER_SCOPE>" in result
    assert '"evidence_only": true' in result
    assert '"actions_performed": false' in result
