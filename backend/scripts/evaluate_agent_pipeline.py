from __future__ import annotations

import asyncio
import re
import sys

from backend.app.api.routes.chat import _with_agent_actions
from backend.app.services.ai_agent_service import AiAgentService
from backend.app.services.ai_guardrail_service import AiGuardrailService
from backend.app.services.chat_context_service import ChatContextService
from backend.app.services.openai_service import OpenAIChatService
from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


ACTOR = {
    "id": "10000000-0000-4000-8000-000000000001",
    "role": "nutritionist",
}
CHAT = {"id": "40000000-0000-4000-8000-000000000001"}
CONTEXT = {
    "patient": None,
    "profile": None,
    "nutritionist": {"id": "30000000-0000-4000-8000-000000000001"},
    "nutritionist_profile": {
        "id": ACTOR["id"],
        "role": "nutritionist",
        "full_name": "Nutricionista de teste",
    },
    "workspace_summary": {"patients_count": 0, "patients_index": []},
    "main_metrics": [],
    "variable_metrics": [],
    "conditions": [],
    "diets": [],
    "workouts": [],
    "imports": [],
}


class ReadOnlyEvaluationWorkspace:
    """Uses the real TACO catalog but never persists evaluation data."""

    def __init__(self) -> None:
        self.taco = SupabaseWorkspaceService()
        self.logs = []

    async def get_authenticated_profile(self, token):
        return ACTOR

    async def get_ai_conversation_state(self, **kwargs):
        return None

    async def clear_ai_conversation_state(self, state_id):
        return None

    async def insert_ai_action_log(self, payload):
        self.logs.append(payload)
        return {"id": f"eval-log-{len(self.logs)}", **payload}

    async def search_taco_foods(self, **kwargs):
        return await self.taco.search_taco_foods(**kwargs)

    async def get_taco_food(self, food_id):
        return await self.taco.get_taco_food(food_id)

    async def find_taco_food(self, **kwargs):
        return await self.taco.find_taco_food(**kwargs)

    async def resolve_taco_food(self, **kwargs):
        return await self.taco.resolve_taco_food(**kwargs)

    async def calculate_taco_food_nutrients(self, **kwargs):
        return await self.taco.calculate_taco_food_nutrients(**kwargs)


SCENARIOS = [
    {
        "name": "exact_main",
        "message": "Quantas calorias tem 150g de arroz tipo 1 cozido segundo a tabela TACO?",
        "history": [],
        "expect": "answer",
        "expected_kcal": "192",
    },
    {
        "name": "ambiguous_main",
        "message": "Quantas calorias tem 150g de arroz segundo a tabela TACO?",
        "history": [],
        "expect": "clarification",
    },
    {
        "name": "informal_order",
        "message": "150g arroz integral cozido tem quantas kcal?",
        "history": [],
        "expect": "answer",
        "expected_kcal": "186",
    },
    {
        "name": "context_follow_up",
        "message": "E em 150g?",
        "history": [
            {"role": "user", "content": "Considere arroz integral cozido."},
            {
                "role": "assistant",
                "content": "Certo, vou considerar arroz integral cozido.",
            },
        ],
        "expect": "answer",
        "expected_kcal": "186",
    },
    {
        "name": "not_found",
        "message": "Quantas calorias tem 150g de XYZ segundo a TACO?",
        "history": [],
        "expect": "not_found",
    },
    {
        "name": "typo",
        "message": "qtd de kcal em 150 gramas de arros tipo 1 cozido?",
        "history": [],
        "expect": "answer",
        "expected_kcal": "192",
    },
    {
        "name": "multiple_foods",
        "message": (
            "Quantas calorias tem 150g de arroz tipo 1 cozido e "
            "100g de feijão carioca cozido segundo a TACO?"
        ),
        "history": [],
        "expect": "multiple",
    },
]


async def run_scenario(scenario: dict) -> tuple[str, str, list[dict], list[str]]:
    workspace = ReadOnlyEvaluationWorkspace()
    ai = OpenAIChatService()
    agent = AiAgentService(workspace, ai)
    message = {"id": "50000000-0000-4000-8000-000000000001"}
    actions = await agent.run(
        chat=CHAT,
        chat_scope="nutritionist",
        context=dict(CONTEXT),
        history=scenario["history"],
        reasoning_level="medium",
        token="evaluation-token",
        user_message=scenario["message"],
        user_message_record=message,
    )
    system_prompt = ChatContextService(workspace=object()).build_system_prompt(
        dict(CONTEXT),
        scenario["message"],
        scenario["history"],
        "medium",
        "nutritionist",
    )
    chunks = []
    async for chunk in ai.stream_chat(
        system_prompt=_with_agent_actions(system_prompt, actions),
        history=scenario["history"],
        reasoning_level="medium",
        user_message=scenario["message"],
    ):
        chunks.append(chunk)
    generated = "".join(chunks).strip()
    validation = AiGuardrailService().validate_output(
        generated,
        actor=ACTOR,
        context=CONTEXT,
        agent_actions=actions,
    )
    answer = validation.content
    failures = []
    normalized = answer.lower()
    tools = [action.get("tool") for action in actions]

    if "resolve_taco_nutrition" not in tools:
        failures.append("resolve_taco_nutrition não foi usada")
    if scenario["expect"] == "answer":
        if scenario["expected_kcal"] not in answer:
            failures.append(f"não apresentou {scenario['expected_kcal']} kcal")
        if "taco" not in normalized:
            failures.append("não citou TACO")
    elif scenario["expect"] == "clarification":
        if "?" not in answer:
            failures.append("não pediu esclarecimento")
        if re.search(r"\b\d+(?:[,.]\d+)?\s*kcal\b", normalized):
            failures.append("apresentou kcal apesar da ambiguidade")
    elif scenario["expect"] == "not_found":
        if not any(term in normalized for term in ("não encontrei", "nao encontrei")):
            failures.append("não informou ausência na TACO")
    elif scenario["expect"] == "multiple":
        successful_resolutions = [
            action
            for action in actions
            if action.get("tool") == "resolve_taco_nutrition"
            and action.get("success") is True
        ]
        if len(successful_resolutions) != 2:
            failures.append("não resolveu os dois alimentos")
        if "arroz" not in normalized or "feij" not in normalized:
            failures.append("resposta final não cobre os dois alimentos")
    if not validation.allowed:
        failures.append(f"guardrail substituiu a saída: {validation.category}")
    return answer, generated, actions, failures


async def main() -> int:
    failed = False
    selected_names = set(sys.argv[1:])
    scenarios = [
        scenario
        for scenario in SCENARIOS
        if not selected_names or scenario["name"] in selected_names
    ]
    for scenario in scenarios:
        answer, generated, actions, failures = await run_scenario(scenario)
        failed = failed or bool(failures)
        action_summary = [
            f"{action.get('tool')}:{action.get('status')}:{(action.get('result') or {}).get('resolution')}"
            for action in actions
        ]
        print(
            f"\n[{scenario['name']}]\n"
            f"Usuário: {scenario['message']}\n"
            f"Tools: {action_summary}\n"
            f"IA: {answer}\n"
            f"Gerada antes do guardrail: {generated if answer != generated else '[igual]'}\n"
            f"Checks: {'OK' if not failures else '; '.join(failures)}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
