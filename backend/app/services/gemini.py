from __future__ import annotations

import json
import logging
import re
import asyncio

import httpx

from ..config import Settings, get_settings
from .gemini_prompts import (
    ANSWER_SYSTEM_INSTRUCTION,
    CLASSIFIER_SYSTEM_INSTRUCTION,
    REWRITE_SYSTEM_INSTRUCTION,
    build_answer_user_prompt,
    build_classifier_user_prompt,
    build_rewrite_user_prompt,
)


ALLOWED_CATEGORIES = [
    "SIPARIS",
    "IADE",
    "ODEME",
    "KARGO_TESLIMAT",
    "HESAP_GUVENLIK",
    "KAMPANYA_PUAN",
    "GENEL_DESTEK",
]
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
logger = logging.getLogger(__name__)


class GeminiServiceError(RuntimeError):
    pass


class GeminiService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.last_usage: dict = {}
        self.last_trace: dict = {}

    @property
    def enabled(self) -> bool:
        return (
            self.settings.llm_provider == "gemini"
            and bool(self.settings.gemini_api_key.get_secret_value())
        )

    def model_name(self, *, use_dev_model: bool = False) -> str:
        return (
            self.settings.gemini_model_dev
            if use_dev_model
            else self.settings.gemini_model
        )

    async def _generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        system_instruction: str,
        model_name: str | None = None,
        use_dev_model: bool = False,
        max_attempts: int | None = None,
    ) -> dict:
        selected_model = model_name or self.model_name(use_dev_model=use_dev_model)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{selected_model}:generateContent"
        )
        request_body = {
            "systemInstruction": {
                "parts": [{"text": system_instruction}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
            ],
        }
        self.last_trace = {
            "model": selected_model,
            "system_instruction_preview": system_instruction[:1200],
            "prompt_preview": prompt[:1200],
            "prompt_length": len(prompt),
            "full_prompt": prompt if self.settings.pipeline_trace_prompts else None,
        }
        attempts = max(
            1,
            max_attempts
            if max_attempts is not None
            else self.settings.gemini_max_retries,
        )
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.post(
                        url,
                        headers={
                            "x-goog-api-key": (
                                self.settings.gemini_api_key.get_secret_value()
                            )
                        },
                        json=request_body,
                    )
                    if (
                        response.status_code in RETRYABLE_STATUS_CODES
                        and attempt + 1 < attempts
                    ):
                        delay = self.settings.gemini_retry_base_seconds * (
                            2**attempt
                        )
                        logger.warning(
                            "Gemini geçici hata döndürdü; model=%s status=%s "
                            "retry=%s/%s",
                            selected_model,
                            response.status_code,
                            attempt + 1,
                            attempts - 1,
                        )
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    self.last_usage = payload.get("usageMetadata", {})
                    text = payload["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text)
                    self.last_trace.update(
                        {
                            "status_code": response.status_code,
                            "response_preview": text[:1200],
                            "response_length": len(text),
                            "parsed_response": parsed,
                            "usage": self.last_usage,
                        }
                    )
                    return parsed
                except (httpx.HTTPError, asyncio.TimeoutError, TimeoutError, KeyError, ValueError, json.JSONDecodeError) as exc:
                    if attempt + 1 < attempts and not isinstance(
                        exc, httpx.HTTPStatusError
                    ):
                        await asyncio.sleep(
                            self.settings.gemini_retry_base_seconds * (2**attempt)
                        )
                        continue
                    status_code = (
                        exc.response.status_code
                        if isinstance(exc, httpx.HTTPStatusError)
                        else None
                    )
                    body_preview = None
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                        body_preview = exc.response.text[:1200]
                    self.last_trace.update(
                        {
                            "error": {
                                "exception_type": type(exc).__name__,
                                "message": str(exc),
                                "status_code": status_code,
                                "body_preview": body_preview,
                            }
                        }
                    )
                    raise GeminiServiceError(
                        "Gemini isteği tamamlanamadı"
                        + (f" (HTTP {status_code})" if status_code else "")
                    ) from exc
        self.last_trace.update(
            {
                "error": {
                    "exception_type": "GeminiServiceError",
                    "message": "Gemini isteği tamamlanamadı.",
                    "status_code": None,
                    "body_preview": None,
                }
            }
        )
        raise GeminiServiceError("Gemini isteği tamamlanamadı.")

    async def classify(
        self,
        pii_masked_query: str,
        *,
        model_name: str | None = None,
        use_dev_model: bool = False,
    ) -> dict:
        if not self.enabled:
            raise RuntimeError("Gemini classifier kullanılamıyor.")
        prompt = build_classifier_user_prompt(pii_masked_query)
        return await self._generate_json(
            prompt,
            {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ALLOWED_CATEGORIES},
                    "subcategory": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"],
                    },
                    "expected_action": {
                        "type": "string",
                        "enum": [
                            "RAG_ANSWER",
                            "ASK_CLARIFICATION",
                            "REJECT",
                            "CREATE_TICKET",
                        ],
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": [
                    "category",
                    "subcategory",
                    "priority",
                    "expected_action",
                ],
            },
            system_instruction=CLASSIFIER_SYSTEM_INSTRUCTION,
            model_name=model_name,
            use_dev_model=use_dev_model,
            max_attempts=1,
        )

    async def rewrite(
        self,
        safe_query: str,
        history: list[str],
        *,
        model_name: str | None = None,
        use_dev_model: bool = False,
    ) -> dict:
        if not self.enabled:
            return {
                "canonical_query": safe_query,
                "category": "GENEL_DESTEK",
                "is_in_scope": True,
            }
        prompt = build_rewrite_user_prompt(safe_query, history)
        return await self._generate_json(
            prompt,
            {
                "type": "object",
                "properties": {
                    "canonical_query": {"type": "string"},
                    "category": {"type": "string", "enum": ALLOWED_CATEGORIES},
                    "is_in_scope": {"type": "boolean"},
                },
                "required": ["canonical_query", "category", "is_in_scope"],
            },
            system_instruction=REWRITE_SYSTEM_INSTRUCTION,
            model_name=model_name,
            use_dev_model=use_dev_model,
            max_attempts=1,
        )

    async def answer(
        self,
        canonical_query: str,
        conversation_history: list[str],
        customer_context: str,
        product_context: str,
        llm_context: str,
        few_shots: list[dict],
        available_sources: list[dict] | None = None,
        *,
        original_user_message: str | None = None,
        resolved_entities: dict | None = None,
        evidence_pack: dict | None = None,
        router_json: dict | None = None,
        answer_scope: dict | None = None,
        compact_context: dict | None = None,
        deterministic_draft: str | None = None,
        model_name: str | None = None,
        use_dev_model: bool = False,
    ) -> dict:
        if not self.enabled:
            return {
                "answer": "",
                "cited_doc_ids": [],
            }
        prompt = build_answer_user_prompt(
            canonical_query,
            conversation_history,
            customer_context,
            product_context,
            llm_context,
            few_shots,
            available_sources,
            original_user_message=original_user_message,
            resolved_entities=resolved_entities,
            evidence_pack=evidence_pack,
            router_json=router_json,
            answer_scope=answer_scope,
            compact_context=compact_context,
            deterministic_draft=deterministic_draft,
        )
        return await self._generate_json(
            prompt,
            {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "cited_doc_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["answer", "cited_doc_ids"],
            },
            system_instruction=ANSWER_SYSTEM_INSTRUCTION,
            model_name=model_name,
            use_dev_model=use_dev_model,
            max_attempts=2,
        )


