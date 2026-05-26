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
        patient_id: str | None,
        chat_id: str | None,
    ) -> tuple[dict, dict, str]:
        if not patient_id:
            return await self.resolve_nutritionist_general_context(token, chat_id)

        _, nutritionist, patient = await self.workspace.resolve_nutritionist_patient(
            token,
            patient_id,
        )

        context = await self.workspace.get_patient_context_for_nutritionist(
            token,
            patient["id"],
            include_chat_context=True,
        )
        chat = await self.workspace.ensure_nutritionist_chat(
            nutritionist["id"],
            patient["id"],
            chat_id,
        )
        return context, chat, "nutritionist"

    async def resolve_nutritionist_general_context(
        self,
        token: str,
        chat_id: str | None,
    ) -> tuple[dict, dict, str]:
        profile = await self.workspace.get_authenticated_profile(token)
        nutritionist = await self.workspace.get_nutritionist_by_user_id(profile["id"])
        workspace = await self.workspace.get_nutritionist_workspace(token)
        chat = await self.workspace.ensure_nutritionist_chat(
            nutritionist["id"],
            None,
            chat_id,
        )

        context = {
            "patient": None,
            "profile": None,
            "nutritionist": nutritionist,
            "nutritionist_profile": profile,
            "workspace_summary": {
                "patients_count": len(workspace.get("patients", [])),
                "active_patients_count": len(
                    [
                        patient
                        for patient in workspace.get("patients", [])
                        if patient.get("is_active") is not False
                    ]
                ),
                "recent_patients": [
                    {
                        "id": patient.get("id"),
                        "full_name": (patient.get("profile") or {}).get("full_name"),
                        "objective": patient.get("objective"),
                    }
                    for patient in workspace.get("patients", [])[:8]
                ],
            },
            "main_metrics": [],
            "variable_metrics": [],
            "conditions": [],
            "diets": [],
            "workouts": [],
            "nutritionist_chats": [],
            "patient_chats": [],
            "recent_professional_messages": [],
            "recent_personal_messages": [],
        }
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
        patient = context.get("patient")
        profile = context.get("profile") or {}
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
                "Voce e o assistente pessoal de rotina do paciente no Star Nutri.\n\n"
                "Voce conversa diretamente com o paciente, com tom claro, acolhedor e pratico.\n"
                "Voce pode ajudar a entender o plano ativo, organizar rotina, lembrar hidratacao, "
                "tirar duvidas gerais e sugerir perguntas para levar ao nutricionista.\n\n"
                "Voce esta integrado ao agente operacional do backend. Quando uma acao simples "
                "for executada e aparecer no resumo de acoes, confirme o que foi salvo; nao diga "
                "que nao tem permissao para registrar dados ja executados pelo sistema.\n\n"
                "Limites obrigatorios deste chat pessoal:\n"
                "- Voce NAO tem acesso a analises internas do nutricionista.\n"
                "- Voce NAO deve mencionar notas clinicas privadas, hipoteses profissionais ou "
                "bastidores do atendimento.\n"
                "- Voce NAO cria uma dieta nova nem altera a dieta ativa.\n"
                "- Voce NAO cria ou altera treino.\n"
                "- Voce NAO diagnostica doencas e NAO prescreve medicamentos.\n"
                "- Se houver sintomas importantes ou risco a saude, oriente buscar atendimento "
                "profissional.\n\n"
                "Nivel de raciocinio solicitado:\n"
                f"{settings['label']} - {settings['instruction']}\n\n"
                "Contexto permitido para o paciente:\n"
                f"{json.dumps(patient_context, ensure_ascii=False, default=str)}\n\n"
                "Historico recente deste chat pessoal:\n"
                f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
                "Mensagem do paciente:\n"
                f"{user_message}\n\n"
                "Responda de forma util, simples e segura."
            )

        if chat_scope == "nutritionist" and not patient:
            nutritionist_profile = context.get("nutritionist_profile") or {}
            general_context = {
                "nutricionista": {
                    "nome": nutritionist_profile.get("full_name"),
                    "email": nutritionist_profile.get("email"),
                },
                "workspace": context.get("workspace_summary") or {},
                "nivel_de_inteligencia": settings["label"],
            }

            return (
                "Voce e a IA profissional geral do nutricionista dentro do Star Nutri.\n\n"
                "Este modo nao esta focado em um paciente especifico.\n"
                "Use-o para raciocinio clinico geral, ideias de acompanhamento, "
                "organizacao do consultorio, rascunhos de orientacoes, materiais "
                "educativos e apoio operacional de baixo risco.\n\n"
                "Limites obrigatorios:\n"
                "- Nao invente dados de pacientes.\n"
                "- Nao afirme que existe um prontuario em foco.\n"
                "- Nao execute alteracoes em prontuario, dieta, treino, metricas ou agenda.\n"
                "- Se o pedido depender de um paciente especifico, oriente selecionar o paciente no topo.\n\n"
                "Nivel de raciocinio solicitado:\n"
                f"{settings['label']} - {settings['instruction']}\n\n"
                "Contexto geral do workspace:\n"
                f"{json.dumps(general_context, ensure_ascii=False, default=str)}\n\n"
                "Historico recente da conversa:\n"
                f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
                "Mensagem do usuario:\n"
                f"{user_message}\n\n"
                "Responda de forma util, objetiva e profissional."
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
            "Voce e a IA profissional do nutricionista dentro do Star Nutri.\n\n"
            "Voce ajuda o nutricionista a analisar pacientes, planejar acompanhamentos, "
            "estruturar hipoteses nutricionais e preparar materiais de trabalho.\n"
            "Este chat e privado do nutricionista e nunca deve ser apresentado como "
            "historico pessoal do paciente.\n\n"
            "Voce esta integrada ao agente operacional do backend. Quando o backend executar "
            "uma acao real, ela aparecera no resumo de acoes antes da resposta; confirme o que "
            "foi salvo e nao oriente o usuario a fazer manualmente algo que ja foi executado.\n\n"
            "Regras obrigatorias:\n"
            "- Voce apoia o nutricionista, mas NAO substitui julgamento profissional.\n"
            "- Voce NAO substitui medico.\n"
            "- Voce NAO diagnostica doencas.\n"
            "- Voce NAO prescreve medicamentos.\n"
            "- Voce pode sugerir rascunhos de planos e acompanhamentos para revisao do nutricionista.\n"
            "- Voce NAO promete resultados.\n"
            "- Voce sempre considera os dados reais cadastrados.\n"
            "- Voce responde com seguranca, clareza e responsabilidade.\n"
            "- Quando houver risco a saude, oriente procurar atendimento profissional.\n\n"
            "Nivel de raciocinio solicitado:\n"
            f"{settings['label']} - {settings['instruction']}\n\n"
            "Contexto do paciente:\n"
            f"{json.dumps(clinical_context, ensure_ascii=False, default=str)}\n\n"
            "Historico recente da conversa:\n"
            f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
            "Mensagem do usuario:\n"
            f"{user_message}\n\n"
            "Responda de forma util, objetiva e profissional."
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
