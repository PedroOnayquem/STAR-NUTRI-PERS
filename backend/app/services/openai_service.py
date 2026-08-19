from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from ..core.config import settings

logger = logging.getLogger(__name__)

OPENAI_TIMEOUT = httpx.Timeout(90.0, connect=10.0, read=90.0, write=30.0)

GENERATION_SETTINGS = {
    "low": {"max_tokens": 700, "temperature": 0.2},
    "medium": {"max_tokens": 1200, "temperature": 0.3},
    "high": {"max_tokens": 1800, "temperature": 0.25},
    "ultra": {"max_tokens": 2600, "temperature": 0.2},
}


class OpenAIChatService:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY nao configurada no backend/.env.",
            )

        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.openai_model

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        reasoning_level: str,
        user_message: str,
    ) -> AsyncIterator[str]:
        generation = GENERATION_SETTINGS.get(
            reasoning_level,
            GENERATION_SETTINGS["medium"],
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": system_prompt},
                *history,
                {"role": "user", "content": user_message},
            ],
            "stream": True,
            "max_completion_tokens": generation["max_tokens"],
        }
        if _uses_gpt_5_6(self.model):
            payload["reasoning_effort"] = "none"
        elif _supports_custom_temperature(self.model):
            payload["temperature"] = generation["temperature"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    self.base_url,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        self._raise_provider_error(response)

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue

                        raw = line.removeprefix("data:").strip()
                        if raw == "[DONE]":
                            break

                        try:
                            chunk = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            yield delta
        except HTTPException:
            raise
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel conectar a OpenAI.",
            ) from None

    async def complete_with_tools(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        reasoning_level: str,
        tools: list[dict],
        user_message: str,
        forced_tool: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict:
        generation = GENERATION_SETTINGS.get(
            reasoning_level,
            GENERATION_SETTINGS["medium"],
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": system_prompt},
                *history,
                {"role": "user", "content": user_message},
            ],
            "tools": tools,
            "tool_choice": (
                {"type": "function", "function": {"name": forced_tool}}
                if forced_tool
                else "auto"
            ),
            "max_completion_tokens": (
                max_completion_tokens
                if max_completion_tokens is not None
                else min(generation["max_tokens"], 900)
            ),
        }
        if _uses_gpt_5_6(self.model):
            payload["reasoning_effort"] = "none"
        elif _supports_custom_temperature(self.model):
            payload["temperature"] = 0

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel conectar a OpenAI.",
            ) from None

        if response.status_code >= 400:
            self._raise_provider_error(response)

        try:
            body = response.json()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="O provedor de IA retornou uma resposta invalida.",
            ) from None
        message = body.get("choices", [{}])[0].get("message", {})
        return message if isinstance(message, dict) else {}

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        reasoning_level: str = "low",
        max_tokens: int = 700,
    ) -> dict:
        generation = GENERATION_SETTINGS.get(
            reasoning_level,
            GENERATION_SETTINGS["low"],
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False, default=str),
                },
            ],
            "max_completion_tokens": min(generation["max_tokens"], max_tokens),
        }
        if _uses_gpt_5_6(self.model):
            payload["reasoning_effort"] = "none"
        elif _supports_custom_temperature(self.model):
            payload["temperature"] = 0

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel conectar a OpenAI.",
            ) from None

        if response.status_code >= 400:
            self._raise_provider_error(response)

        try:
            body = response.json()
        except ValueError:
            return {}
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_json_object(content)

    def _raise_provider_error(self, response: httpx.Response) -> None:
        try:
            provider_error = response.json().get("error") or {}
        except ValueError:
            provider_error = {}
        logger.warning(
            "OpenAI request rejected: status=%s type=%s code=%s param=%s model=%s request_id=%s",
            response.status_code,
            provider_error.get("type"),
            provider_error.get("code"),
            provider_error.get("param"),
            self.model,
            response.headers.get("x-request-id"),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="O provedor de IA nao conseguiu processar a solicitacao.",
        )


def _supports_custom_temperature(model: str) -> bool:
    normalized = model.lower()
    return not normalized.startswith(("gpt-5", "o1", "o3", "o4"))


def _uses_gpt_5_6(model: str) -> bool:
    return model.lower().startswith("gpt-5.6")


def _parse_json_object(content: str) -> dict:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        return {}

    try:
        parsed = json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
