from __future__ import annotations

from ..config import Settings, get_settings
from .retrieval import RetrievedChunk


SYSTEM_PROMPT = """Sen bir e-ticaret müşteri destek asistanısın.
Yalnızca verilen bilgi tabanı parçalarını kullan.
Bilgi yoksa tahmin yürütme.
Yanıtı Türkçe, kısa, net ve profesyonel yaz.
Kaynaklarda bulunmayan süre, ücret, garanti veya politika ekleme."""


class AnswerService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _extractive_answer(self, chunks: list[RetrievedChunk]) -> str:
        standard = next(
            (chunk.content for chunk in chunks if chunk.section == "standart_yanit"),
            None,
        )
        if standard:
            return standard
        selected = []
        for chunk in chunks:
            if chunk.content not in selected:
                selected.append(chunk.content)
            if len(selected) == 2:
                break
        return "\n\n".join(selected)

    async def generate(
        self, query: str, chunks: list[RetrievedChunk]
    ) -> str:
        # MVP retrieval aşamasında dış veya yerel LLM çağrısı yapılmaz.
        # İleride sağlayıcı eklendiğinde bu servis arayüzü korunabilir.
        return self._extractive_answer(chunks)
