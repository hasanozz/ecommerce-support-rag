from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..config import PROJECT_ROOT, Settings


logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump(mode="json"))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def _trace_dir(settings: Settings) -> Path:
    path = settings.pipeline_trace_dir
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


class PipelineTrace:
    def __init__(
        self,
        *,
        trace_id: str,
        settings: Settings,
        user_question: str,
        conversation_id: int,
        user_id: int,
    ) -> None:
        self.trace_id = trace_id
        self.settings = settings
        self.payload: dict[str, Any] = {
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "user_question": user_question,
            "stages": [],
        }

    @property
    def enabled(self) -> bool:
        return bool(self.settings.pipeline_trace_json)

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        self.payload[key] = _json_safe(value)

    def add_stage(self, stage: str, data: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.payload["stages"].append(
            {
                "stage": stage,
                "data": _json_safe(data),
            }
        )

    def write(self) -> None:
        if not self.enabled:
            return
        try:
            directory = _trace_dir(self.settings)
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{self.trace_id}.json"
            path.write_text(
                json.dumps(_json_safe(self.payload), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("pipeline_trace_file trace_id=%s path=%s", self.trace_id, path)
        except Exception as exc:
            logger.warning(
                "pipeline_trace_file_write_failed trace_id=%s error=%s",
                self.trace_id,
                type(exc).__name__,
            )
