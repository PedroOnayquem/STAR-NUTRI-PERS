from __future__ import annotations

import json

from fastapi import HTTPException, status

from .supabase_workspace_service import SupabaseWorkspaceService


REASONING_SETTINGS = {
    "low": {
        "label": "Pensamento Baixo",
        "history_limit": 6,
        "metric_limit": 12,
        "condition_limit": 10,
        "instruction": (
            "Responda de forma rapida, direta e objetiva. Priorize apenas o "
            "essencial e evite analises longas."
        ),
    },
    "medium": {
        "label": "Pensamento Medio",
        "history_limit": 12,
        "metric_limit": 30,
        "condition_limit": 20,
        "instruction": (
            "Equilibre objetividade com uma explicacao suficiente para tomada "
            "de decisao segura."
        ),
    },
    "high": {
        "label": "Pensamento Alto",
        "history_limit": 20,
        "metric_limit": 60,
        "condition_limit": 40,
        "instruction": (
            "Analise o caso com mais profundidade, conectando dieta, treino, "
            "metricas, aderencia e pontos de atencao."
        ),
    },
    "ultra": {
        "label": "Pensamento Altissimo",
        "history_limit": 32,
        "metric_limit": 120,
        "condition_limit": 80,
        "instruction": (
            "Faca uma analise profunda, estruturada e criteriosa. Explique "
            "hipoteses, limites, riscos e proximos pontos a observar."
        ),
    },
}


class ChatContextService:
    def __init__(self, workspace: SupabaseWorkspaceService) -> None:
        self.workspace = workspace

    async def resolve_context(
        self,
        token: str,
        patient_id: str | None,
        session_id: str | None,
    ) -> tuple[dict, dict, str]:
        _, patient, sender = await self.workspace.resolve_chat_patient(
            token,
            patient_id=patient_id,
            session_id=session_id,
        )

        if sender == "patient":
            context = await self.workspace.get_patient_context_for_patient(token)
        elif sender == "nutritionist":
            context = await self.workspace.get_patient_context_for_nutritionist(
                token,
                patient["id"],
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perfil sem permissao para chat clinico.",
            )

        session = await self.workspace.ensure_chat_session(patient["id"], session_id)
        return context, session, sender

    def build_system_prompt(
        self,
        context: dict,
        user_message: str,
        history: list[dict[str, str]],
        reasoning_level: str,
    ) -> str:
        settings = self.get_reasoning_settings(reasoning_level)
        patient = context["patient"]
        profile = context["profile"] or {}
        active_diet = next(
            (diet for diet in context["diets"] if diet.get("is_active")),
            None,
        )
        active_workout = next(
            (workout for workout in context["workouts"] if workout.get("is_active")),
            None,
        )

        clinical_context = {
            "paciente": {
                "nome": profile.get("full_name"),
                "objetivo": patient.get("objective"),
                "observacoes": patient.get("notes"),
                "genero": patient.get("gender"),
                "nascimento": patient.get("birth_date"),
            },
            "nivel_de_inteligencia": settings["label"],
            "condicoes_clinicas": context["conditions"][: settings["condition_limit"]],
            "metricas_principais": context["main_metrics"],
            "metricas_variaveis_recentes": context["variable_metrics"][
                : settings["metric_limit"]
            ],
            "dieta_ativa": active_diet,
            "treino_ativo": active_workout,
        }

        return (
            "Você é a IA assistente do sistema Star Nutri.\n\n"
            "Você ajuda nutricionistas e pacientes no acompanhamento nutricional.\n"
            "Você deve responder com base nos dados reais cadastrados no sistema.\n\n"
            "Regras obrigatórias:\n"
            "- Você NÃO substitui nutricionista.\n"
            "- Você NÃO substitui médico.\n"
            "- Você NÃO diagnostica doenças.\n"
            "- Você NÃO prescreve medicamentos.\n"
            "- Você NÃO cria dietas novas sem autorização do nutricionista.\n"
            "- Você NÃO altera treinos sem autorização do nutricionista.\n"
            "- Você NÃO promete resultados.\n"
            "- Você sempre considera os dados reais cadastrados.\n"
            "- Você responde com segurança, clareza e responsabilidade.\n"
            "- Quando houver risco à saúde, oriente procurar atendimento profissional.\n\n"
            "Nivel de raciocinio solicitado:\n"
            f"{settings['label']} - {settings['instruction']}\n\n"
            "Contexto do paciente:\n"
            f"{json.dumps(clinical_context, ensure_ascii=False, default=str)}\n\n"
            "Histórico recente da conversa:\n"
            f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
            "Mensagem do usuário:\n"
            f"{user_message}\n\n"
            "Responda de forma útil, objetiva e profissional."
        )

    def get_reasoning_settings(self, reasoning_level: str) -> dict:
        return REASONING_SETTINGS.get(reasoning_level, REASONING_SETTINGS["medium"])

    def build_history(self, context: dict, session_id: str) -> list[dict[str, str]]:
        messages = [
            message
            for message in reversed(context["recent_messages"])
            if message.get("session_id") == session_id
        ][-12:]

        history: list[dict[str, str]] = []
        for message in messages:
            sender = message.get("sender")
            if sender == "ai":
                role = "assistant"
            else:
                role = "user"
            history.append({"role": role, "content": message.get("content", "")})

        return history

    def build_history_from_messages(
        self,
        messages: list[dict],
        *,
        exclude_message_id: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, str]]:
        scoped_messages = [
            message
            for message in messages
            if not exclude_message_id or message.get("id") != exclude_message_id
        ][-limit:]

        history: list[dict[str, str]] = []
        for message in scoped_messages:
            sender = message.get("sender")
            role = "assistant" if sender == "ai" else "user"
            history.append({"role": role, "content": message.get("content", "")})

        return history
