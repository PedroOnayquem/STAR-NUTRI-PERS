from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException, status

from ..core.config import settings


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
            "temperature": generation["temperature"],
            "max_completion_tokens": generation["max_tokens"],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    self.base_url,
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"OpenAI rejeitou a requisicao: {body.decode(errors='ignore')}",
                        )

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
