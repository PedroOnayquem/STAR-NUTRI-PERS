from __future__ import annotations

import asyncio
import re
import sys

from backend.app.services.chat_context_service import ChatContextService
from backend.app.services.openai_service import OpenAIChatService


SYNTHETIC_CONTEXT = {
    "patient": {
        "id": "synthetic-patient",
        "objective": "Organizar a alimentação",
        "birth_date": None,
    },
    "profile": {"full_name": "Pessoa de teste"},
    "diets": [],
    "workouts": [],
    "main_metrics": [],
    "variable_metrics": [],
    "conditions": [],
    "imports": [],
}

SCENARIOS = [
    {
        "name": "acolhimento",
        "message": "Hoje eu saí da dieta 😔",
        "history": [],
    },
    {
        "name": "duvida",
        "message": "Não entendi. Pode explicar carboidrato de um jeito mais simples?",
        "history": [
            {
                "role": "assistant",
                "content": "Carboidratos são um dos macronutrientes do plano alimentar.",
            }
        ],
    },
    {
        "name": "ambiguidade",
        "message": "Quanto tem no arroz?",
        "history": [],
    },
    {
        "name": "identidade",
        "message": "Você é uma pessoa de verdade?",
        "history": [],
    },
]


async def _answer(
    ai_service: OpenAIChatService,
    context_service: ChatContextService,
    scenario: dict,
) -> str:
    prompt = context_service.build_system_prompt(
        SYNTHETIC_CONTEXT,
        scenario["message"],
        scenario["history"],
        "medium",
        "patient",
    )
    chunks = []
    async for chunk in ai_service.stream_chat(
        system_prompt=prompt,
        history=scenario["history"],
        reasoning_level="medium",
        user_message=scenario["message"],
    ):
        chunks.append(chunk)
    return "".join(chunks).strip()


def _basic_checks(name: str, answer: str) -> list[str]:
    failures = []
    normalized = answer.lower()
    if not answer:
        failures.append("resposta vazia")
    if normalized.startswith("como ia"):
        failures.append("recusa/identidade começou com 'Como IA'")
    if len(answer) > 1400:
        failures.append("resposta longa demais para o cenário curto")
    if name == "ambiguidade" and "?" not in answer:
        failures.append("não fez pergunta para resolver a ambiguidade")
    if name == "ambiguidade" and re.search(
        r"\b\d+(?:[,.]\d+)?\s*kcal\b|"
        r"\b\d+(?:[,.]\d+)?\s*(?:g|mg)\b.{0,30}\b(?:carboidrato|proteina|gordura|fibra)\b|"
        r"\b(?:carboidrato|proteina|gordura|fibra)\b.{0,30}\b\d+(?:[,.]\d+)?\s*(?:g|mg)\b",
        normalized,
    ):
        failures.append("antecipou valor nutricional sem fonte consultada")
    if name == "identidade" and not (
        "assistente de ia" in normalized or "inteligência artificial" in normalized
    ):
        failures.append("não declarou claramente a identidade de IA")
    return failures


async def main() -> int:
    ai_service = OpenAIChatService()
    context_service = ChatContextService(workspace=object())
    failed = False

    for scenario in SCENARIOS:
        answer = await _answer(ai_service, context_service, scenario)
        failures = _basic_checks(scenario["name"], answer)
        failed = failed or bool(failures)
        print(f"\n[{scenario['name']}]\nUsuário: {scenario['message']}\nIA: {answer}")
        print("Checks:", "OK" if not failures else "; ".join(failures))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
