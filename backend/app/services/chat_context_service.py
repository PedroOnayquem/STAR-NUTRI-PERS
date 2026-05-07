from __future__ import annotations

import json

from fastapi import HTTPException, status

from .supabase_workspace_service import SupabaseWorkspaceService


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
    ) -> str:
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
            "condicoes_clinicas": context["conditions"],
            "metricas_principais": context["main_metrics"],
            "metricas_variaveis_recentes": context["variable_metrics"][:30],
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
            "Contexto do paciente:\n"
            f"{json.dumps(clinical_context, ensure_ascii=False, default=str)}\n\n"
            "Histórico recente da conversa:\n"
            f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
            "Mensagem do usuário:\n"
            f"{user_message}\n\n"
            "Responda de forma útil, objetiva e profissional."
        )

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