def guard_llm_output(answer: str, allowed_doc_ids: set[str]) -> str:
    del allowed_doc_ids  # Citation IDs are validated by the pipeline.
    cleaned = re.sub(r"<[^>]+>", " ", answer)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    lowered = cleaned.casefold()
    forbidden = ["api key", "system prompt", "developer message", "gizli talimat"]
    action_claim_patterns = [
        r"(sizin adınıza|adınıza).{0,80}(destek kayd[ıi]|ticket).{0,80}(oluştur|olustur|aç|ac)",
        r"(destek kayd[ıi]|ticket).{0,80}(oluşturacağım|olusturacagim|oluşturuyorum|olusturuyorum|oluşturdum|olusturdum|açacağım|acacagim|açıyorum|aciyorum|açtım|actim)",
        r"(destek kayd[ıi]|ticket).{0,80}(oluşturuldu|olusturuldu|açıldı|acildi)",
        r"(ekibimiz|destek ekibimiz).{0,80}(iletişime geçecek|iletisime gececek|sizinle iletişime|sizinle iletisime)",
    ]
    has_unperformed_action_claim = any(
        re.search(pattern, lowered, flags=re.IGNORECASE)
        for pattern in action_claim_patterns
    )
    if (
        not cleaned
        or len(cleaned) > 4000
        or any(item in lowered for item in forbidden)
        or has_unperformed_action_claim
    ):
        return ""
    return cleaned
