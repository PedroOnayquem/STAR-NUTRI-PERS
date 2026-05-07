from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException, status

from ..core.config import settings


class GlmService:
    def __init__(self) -> None:
        if not settings.glm_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GLM_API_KEY nao configurada no backend/.env.",
            )

        self.api_key = settings.glm_api_key
        self.base_url = (
            settings.glm_base_url
            or "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        )
        self.model = settings.glm_model or "glm-5"

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": user_message},
            ],
            "stream": True,
            "temperature": 0.3,
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
                            detail=f"GLM rejeitou a requisicao: {body.decode(errors='ignore')}",
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
                detail="Nao foi possivel conectar ao GLM 5.0.",
            ) from None
