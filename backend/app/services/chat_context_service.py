from __future__ import annotations

import json

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

    async def resolve_nutritionist_context(
        self,
        token: str,
        patient_id: str,
        chat_id: str | None,
    ) -> tuple[dict, dict, str]:
        _, nutritionist, patient = await self.workspace.resolve_nutritionist_patient(
            token,
            patient_id,
        )

        context = await self.workspace.get_patient_context_for_nutritionist(
            token,
            patient["id"],
        )
        chat = await self.workspace.ensure_nutritionist_chat(
            nutritionist["id"],
            patient["id"],
            chat_id,
        )
        return context, chat, "nutritionist"

    async def resolve_patient_context(
        self,
        token: str,
        chat_id: str | None,
    ) -> tuple[dict, dict, str]:
        _, patient = await self.workspace.resolve_patient_owner(token)
        context = await self.workspace.get_patient_chat_context_for_patient(token)
        chat = await self.workspace.ensure_patient_chat(patient["id"], chat_id)
        return context, chat, "patient"

    async def resolve_context(
        self,
        token: str,
        patient_id: str | None,
        session_id: str | None,
    ) -> tuple[dict, dict, str]:
        if patient_id:
            return await self.resolve_nutritionist_context(
                token,
                patient_id,
                session_id,
            )
        return await self.resolve_patient_context(token, session_id)

    def build_system_prompt(
        self,
        context: dict,
        user_message: str,
        history: list[dict[str, str]],
        reasoning_level: str,
        chat_scope: str,
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

        if chat_scope == "patient":
            patient_context = {
                "paciente": {
                    "nome": profile.get("full_name"),
                    "objetivo": patient.get("objective"),
                },
                "nivel_de_inteligencia": settings["label"],
                "dieta_ativa": active_diet,
                "treino_ativo": active_workout,
                "metricas_recentes_informadas_pelo_paciente": context[
                    "variable_metrics"
                ][: settings["metric_limit"]],
            }

            return (
                "Você é o assistente pessoal de rotina do paciente no Star Nutri.\n\n"
                "Você conversa diretamente com o paciente, com tom claro, acolhedor e prático.\n"
                "Você pode ajudar a entender o plano ativo, organizar rotina, lembrar hidratação, "
                "tirar dúvidas gerais e sugerir perguntas para levar ao nutricionista.\n\n"
                "Limites obrigatórios deste chat pessoal:\n"
                "- Você NÃO tem acesso a análises internas do nutricionista.\n"
                "- Você NÃO deve mencionar notas clínicas privadas, hipóteses profissionais ou "
                "bastidores do atendimento.\n"
                "- Você NÃO cria uma dieta nova nem altera a dieta ativa.\n"
                "- Você NÃO cria ou altera treino.\n"
                "- Você NÃO diagnostica doenças e NÃO prescreve medicamentos.\n"
                "- Se houver sintomas importantes ou risco à saúde, oriente buscar atendimento "
                "profissional.\n\n"
                "Nivel de raciocinio solicitado:\n"
                f"{settings['label']} - {settings['instruction']}\n\n"
                "Contexto permitido para o paciente:\n"
                f"{json.dumps(patient_context, ensure_ascii=False, default=str)}\n\n"
                "Histórico recente deste chat pessoal:\n"
                f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
                "Mensagem do paciente:\n"
                f"{user_message}\n\n"
                "Responda de forma útil, simples e segura."
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
            "Você é a IA profissional do nutricionista dentro do Star Nutri.\n\n"
            "Você ajuda o nutricionista a analisar pacientes, planejar acompanhamentos, "
            "estruturar hipóteses nutricionais e preparar materiais de trabalho.\n"
            "Este chat é privado do nutricionista e nunca deve ser apresentado como "
            "histórico pessoal do paciente.\n\n"
            "Regras obrigatórias:\n"
            "- Você apoia o nutricionista, mas NÃO substitui julgamento profissional.\n"
            "- Você NÃO substitui médico.\n"
            "- Você NÃO diagnostica doenças.\n"
            "- Você NÃO prescreve medicamentos.\n"
            "- Você pode sugerir rascunhos de planos e acompanhamentos para revisão do nutricionista.\n"
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
