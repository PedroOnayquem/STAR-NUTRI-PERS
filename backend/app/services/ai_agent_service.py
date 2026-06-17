from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..core.config import settings
from .openai_service import OpenAIChatService
from .supabase_workspace_service import SupabaseWorkspaceService


PATIENT_READ_TOOLS = {
    "get_patient_conditions",
    "get_patient_metrics",
    "get_patient_profile",
    "get_patient_summary",
    "search_patient_by_name",
}

AUTO_TOOLS = {
    "add_food_to_meal",
    "add_observation",
    "add_workout_observation",
    "create_appointment",
    "create_patient_appointment",
    "create_training_plan",
    "register_injury",
    "register_progress",
    "register_weight_change",
    "update_patient_birth_date",
    "update_patient_profile",
}

TACO_TOOLS = {
    "add_taco_food_to_meal",
    "calculate_taco_food_nutrients",
    "get_taco_food",
    "search_taco_foods",
}

GENERAL_NUTRITIONIST_TOOLS = {
    "calculate_taco_food_nutrients",
    "get_taco_food",
    "search_taco_foods",
    "update_patient_birth_date",
} | PATIENT_READ_TOOLS

NUTRITIONIST_TOOLS = AUTO_TOOLS | TACO_TOOLS | PATIENT_READ_TOOLS | {"request_confirmation"}
PATIENT_TOOLS = {
    "add_observation",
    "register_injury",
    "register_progress",
    "register_weight_change",
    "request_confirmation",
}
PENDING_TOOLS = {"add_workout_observation", "update_patient_birth_date"}

PATIENT_QUERY_STOPWORDS = {
    "a",
    "agora",
    "alterar",
    "altere",
    "anos",
    "altura",
    "atual",
    "atualizar",
    "atualize",
    "cadastro",
    "clinica",
    "clinicas",
    "com",
    "condicao",
    "condicoes",
    "considerando",
    "corrigir",
    "corrija",
    "da",
    "dados",
    "data",
    "de",
    "dele",
    "dela",
    "do",
    "e",
    "esse",
    "essa",
    "estao",
    "esta",
    "faca",
    "faz",
    "genero",
    "idade",
    "mudar",
    "me",
    "metricas",
    "metrica",
    "nascimento",
    "o",
    "objetivo",
    "observacao",
    "observacoes",
    "paciente",
    "peso",
    "pois",
    "possui",
    "para",
    "prontuario",
    "qual",
    "quais",
    "quantos",
    "quero",
    "correta",
    "correto",
    "cadastrada",
    "cadastrado",
    "errada",
    "errado",
    "foi",
    "resuma",
    "resumo",
    "sobre",
    "tem",
    "ter",
    "trocar",
    "troque",
    "um",
    "uma",
}


class AiAgentService:
    def __init__(
        self,
        workspace: SupabaseWorkspaceService,
        ai_service: OpenAIChatService,
    ) -> None:
        self.workspace = workspace
        self.ai_service = ai_service

    async def run(
        self,
        *,
        chat: dict,
        chat_scope: str,
        context: dict,
        history: list[dict[str, str]],
        reasoning_level: str,
        token: str,
        user_message: str,
        user_message_record: dict,
    ) -> list[dict]:
        profile = await self.workspace.get_authenticated_profile(token)
        is_general_nutritionist_chat = chat_scope == "nutritionist" and not context.get("patient")
        if is_general_nutritionist_chat:
            allowed_tools = GENERAL_NUTRITIONIST_TOOLS
        else:
            allowed_tools = (
                NUTRITIONIST_TOOLS if chat_scope == "nutritionist" else PATIENT_TOOLS
            )
        pending_state = await self.workspace.get_ai_conversation_state(
            conversation_id=chat["id"],
            user_id=profile["id"],
        )
        pending_resolution = self._resolve_pending_action(
            pending_state=pending_state,
            user_message=user_message,
        )
        if pending_resolution:
            tool_name, arguments = pending_resolution
            if tool_name not in allowed_tools:
                if pending_state:
                    await self.workspace.clear_ai_conversation_state(pending_state["id"])
                return [
                    await self._record_action(
                        actor=profile,
                        arguments={
                            "message": user_message,
                            "pending_action": tool_name,
                        },
                        chat=chat,
                        chat_scope=chat_scope,
                        context=context,
                        error="A acao pendente nao esta disponivel neste tipo de chat.",
                        intent="confirm_pending_action",
                        message=user_message_record,
                        status="skipped",
                        tool_name="conversation_state",
                    )
                ]
            return [
                await self._execute_tool(
                    actor=profile,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent="confirm_pending_action",
                    message=user_message_record,
                    tool_name=tool_name,
                )
            ]

        intent = self._classify_intent(user_message, has_pending_state=bool(pending_state))
        if intent in {"confirm_pending_action", "cancel_pending_action"}:
            if pending_state and intent == "cancel_pending_action":
                await self.workspace.clear_ai_conversation_state(pending_state["id"])
            if pending_state and intent == "cancel_pending_action":
                return [
                    await self._record_action(
                        actor=profile,
                        arguments={"message": user_message},
                        chat=chat,
                        chat_scope=chat_scope,
                        context=context,
                        intent=intent,
                        message=user_message_record,
                        result={
                            "label": "Acao pendente cancelada",
                            "summary": "A confirmacao pendente foi cancelada.",
                        },
                        status="skipped",
                        tool_name="conversation_state",
                    )
                ]
            if pending_state and intent == "confirm_pending_action":
                await self.workspace.clear_ai_conversation_state(pending_state["id"])
                return [
                    await self._record_action(
                        actor=profile,
                        arguments={
                            "message": user_message,
                            "pending_action": pending_state.get("pending_action"),
                        },
                        chat=chat,
                        chat_scope=chat_scope,
                        context=context,
                        error="A acao pendente nao esta mais disponivel para execucao.",
                        intent=intent,
                        message=user_message_record,
                        result={
                            "label": "Acao pendente indisponivel",
                            "summary": (
                                "Nao consegui executar a acao pendente. "
                                "Envie o pedido novamente com os dados necessarios."
                            ),
                        },
                        status="skipped",
                        tool_name="conversation_state",
                    )
                ]
            return []

        if intent == "patient_lookup":
            actions = await self._patient_lookup_actions(
                actor=profile,
                allowed_tools=allowed_tools,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                intent=intent,
                message=user_message_record,
                user_message=user_message,
            )
            if actions:
                return actions

        fallback = self._fallback_tool_call(
            allowed_tools=allowed_tools,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            user_message=user_message,
        )
        if fallback:
            tool_name, arguments = fallback
            return [
                await self._execute_tool(
                    actor=profile,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=user_message_record,
                    tool_name=tool_name,
                )
            ]

        if not self._looks_actionable(user_message):
            return []

        tools = [
            tool
            for tool in AGENT_TOOLS
            if tool["function"]["name"] in allowed_tools
        ]

        decision: dict = {}
        try:
            decision = await self.ai_service.complete_with_tools(
                system_prompt=self._build_tool_prompt(chat_scope, context, profile),
                history=history,
                reasoning_level=reasoning_level,
                tools=tools,
                user_message=user_message,
            )
        except Exception:
            decision = {}

        actions: list[dict] = []
        for tool_call in decision.get("tool_calls") or []:
            function = tool_call.get("function") or {}
            tool_name = function.get("name")
            if not tool_name:
                continue

            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"raw_arguments": function.get("arguments")}
                actions.append(
                    await self._record_action(
                        actor=profile,
                        arguments=arguments,
                        chat=chat,
                        chat_scope=chat_scope,
                        context=context,
                        error="Argumentos invalidos gerados pela IA.",
                        intent=intent,
                        message=user_message_record,
                        status="failed",
                        tool_name=tool_name,
                    )
                )
                continue

            if tool_name not in allowed_tools:
                actions.append(
                    await self._record_action(
                        actor=profile,
                        arguments=arguments,
                        chat=chat,
                        chat_scope=chat_scope,
                        context=context,
                        error="Tool nao permitida para este perfil ou escopo.",
                        intent=intent,
                        message=user_message_record,
                        status="skipped",
                        tool_name=tool_name,
                    )
                )
                continue

            actions.append(
                await self._execute_tool(
                    actor=profile,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=user_message_record,
                    tool_name=tool_name,
                )
            )

        return actions

    def _build_tool_prompt(
        self,
        chat_scope: str,
        context: dict,
        profile: dict,
    ) -> str:
        now = _sao_paulo_now().isoformat()
        patient = context.get("patient") or {}
        patient_profile = patient.get("profile") or context.get("profile") or {}
        active_diet = next(
            (diet for diet in context.get("diets", []) if diet.get("is_active")),
            None,
        )
        active_workout = next(
            (workout for workout in context.get("workouts", []) if workout.get("is_active")),
            None,
        )
        summary = {
            "agora_sao_paulo": now,
            "escopo": chat_scope,
            "usuario": {"id": profile.get("id"), "role": profile.get("role")},
            "paciente_em_foco": {
                "id": patient.get("id"),
                "nome": patient_profile.get("full_name"),
                "data_nascimento": patient.get("birth_date"),
                "objetivo": patient.get("objective"),
            },
            "dieta_ativa": active_diet,
            "treino_ativo": active_workout,
            "condicoes_clinicas_atuais": context.get("conditions", [])[:12],
            "metricas_recentes": context.get("variable_metrics", [])[:8],
        }

        return (
            "Você é o orquestrador de tools do agente Star Nutri.\n"
            "Sua tarefa é decidir se a mensagem exige ações reais no sistema.\n"
            "Chame tools somente quando houver intenção clara, entidade suficiente e baixo risco.\n"
            "Comandos naturais como cadastrar lesao, registrar peso, adicionar observacao, "
            "adicionar alimento ou criar treino devem chamar uma tool em vez de responder com instrucoes manuais.\n"
            "Nunca diga que algo foi cadastrado, salvo, executado ou atualizado sem tool retornando sucesso real.\n"
            "Para create_training_plan, converta qualquer tabela/markdown em JSON estruturado: plano, dias e exercicios. "
            "Nunca salve markdown bruto ou texto livre como treino.\n"
            "Mensagens curtas como 'sim', 'ok', 'pode' ou 'confirmo' so confirmam uma pending_action existente. "
            "Nunca transforme uma confirmacao curta em uma nova action antiga.\n"
            "Para register_injury, extraia JSON estruturado. Nunca use a mensagem bruta do usuario "
            "como local, description, notes ou title. O texto do usuario serve apenas para inferir "
            "local, descricao clinica curta, gravidade, origem, data e observacoes.\n"
            "Correcoes simples e reversiveis de cadastro, como data de nascimento claramente informada, "
            "devem chamar update_patient_birth_date diretamente. Para frases como 'nasceu em 98', "
            "use o dia e mes da data de nascimento atual do paciente em foco, se existir; se nao existir, "
            "nao invente dia/mes e nao execute a alteracao.\n"
            "Use sempre o paciente em foco; não altere dados de outro paciente citado por engano.\n"
            "Não invente valores, horários, macros ou medidas ausentes.\n"
            "Para composição de alimentos, calorias, macros ou TACO, use search_taco_foods, "
            "get_taco_food ou calculate_taco_food_nutrients. Se o alimento não existir na TACO, "
            "não invente valores; informe que não encontrou.\n"
            "Quando a mensagem perguntar sobre dados de paciente, consulte o banco antes de responder: "
            "use o paciente em foco quando existir; se não existir foco, use search_patient_by_name "
            "para nomes citados e depois get_patient_profile, get_patient_metrics, "
            "get_patient_conditions ou get_patient_summary.\n"
            "Nunca diga que idade, peso, objetivo, condições ou qualquer dado de paciente não consta "
            "sem antes executar uma tool de busca/leitura real. Se birth_date existir, calcule/retorne "
            "a idade; não diga que idade não consta.\n"
            "Em chat profissional geral sem paciente em foco, use tools de leitura para pacientes citados "
            "pelo nome e tools TACO. A única alteração permitida sem paciente em foco é "
            "update_patient_birth_date quando o nutricionista citar o paciente pelo nome e informar "
            "uma data completa. Não crie ou altere dietas, treinos, métricas ou agenda sem paciente em foco.\n"
            "Ações de deletar, cancelar, remover, sobrescrever plano completo ou apagar dados "
            "devem usar request_confirmation com pending_action e pending_payload executaveis, nunca execução direta.\n"
            "Depois de pedir confirmacao uma vez, a proxima confirmacao curta deve executar a pending_action; "
            "nunca peca a mesma confirmacao novamente.\n"
            "Se a mensagem for conversa geral ou ambígua sem necessidade de dado real, não chame nenhuma tool. "
            "Perguntas sobre dados de paciente ou TACO exigem tool de leitura antes da resposta.\n\n"
            "Contexto operacional:\n"
            f"{json.dumps(summary, ensure_ascii=False, default=str)}"
        )

    async def _execute_tool(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
        tool_name: str,
    ) -> dict:
        if tool_name != "request_confirmation" and self._patient_name_mismatch(
            context,
            arguments.get("patient_name"),
        ):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Nome citado nao corresponde ao paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name=tool_name,
            )
        if tool_name != "request_confirmation" and self._patient_id_mismatch(
            context,
            arguments.get("patient_id"),
        ):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="ID do paciente nao corresponde ao paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name=tool_name,
            )

        arguments = {**arguments, "_intent": intent}
        try:
            if tool_name == "request_confirmation":
                return await self._request_confirmation(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "search_patient_by_name":
                return await self._search_patient_by_name(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "get_patient_profile":
                return await self._get_patient_profile(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "get_patient_metrics":
                return await self._get_patient_metrics(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "get_patient_conditions":
                return await self._get_patient_conditions(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "get_patient_summary":
                return await self._get_patient_summary(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "update_patient_profile":
                return await self._update_patient_profile(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "register_injury":
                return await self._register_injury(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "register_weight_change":
                return await self._register_weight_change(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "register_progress":
                return await self._register_progress(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "add_observation":
                return await self._add_observation(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "add_food_to_meal":
                return await self._add_food_to_meal(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "search_taco_foods":
                return await self._search_taco_foods(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "get_taco_food":
                return await self._get_taco_food(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "calculate_taco_food_nutrients":
                return await self._calculate_taco_food_nutrients(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "add_taco_food_to_meal":
                return await self._add_taco_food_to_meal(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "create_appointment":
                return await self._create_appointment(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                    tool_name=tool_name,
                )
            if tool_name == "create_patient_appointment":
                return await self._create_appointment(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                    tool_name=tool_name,
                )
            if tool_name == "create_training_plan":
                return await self._create_training_plan(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "add_workout_observation":
                return await self._add_workout_observation(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
            if tool_name == "update_patient_birth_date":
                return await self._update_patient_birth_date(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                )
        except Exception as exc:
            friendly_error = _friendly_tool_error(exc)
            if settings.app_env == "development":
                print("Erro técnico em tool:", tool_name, repr(exc))
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error=friendly_error,
                intent=intent,
                message=message,
                result={
                    "label": "Ação não concluída",
                    "summary": friendly_error,
                },
                status="failed",
                tool_name=tool_name,
            )

        return await self._record_action(
            actor=actor,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            error="Tool desconhecida.",
            intent=intent,
            message=message,
            status="skipped",
            tool_name=tool_name,
        )

    async def _patient_lookup_actions(
        self,
        *,
        actor: dict,
        allowed_tools: set[str],
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
        user_message: str,
    ) -> list[dict]:
        if chat_scope != "nutritionist":
            return []

        raw = user_message.strip()
        normalized = _normalize(raw)
        patient = context.get("patient") or {}
        patient_profile = patient.get("profile") or context.get("profile") or {}
        focused_patient_id = patient.get("id")
        detected_name = None if focused_patient_id else self._extract_patient_query(raw, normalized)

        if settings.app_env == "development":
            print("Mensagem recebida:", user_message)
            print("Paciente em foco:", focused_patient_id)
            print("Paciente citado:", detected_name)

        tool_name = self._patient_read_tool_for_request(normalized)
        if tool_name not in allowed_tools:
            return []

        if focused_patient_id:
            return [
                await self._execute_tool(
                    actor=actor,
                    arguments={
                        "patient_id": focused_patient_id,
                        "patient_name": patient_profile.get("full_name"),
                    },
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                    tool_name=tool_name,
                )
            ]

        if not detected_name or "search_patient_by_name" not in allowed_tools:
            return []

        actions = [
            await self._execute_tool(
                actor=actor,
                arguments={"query": detected_name},
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                intent=intent,
                message=message,
                tool_name="search_patient_by_name",
            )
        ]
        search_result = actions[0].get("result") or {}
        matches = search_result.get("matches") or []
        if len(matches) != 1:
            return actions

        match = matches[0]
        actions.append(
            await self._execute_tool(
                actor=actor,
                arguments={
                    "patient_id": match.get("id"),
                    "patient_name": match.get("full_name") or detected_name,
                },
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                intent=intent,
                message=message,
                tool_name=tool_name,
            )
        )
        return actions

    async def _search_patient_by_name(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        query = _optional_text(arguments.get("query") or arguments.get("patient_name"))
        if not query:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Informe o nome do paciente para buscar.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="search_patient_by_name",
            )

        try:
            matches = await self.workspace.search_patients_by_name_for_nutritionist(
                nutritionist_id=nutritionist_id,
                query=query,
                limit=_positive_int(arguments.get("limit"), default=10),
            )
        except Exception:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não consegui consultar os dados do paciente agora. Tente novamente em instantes.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="search_patient_by_name",
            )

        if not matches:
            summary = f"Não encontrei paciente chamado {query} neste workspace."
        elif len(matches) > 1:
            names = ", ".join(match.get("full_name") or "Paciente sem nome" for match in matches[:5])
            summary = f"Encontrei mais de um paciente chamado {query}: {names}."
        else:
            summary = f"Paciente encontrado: {matches[0].get('full_name') or query}."

        result = {
            "count": len(matches),
            "label": "Busca de paciente",
            "matches": matches,
            "query": query,
            "summary": summary,
        }
        if settings.app_env == "development":
            print("patient_search_result:", json.dumps(result, ensure_ascii=False, default=str))
            print("Resultado search_patient_by_name:", json.dumps(result, ensure_ascii=False, default=str))

        return await self._record_action(
            actor=actor,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="search_patient_by_name",
        )

    async def _get_patient_profile(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        patient_id = await self._resolve_patient_id_for_tools(
            arguments,
            context,
            nutritionist_id=nutritionist_id,
        )
        if not patient_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não identifiquei qual paciente consultar.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="get_patient_profile",
            )

        try:
            profile = await self.workspace.get_patient_profile_for_nutritionist(
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
            )
        except Exception:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não consegui consultar os dados do paciente agora. Tente novamente em instantes.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="get_patient_profile",
            )

        result = {
            "label": "Perfil do paciente",
            "patient": profile,
            "summary": self._patient_profile_summary(profile),
        }
        if settings.app_env == "development":
            print("Resultado get_patient_profile:", json.dumps(result, ensure_ascii=False, default=str))

        return await self._record_action(
            actor=actor,
            arguments={**arguments, "patient_id": patient_id},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="get_patient_profile",
        )

    async def _get_patient_metrics(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        patient_id = await self._resolve_patient_id_for_tools(
            arguments,
            context,
            nutritionist_id=nutritionist_id,
        )
        if not patient_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não identifiquei qual paciente consultar.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="get_patient_metrics",
            )

        try:
            metrics = await self.workspace.list_patient_metrics_for_nutritionist(
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
                limit=_positive_int(arguments.get("limit"), default=40),
            )
        except Exception:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não consegui consultar os dados do paciente agora. Tente novamente em instantes.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="get_patient_metrics",
            )

        result = {
            "label": "Métricas do paciente",
            "metrics": metrics,
            "patient_id": patient_id,
            "summary": self._patient_metrics_summary(metrics),
        }
        return await self._record_action(
            actor=actor,
            arguments={**arguments, "patient_id": patient_id},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="get_patient_metrics",
        )

    async def _get_patient_conditions(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        patient_id = await self._resolve_patient_id_for_tools(
            arguments,
            context,
            nutritionist_id=nutritionist_id,
        )
        if not patient_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não identifiquei qual paciente consultar.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="get_patient_conditions",
            )

        try:
            conditions = await self.workspace.list_patient_conditions_for_nutritionist(
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
                limit=_positive_int(arguments.get("limit"), default=40),
            )
        except Exception:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não consegui consultar os dados do paciente agora. Tente novamente em instantes.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="get_patient_conditions",
            )

        result = {
            "conditions": conditions,
            "label": "Condições do paciente",
            "patient_id": patient_id,
            "summary": self._patient_conditions_summary(conditions),
        }
        return await self._record_action(
            actor=actor,
            arguments={**arguments, "patient_id": patient_id},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="get_patient_conditions",
        )

    async def _get_patient_summary(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        patient_id = await self._resolve_patient_id_for_tools(
            arguments,
            context,
            nutritionist_id=nutritionist_id,
        )
        if not patient_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não identifiquei qual paciente consultar.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="get_patient_summary",
            )

        try:
            summary = await self.workspace.get_patient_summary_for_nutritionist(
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
            )
        except Exception:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não consegui consultar os dados do paciente agora. Tente novamente em instantes.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="get_patient_summary",
            )

        result = {
            "label": "Resumo do paciente",
            "patient_id": patient_id,
            "summary": self._patient_summary_text(summary),
            "context": summary,
        }
        return await self._record_action(
            actor=actor,
            arguments={**arguments, "patient_id": patient_id},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="get_patient_summary",
        )

    async def _update_patient_profile(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist" or not context.get("patient"):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Atualizações de perfil exigem um paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="update_patient_profile",
            )

        nutritionist_id = self._nutritionist_id_for_tools(actor, context)
        patient_id = await self._resolve_patient_id_for_tools(
            arguments,
            context,
            nutritionist_id=nutritionist_id,
        )
        allowed_fields = {
            "birth_date",
            "full_name",
            "gender",
            "is_active",
            "notes",
            "objective",
            "phone",
        }
        payload = {
            key: value
            for key, value in arguments.items()
            if key in allowed_fields and value is not None
        }
        if "birth_date" in payload:
            birth_date = _safe_birth_date(payload["birth_date"])
            if not birth_date:
                return await self._record_action(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    error="Data de nascimento inválida.",
                    intent=intent,
                    message=message,
                    status="skipped",
                    tool_name="update_patient_profile",
                )
            payload["birth_date"] = birth_date
        if not payload:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Nenhum campo permitido foi informado para atualização.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="update_patient_profile",
            )

        before_state = await self.workspace.get_patient_profile_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        updated = await self.workspace.update_patient_profile_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
            payload=payload,
        )
        return await self._record_action(
            actor=actor,
            arguments={**arguments, "patient_id": patient_id},
            after_state=updated,
            before_state=before_state,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            new_value=payload,
            old_value=before_state,
            result={
                "label": "Perfil do paciente atualizado",
                "patient": updated,
                "summary": "Perfil do paciente atualizado com sucesso.",
            },
            status="executed",
            tool_name="update_patient_profile",
        )

    async def _request_confirmation(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        pending_action = _optional_text(
            arguments.get("pending_action") or arguments.get("tool_name")
        )
        pending_payload = _object_payload(
            arguments.get("pending_payload") or arguments.get("payload")
        )
        if not pending_action or pending_action not in PENDING_TOOLS:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Confirmacao sem acao executavel.",
                intent=intent,
                message=message,
                result={
                    "label": "Confirmacao sem acao executavel",
                    "summary": (
                        "Nao consegui preparar a acao para confirmacao. "
                        "Envie o pedido novamente com os dados necessarios."
                    ),
                },
                status="skipped",
                tool_name="request_confirmation",
            )

        allowed_pending = (
            NUTRITIONIST_TOOLS if chat_scope == "nutritionist" else PATIENT_TOOLS
        )
        if pending_action not in allowed_pending:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Acao pendente nao permitida neste chat.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="request_confirmation",
            )

        pending_payload = {**pending_payload}
        pending_payload.setdefault("patient_id", self._patient_id(context))
        if self._patient_id_mismatch(context, pending_payload.get("patient_id")):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="ID do paciente nao corresponde ao paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="request_confirmation",
            )
        if self._patient_name_mismatch(context, pending_payload.get("patient_name")):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Nome citado nao corresponde ao paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="request_confirmation",
            )

        state = await self.workspace.upsert_ai_conversation_state(
            {
                "conversation_id": chat["id"],
                "user_id": actor["id"],
                "patient_id": self._patient_id(context),
                "pending_action": pending_action,
                "target_entity": arguments.get("target_entity"),
                "pending_payload": pending_payload,
                "expires_at": (_sao_paulo_now() + timedelta(minutes=30)).isoformat(),
            }
        )
        question = (
            _optional_text(arguments.get("question"))
            or _optional_text(arguments.get("action_description"))
            or "Confirma a execucao desta acao?"
        )
        return await self._record_action(
            actor=actor,
            arguments={
                **arguments,
                "pending_action": pending_action,
                "pending_payload": pending_payload,
            },
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            requires_confirmation=True,
            result={
                "label": "Confirmacao necessaria",
                "pending_action": pending_action,
                "state_id": state.get("id"),
                "summary": question,
            },
            status="pending_confirmation",
            tool_name="request_confirmation",
        )

    async def _update_patient_birth_date(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist":
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Apenas nutricionistas podem alterar a data de nascimento do paciente.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        nutritionist = context.get("nutritionist") or {}
        nutritionist_id = _optional_text(nutritionist.get("id"))
        if not nutritionist_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Nutricionista nao identificado para atualizar o paciente.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        try:
            patient_id = await self._resolve_patient_id_for_tools(
                arguments,
                context,
                nutritionist_id=nutritionist_id,
            )
        except ValueError as exc:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error=str(exc),
                intent=intent,
                message=message,
                result={
                    "label": "Paciente não identificado",
                    "summary": str(exc),
                },
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        if not patient_id:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Não identifiquei qual paciente atualizar.",
                intent=intent,
                message=message,
                result={
                    "label": "Paciente não identificado",
                    "summary": "Informe o nome do paciente que deseja atualizar.",
                },
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        if settings.app_env == "development":
            print("chat_scope:", chat_scope)
            print("patient_id:", patient_id)
            print("detected_patient_name:", arguments.get("patient_name"))
            print("intent:", intent)
            print("payload:", json.dumps(arguments, ensure_ascii=False, default=str))

        birth_date = _safe_birth_date(arguments.get("birth_date"))
        birth_year = _birth_year(arguments.get("birth_year"))
        if not birth_date and birth_year:
            current_birth_date = _safe_birth_date(
                (context.get("patient") or {}).get("birth_date")
            )
            if current_birth_date:
                current_date = datetime.fromisoformat(current_birth_date).date()
                birth_date = _compose_birth_date(
                    birth_year,
                    current_date.month,
                    current_date.day,
                )
            else:
                await self.workspace.upsert_ai_conversation_state(
                    {
                        "conversation_id": chat["id"],
                        "user_id": actor["id"],
                        "patient_id": patient_id,
                        "pending_action": "update_patient_birth_date",
                        "target_entity": "patient_birth_date",
                        "pending_payload": {
                            "birth_year": birth_year,
                            "needs_day_month": True,
                            "patient_id": patient_id,
                        },
                        "expires_at": (
                            _sao_paulo_now() + timedelta(minutes=30)
                        ).isoformat(),
                    }
                )
                return await self._record_action(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
                    requires_confirmation=True,
                    result={
                        "label": "Data de nascimento incompleta",
                        "summary": (
                            f"Encontrei o ano {birth_year}, mas preciso do dia e do mes "
                            "para atualizar a data de nascimento."
                        ),
                    },
                    status="pending_confirmation",
                    tool_name="update_patient_birth_date",
                )

        if not birth_date:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Data de nascimento ausente ou invalida.",
                intent=intent,
                message=message,
                result={
                    "label": "Data de nascimento invalida",
                    "summary": (
                        "Informe uma data de nascimento completa, por exemplo 14/08/1998."
                    ),
                },
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        before = await self.workspace.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        raw_patient_label = _optional_text(arguments.get("patient_name"))
        patient_label = _title_text(raw_patient_label) if raw_patient_label else "paciente"
        previous_birth_date = _safe_birth_date(before.get("birth_date"))
        state_id = _optional_text(arguments.get("_state_id"))
        if previous_birth_date == birth_date:
            if state_id:
                await self.workspace.clear_ai_conversation_state(state_id)
            return await self._record_action(
                actor=actor,
                arguments={**arguments, "birth_date": birth_date},
                before_state=before,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                intent=intent,
                message=message,
                result={
                    "label": "Data de nascimento ja estava correta",
                    "summary": (
                        f"A data de nascimento de {patient_label} ja estava como "
                        f"{_format_date_br(birth_date)}."
                    ),
                },
                status="skipped",
                tool_name="update_patient_birth_date",
            )

        updated = await self.workspace.update_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
            payload={"birth_date": birth_date},
        )
        if state_id:
            await self.workspace.clear_ai_conversation_state(state_id)

        return await self._record_action(
            actor=actor,
            after_state=updated,
            arguments={**arguments, "birth_date": birth_date, "patient_id": patient_id},
            before_state=before,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            new_value={"birth_date": birth_date},
            old_value={"birth_date": previous_birth_date},
            result={
                "label": "Data de nascimento atualizada",
                "old_birth_date": previous_birth_date,
                "new_birth_date": birth_date,
                "patient_name": patient_label,
                "summary": (
                    f"Data de nascimento de {patient_label} atualizada com sucesso para "
                    f"{_format_date_br(birth_date)}."
                ),
            },
            status="executed",
            tool_name="update_patient_birth_date",
        )

    async def _register_injury(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        patient_id = self._patient_id(context)
        injury_payload = self._normalize_injury_payload(arguments, context, message)
        if not injury_payload["local"] or not injury_payload["description"]:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Lesao sem parte do corpo ou descricao suficiente.",
                message=message,
                status="skipped",
                tool_name="register_injury",
            )

        title = f"Lesão - {injury_payload['local']}"[:120]
        duplicate = await self.workspace.find_similar_health_condition(
            patient_id=patient_id,
            condition_type="injury",
            title=title,
        )
        if duplicate:
            return await self._record_action(
                actor=actor,
                arguments=injury_payload,
                before_state=duplicate,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                message=message,
                result={
                    "label": "Lesao ja registrada",
                    "summary": f"Ja existia um registro semelhante: {duplicate.get('title')}.",
                },
                status="skipped",
                tool_name="register_injury",
            )

        created = await self.workspace.create_health_condition_record(
            patient_id=patient_id,
            condition_type="injury",
            title=title,
            description=injury_payload["description"],
            injury_local=injury_payload["local"],
            notes=injury_payload["notes"],
            origin=injury_payload["origin"],
            recommendations=injury_payload["recommendations"],
            severity=injury_payload["severity"],
            started_at=injury_payload["date"],
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=injury_payload,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={
                "label": "Lesao registrada",
                "summary": (
                    f"{injury_payload['local']}, gravidade "
                    f"{injury_payload['severity'].lower()}."
                ),
            },
            status="executed",
            tool_name="register_injury",
        )

    async def _register_weight_change(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        patient_id = self._patient_id(context)
        current_weight = _number(arguments.get("current_weight_kg"))
        delta = _number(arguments.get("delta_kg"))
        latest = await self.workspace.get_latest_variable_metric(
            patient_id=patient_id,
            name="peso",
        )

        if current_weight is None and delta is not None and latest:
            latest_value = _number(latest.get("value"))
            if latest_value is not None:
                current_weight = latest_value + delta

        if current_weight is None:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=latest,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Nao havia peso atual suficiente para calcular o novo peso.",
                message=message,
                result={
                    "label": "Peso nao registrado",
                    "summary": "Informe o peso atual ou tenha um peso anterior registrado.",
                },
                status="skipped",
                tool_name="register_weight_change",
            )

        recorded_at = str(arguments.get("recorded_at") or datetime.now(UTC).isoformat())
        if (
            latest
            and _number(latest.get("value")) == current_weight
            and _same_recorded_day(latest, recorded_at)
        ):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=latest,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                message=message,
                result={
                    "label": "Peso ja registrado",
                    "summary": f"O peso {_format_number(current_weight)} kg ja constava para esta data.",
                },
                status="skipped",
                tool_name="register_weight_change",
            )

        created = await self.workspace.create_variable_metric_record(
            patient_id=patient_id,
            name="peso",
            value=_format_number(current_weight),
            unit="kg",
            recorded_at=recorded_at,
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=arguments,
            before_state=latest,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={
                "label": "Peso registrado",
                "summary": f"Peso atualizado para {_format_number(current_weight)} kg.",
            },
            status="executed",
            tool_name="register_weight_change",
        )

    async def _register_progress(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        name = str(arguments.get("metric_name") or "").strip().lower()
        value = arguments.get("value")
        unit = _optional_text(arguments.get("unit"))
        if not name or value in (None, ""):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Metrica sem nome ou valor.",
                message=message,
                status="skipped",
                tool_name="register_progress",
            )

        latest = await self.workspace.get_latest_variable_metric(
            patient_id=self._patient_id(context),
            name=name,
        )
        recorded_at = str(arguments.get("recorded_at") or datetime.now(UTC).isoformat())
        if (
            latest
            and str(latest.get("value")) == str(value)
            and (unit is None or latest.get("unit") == unit)
            and _same_recorded_day(latest, recorded_at)
        ):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=latest,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                message=message,
                result={
                    "label": "Evolucao ja registrada",
                    "summary": f"{name}: {value} {unit or ''}".strip(),
                },
                status="skipped",
                tool_name="register_progress",
            )

        created = await self.workspace.create_variable_metric_record(
            patient_id=self._patient_id(context),
            name=name,
            value=str(value),
            unit=unit,
            recorded_at=recorded_at,
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={"label": "Evolucao registrada", "summary": f"{name}: {value} {unit or ''}".strip()},
            status="executed",
            tool_name="register_progress",
        )

    async def _add_observation(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        observation = str(arguments.get("observation") or "").strip()
        if not observation:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Observacao vazia.",
                message=message,
                status="skipped",
                tool_name="add_observation",
            )

        title = str(arguments.get("title") or observation[:80]).strip()[:120]
        created = await self.workspace.create_health_condition_record(
            patient_id=self._patient_id(context),
            condition_type="observation",
            title=title,
            description=observation,
            severity=None,
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={"label": "Observacao adicionada", "summary": title},
            status="executed",
            tool_name="add_observation",
        )

    async def _search_taco_foods(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        query = _optional_text(arguments.get("query") or arguments.get("food_name"))
        if not query:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Busca TACO sem termo de alimento.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="search_taco_foods",
            )

        foods = await self.workspace.search_taco_foods(
            query=query,
            category=_optional_text(arguments.get("category")),
            limit=_positive_int(arguments.get("limit"), default=6),
        )
        return await self._record_action(
            actor=actor,
            after_state=foods,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result={
                "foods": [_compact_taco_food(food) for food in foods],
                "label": "Busca TACO",
                "summary": (
                    f"{len(foods)} alimento(s) encontrado(s) na TACO para '{query}'."
                    if foods
                    else f"Nenhum alimento TACO encontrado para '{query}'."
                ),
            },
            status="executed",
            tool_name="search_taco_foods",
        )

    async def _get_taco_food(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        food_id = _optional_text(arguments.get("food_id"))
        food_name = _optional_text(arguments.get("food_name") or arguments.get("query"))
        food = await self.workspace.find_taco_food(food_id=food_id, query=food_name)
        if not food:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Alimento nao encontrado na TACO.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="get_taco_food",
            )

        return await self._record_action(
            actor=actor,
            after_state=food,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result={
                "food": _compact_taco_food(food),
                "label": "Alimento TACO",
                "summary": _taco_food_summary(food),
            },
            status="executed",
            tool_name="get_taco_food",
        )

    async def _calculate_taco_food_nutrients(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        food_id = _optional_text(arguments.get("food_id"))
        food_name = _optional_text(arguments.get("food_name") or arguments.get("query"))
        quantity_g = _quantity_grams(arguments.get("quantity_g") or arguments.get("quantity"))
        if quantity_g is None:
            quantity_g = 100

        food = await self.workspace.find_taco_food(food_id=food_id, query=food_name)
        if not food:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Alimento nao encontrado na TACO.",
                intent=intent,
                message=message,
                result={
                    "label": "Alimento TACO nao encontrado",
                    "summary": (
                        "Nao encontrei esse alimento na TACO. "
                        "Confirme o nome ou cadastre um alimento personalizado."
                    ),
                },
                status="skipped",
                tool_name="calculate_taco_food_nutrients",
            )

        nutrients = _calculate_taco_nutrients(food, quantity_g)
        return await self._record_action(
            actor=actor,
            after_state={"food": food, "nutrients": nutrients},
            arguments={**arguments, "quantity_g": quantity_g},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result={
                "food": _compact_taco_food(food),
                "label": "Calculo TACO",
                "nutrients": nutrients,
                "quantity_g": quantity_g,
                "summary": _nutrient_summary(food, nutrients, quantity_g),
            },
            status="executed",
            tool_name="calculate_taco_food_nutrients",
        )

    async def _add_taco_food_to_meal(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist" or not context.get("patient"):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Adicionar alimento em refeicao exige paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_taco_food_to_meal",
            )

        meal_name = _optional_text(arguments.get("meal_name"))
        quantity_g = _quantity_grams(arguments.get("quantity_g") or arguments.get("quantity"))
        food_id = _optional_text(arguments.get("food_id"))
        food_name = _optional_text(arguments.get("food_name") or arguments.get("query"))
        if not meal_name or quantity_g is None or not (food_id or food_name):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Dados insuficientes para adicionar alimento TACO.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_taco_food_to_meal",
            )

        food = await self.workspace.find_taco_food(food_id=food_id, query=food_name)
        if not food:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Alimento nao encontrado na TACO.",
                intent=intent,
                message=message,
                result={
                    "label": "Alimento TACO nao encontrado",
                    "summary": (
                        "Nao encontrei esse alimento na TACO. "
                        "Confirme o nome ou cadastre um alimento personalizado."
                    ),
                },
                status="skipped",
                tool_name="add_taco_food_to_meal",
            )

        diet = await self.workspace.get_active_diet_with_meals(self._patient_id(context))
        if not diet:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Paciente sem dieta ativa.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_taco_food_to_meal",
            )

        normalized_target = _normalize(meal_name)
        meal = next(
            (
                item
                for item in diet.get("meals", [])
                if normalized_target in _normalize(item.get("meal_name", ""))
                or _normalize(item.get("meal_name", "")) in normalized_target
            ),
            None,
        )
        nutrients = _calculate_taco_nutrients(food, quantity_g)
        food_item = {
            "carbohydrate_g": nutrients["carbohydrate_g"],
            "energy_kcal": nutrients["energy_kcal"],
            "fiber_g": nutrients["fiber_g"],
            "lipid_g": nutrients["lipid_g"],
            "name": food["name"],
            "protein_g": nutrients["protein_g"],
            "quantity": f"{_format_number(quantity_g)}g",
            "quantity_g": quantity_g,
            "sodium_mg": nutrients["sodium_mg"],
            "taco_food_id": food["id"],
        }

        if meal:
            foods = list(meal.get("foods") or [])
            foods.append(food_item)
            updated_meal = await self.workspace.update_diet_meal_foods(
                meal_id=meal["id"],
                foods=foods,
            )
        else:
            updated_meal = await self.workspace.create_diet_meal_record(
                diet_id=diet["id"],
                meal_name=meal_name,
                foods=[food_item],
            )
            foods = [food_item]

        created_item = await self.workspace.create_diet_meal_item(
            meal_id=updated_meal["id"],
            taco_food_id=food["id"],
            custom_food_name=None,
            quantity_g=quantity_g,
            nutrients=nutrients,
        )

        next_meals = []
        replaced = False
        for current_meal in diet.get("meals", []):
            if current_meal.get("id") == updated_meal.get("id"):
                replaced = True
                existing_items = list(current_meal.get("items") or [])
                next_meals.append(
                    {
                        **current_meal,
                        "foods": foods,
                        "items": existing_items + [created_item],
                    }
                )
            else:
                next_meals.append(current_meal)
        if not replaced:
            next_meals.append({**updated_meal, "items": [created_item]})

        totals = _diet_totals(next_meals)
        updated_diet = await self.workspace.update_diet_macro_totals(
            diet_id=diet["id"],
            payload={
                "calories": round(totals["energy_kcal"]),
                "protein": totals["protein_g"],
                "carbs": totals["carbohydrate_g"],
                "fats": totals["lipid_g"],
            },
        )

        return await self._record_action(
            actor=actor,
            after_state={
                "diet": updated_diet,
                "food": food,
                "meal": updated_meal,
                "meal_item": created_item,
            },
            arguments={**arguments, "food_id": food["id"], "quantity_g": quantity_g},
            before_state={"diet": diet, "meal": meal},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result={
                "food": _compact_taco_food(food),
                "label": "Alimento TACO adicionado",
                "nutrients": nutrients,
                "quantity_g": quantity_g,
                "summary": (
                    f"{_format_number(quantity_g)}g de {food['name']} adicionados "
                    f"em {updated_meal.get('meal_name')} com valores da TACO."
                ),
            },
            status="executed",
            tool_name="add_taco_food_to_meal",
        )

    async def _add_food_to_meal(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
        tool_name: str = "create_appointment",
    ) -> dict:
        if chat_scope != "nutritionist":
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Pacientes nao podem alterar dieta pelo agente.",
                message=message,
                status="skipped",
                tool_name="add_food_to_meal",
            )

        patient_id = self._patient_id(context)
        diet = await self.workspace.get_active_diet_with_meals(patient_id)
        if not diet:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Paciente sem dieta ativa.",
                message=message,
                status="skipped",
                tool_name="add_food_to_meal",
            )

        meal_name = str(arguments.get("meal_name") or "").strip()
        food_name = str(arguments.get("food_name") or "").strip()
        quantity = str(arguments.get("quantity") or "").strip()
        if not meal_name or not food_name or not quantity:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=diet,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Alimento sem refeicao, nome ou quantidade.",
                message=message,
                status="skipped",
                tool_name="add_food_to_meal",
            )

        normalized_target = _normalize(meal_name)
        meal = next(
            (
                item
                for item in diet.get("meals", [])
                if normalized_target in _normalize(item.get("meal_name", ""))
                or _normalize(item.get("meal_name", "")) in normalized_target
            ),
            None,
        )
        food = {
            "name": food_name,
            "quantity": quantity,
            "notes": _optional_text(arguments.get("notes")),
        }
        foods = list((meal or {}).get("foods") or [])
        if any(
            _normalize(item.get("name", "")) == _normalize(food_name)
            and _normalize(item.get("quantity", "")) == _normalize(quantity)
            for item in foods
        ):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=meal,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                message=message,
                result={
                    "label": "Alimento ja estava na refeicao",
                    "summary": f"{food_name} {quantity}",
                },
                status="skipped",
                tool_name="add_food_to_meal",
            )

        foods.append(food)
        if meal:
            updated_meal = await self.workspace.update_diet_meal_foods(
                meal_id=meal["id"],
                foods=foods,
            )
        else:
            updated_meal = await self.workspace.create_diet_meal_record(
                diet_id=diet["id"],
                meal_name=meal_name,
                foods=foods,
            )

        macro_payload = self._macro_payload(diet, arguments)
        updated_diet = None
        if macro_payload:
            updated_diet = await self.workspace.update_diet_macro_totals(
                diet_id=diet["id"],
                payload=macro_payload,
            )

        return await self._record_action(
            actor=actor,
            after_state={"meal": updated_meal, "diet": updated_diet},
            arguments=arguments,
            before_state={"meal": meal, "diet": diet},
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={
                "label": "Alimento adicionado",
                "summary": f"{quantity} de {food_name} em {updated_meal.get('meal_name')}.",
                "macros_updated": bool(macro_payload),
            },
            status="executed",
            tool_name="add_food_to_meal",
        )

    async def _create_appointment(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist":
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Apenas nutricionistas podem criar consultas.",
                message=message,
                status="skipped",
                tool_name=tool_name,
            )

        nutritionist = context.get("nutritionist") or {}
        scheduled_at = str(arguments.get("scheduled_at_iso") or "").strip()
        date = str(arguments.get("date") or "").strip()
        start_time = str(arguments.get("start_time") or "").strip()
        if scheduled_at and (not date or not start_time):
            parsed = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            local = parsed.astimezone(ZoneInfo("America/Sao_Paulo"))
            date = local.date().isoformat()
            start_time = local.time().replace(microsecond=0).isoformat()

        if not nutritionist.get("id") or not date or not start_time:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Consulta sem nutricionista ou horario valido.",
                message=message,
                status="skipped",
                tool_name=tool_name,
            )

        duplicate = await self.workspace.find_appointment(
            nutritionist_id=nutritionist["id"],
            patient_id=self._patient_id(context),
            date=date,
            start_time=start_time,
        )
        if duplicate:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=duplicate,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                message=message,
                result={
                    "label": "Consulta ja existia",
                    "summary": duplicate.get("title"),
                },
                status="skipped",
                tool_name=tool_name,
            )

        created = await self.workspace.create_patient_appointment(
            nutritionist_id=nutritionist["id"],
            patient_id=self._patient_id(context),
            title=str(arguments.get("title") or "Retorno nutricional")[:160],
            type=str(arguments.get("type") or "consulta"),
            description=_optional_text(arguments.get("description")),
            date=date,
            start_time=start_time,
            end_time=_optional_text(arguments.get("end_time")),
            location=_optional_text(arguments.get("location")),
            meeting_link=_optional_text(arguments.get("meeting_link")),
            notes=_optional_text(arguments.get("notes")),
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={
                "label": "Consulta marcada",
                "summary": (
                    f"{created.get('title')} em {created.get('date')} "
                    f"as {created.get('start_time')}"
                ),
            },
            status="executed",
            tool_name=tool_name,
        )

    async def _create_training_plan(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist":
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Apenas nutricionistas podem cadastrar treinos pelo agente.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="create_training_plan",
            )

        nutritionist = context.get("nutritionist") or {}
        patient = context.get("patient") or {}
        if not nutritionist.get("id") or not patient.get("id"):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Contexto sem nutricionista ou paciente valido.",
                intent=intent,
                message=message,
                status="failed",
                tool_name="create_training_plan",
            )

        payload = self._normalize_training_plan_payload(arguments, context)
        error = self._validate_training_plan_payload(payload)
        if error:
            return await self._record_action(
                actor=actor,
                arguments=payload,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error=error,
                intent=intent,
                message=message,
                status="skipped",
                tool_name="create_training_plan",
            )

        plan = await self.workspace.create_training_plan_record(
            nutritionist_id=nutritionist["id"],
            patient_id=patient["id"],
            title=payload["title"],
            objective=payload["objective"],
            restrictions=payload["restrictions"],
            observations=payload["observations"],
            status="active",
        )
        days = await self.workspace.create_training_day_records(
            training_plan_id=plan["id"],
            days=payload["days"],
        )
        day_by_order = {day["order_index"]: day for day in days}
        training_exercises_payload: list[dict] = []
        mirror_exercises_payload: list[dict] = []
        for day_index, day in enumerate(payload["days"]):
            created_day = day_by_order.get(day_index)
            if not created_day:
                continue
            for exercise_index, exercise in enumerate(day["exercises"]):
                training_exercises_payload.append(
                    {
                        "training_day_id": created_day["id"],
                        "muscle_group": exercise.get("muscle_group"),
                        "exercise_name": exercise["exercise_name"],
                        "sets": exercise["sets"],
                        "reps": exercise["reps"],
                        "rest": exercise.get("rest"),
                        "load_guidance": exercise.get("load_guidance"),
                        "notes": exercise.get("notes"),
                        "order_index": exercise_index,
                    }
                )
                mirror_exercises_payload.append(exercise)

        exercises = await self.workspace.create_training_exercise_records(
            training_exercises_payload,
        )
        workout = await self.workspace.create_workout_record(
            nutritionist_id=nutritionist["id"],
            patient_id=patient["id"],
            title=payload["title"],
            description=self._training_plan_description(payload),
            frequency_per_week=len(payload["days"]),
            is_active=True,
        )
        workout_exercises = await self.workspace.create_workout_exercise_records(
            workout_id=workout["id"],
            exercises=mirror_exercises_payload,
        )

        pending_observation = _optional_text(
            arguments.get("suggested_observation")
            or (
                "Treino temporario e sujeito a reavaliacao medica."
                if payload["restrictions"]
                else None
            )
        )
        if pending_observation:
            await self.workspace.upsert_ai_conversation_state(
                {
                    "conversation_id": chat["id"],
                    "user_id": actor["id"],
                    "patient_id": patient["id"],
                    "pending_action": "add_workout_observation",
                    "target_entity": "training_plan",
                    "pending_payload": {
                        "training_plan_id": plan["id"],
                        "observation": pending_observation,
                    },
                    "expires_at": (_sao_paulo_now() + timedelta(minutes=30)).isoformat(),
                }
            )

        result = {
            "label": "Treino cadastrado",
            "summary": (
                f"Plano {payload['title']} salvo com {len(days)} dia(s) "
                f"e {len(exercises)} exercicio(s)."
            ),
            "training_plan_id": plan["id"],
            "workout_id": workout["id"],
            "days_count": len(days),
            "exercises_count": len(exercises),
            "pending_observation": pending_observation,
        }
        return await self._record_action(
            actor=actor,
            after_state={
                "training_plan": plan,
                "training_days": days,
                "training_exercises": exercises,
                "workout": workout,
                "workout_exercises": workout_exercises,
            },
            arguments=payload,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result=result,
            status="executed",
            tool_name="create_training_plan",
        )

    async def _add_workout_observation(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        intent: str,
        message: dict,
    ) -> dict:
        if chat_scope != "nutritionist":
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Apenas nutricionistas podem alterar observacoes de treino.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_workout_observation",
            )

        training_plan_id = _optional_text(arguments.get("training_plan_id"))
        observation = _optional_text(arguments.get("observation"))
        if not training_plan_id or not observation:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Observacao de treino sem plano ou texto.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_workout_observation",
            )

        before = await self.workspace.get_training_plan(training_plan_id)
        if before.get("patient_id") != self._patient_id(context):
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                before_state=before,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Plano de treino nao pertence ao paciente em foco.",
                intent=intent,
                message=message,
                status="skipped",
                tool_name="add_workout_observation",
            )

        updated = await self.workspace.update_training_plan_observation(
            training_plan_id=training_plan_id,
            observation=observation,
        )
        state_id = _optional_text(arguments.get("_state_id"))
        if state_id:
            await self.workspace.clear_ai_conversation_state(state_id)

        return await self._record_action(
            actor=actor,
            after_state=updated,
            arguments=arguments,
            before_state=before,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            intent=intent,
            message=message,
            result={
                "label": "Observacao adicionada ao treino",
                "summary": observation,
                "training_plan_id": training_plan_id,
            },
            status="executed",
            tool_name="add_workout_observation",
        )

    async def _record_action(
        self,
        *,
        actor: dict,
        arguments: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        message: dict,
        status: str,
        tool_name: str,
        after_state: Any = None,
        before_state: Any = None,
        error: str | None = None,
        intent: str | None = None,
        new_value: Any = None,
        old_value: Any = None,
        requires_confirmation: bool = False,
        result: dict | None = None,
    ) -> dict:
        clean_arguments = {
            key: value
            for key, value in arguments.items()
            if not str(key).startswith("_")
        }
        resolved_intent = intent or str(arguments.get("_intent") or tool_name)
        success = status == "executed"
        log_payload = {
            "actor_user_id": actor["id"],
            "user_id": actor["id"],
            "actor_role": actor["role"],
            "patient_id": (context.get("patient") or {}).get("id") or clean_arguments.get("patient_id"),
            "nutritionist_id": (context.get("nutritionist") or {}).get("id"),
            "chat_scope": chat_scope,
            "chat_id": chat["id"],
            "conversation_id": chat["id"],
            "message_id": message["id"],
            "tool_name": tool_name,
            "intent": resolved_intent,
            "status": status,
            "success": success,
            "requires_confirmation": requires_confirmation,
            "input": clean_arguments,
            "payload": clean_arguments,
            "result": result or {},
            "before_state": before_state,
            "after_state": after_state,
            "error": error,
            "error_message": error,
        }
        if old_value is not None:
            log_payload["old_value"] = old_value
        if new_value is not None:
            log_payload["new_value"] = new_value

        log = await self.workspace.insert_ai_action_log(log_payload)
        return {
            "error": error,
            "intent": resolved_intent,
            "label": (result or {}).get("label") or tool_name,
            "log_id": log["id"],
            "requires_confirmation": requires_confirmation,
            "result": result or {},
            "status": status,
            "success": success,
            "summary": (result or {}).get("summary") or error,
            "tool": tool_name,
        }

    def _patient_id(self, context: dict) -> str:
        patient = context.get("patient") or {}
        return str(patient.get("id") or "")

    def _nutritionist_id_for_tools(self, actor: dict, context: dict) -> str:
        if actor.get("role") != "nutritionist":
            raise ValueError("Apenas nutricionistas podem consultar dados de pacientes.")

        nutritionist_id = (context.get("nutritionist") or {}).get("id")
        if not nutritionist_id:
            raise ValueError("Cadastro de nutricionista nao encontrado no contexto.")
        return nutritionist_id

    async def _resolve_patient_id_for_tools(
        self,
        arguments: dict,
        context: dict,
        *,
        nutritionist_id: str,
    ) -> str | None:
        patient_id = arguments.get("patient_id")
        if patient_id:
            return str(patient_id)

        focused_patient_id = (context.get("patient") or {}).get("id")
        if focused_patient_id:
            return str(focused_patient_id)

        patient_name = _optional_text(
            arguments.get("patient_name")
            or arguments.get("query")
            or arguments.get("name")
        )
        if not patient_name:
            return None

        matches = await self.workspace.search_patients_by_name_for_nutritionist(
            nutritionist_id=nutritionist_id,
            query=patient_name,
            limit=5,
        )
        if settings.app_env == "development":
            print(
                "patient_search_result:",
                json.dumps(
                    {
                        "count": len(matches),
                        "matches": matches,
                        "query": patient_name,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            print(
                "Resultado search_patient_by_name:",
                json.dumps(
                    {
                        "count": len(matches),
                        "matches": matches,
                        "query": patient_name,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        if len(matches) == 1:
            return str(matches[0]["id"])
        if len(matches) > 1:
            names = ", ".join(match.get("full_name") or "Paciente sem nome" for match in matches)
            raise ValueError(
                f"Encontrei mais de um paciente chamado {patient_name}: {names}. "
                "Pergunte qual paciente usar."
            )
        raise ValueError(f"Não encontrei nenhum paciente chamado {patient_name} no seu cadastro.")

    def _patient_name_mismatch(self, context: dict, patient_name: Any) -> bool:
        if not patient_name:
            return False

        patient = context.get("patient") or {}
        profile = patient.get("profile") or context.get("profile") or {}
        focused_name = _normalize(str(profile.get("full_name") or ""))
        extracted_name = _normalize(str(patient_name))
        if not focused_name or not extracted_name:
            return False

        return extracted_name not in focused_name and focused_name not in extracted_name

    def _patient_id_mismatch(self, context: dict, patient_id: Any) -> bool:
        if not patient_id:
            return False
        if not context.get("patient"):
            return False
        return str(patient_id) != self._patient_id(context)

    def _patient_read_tool_for_request(self, normalized: str) -> str:
        if any(term in normalized for term in ("resumo", "resuma", "sumario", "prontuario", "dados do paciente")):
            return "get_patient_summary"
        if any(term in normalized for term in ("condicao", "condicoes", "clinica", "clinicas", "alergia", "restricao")):
            return "get_patient_conditions"
        if any(term in normalized for term in ("peso", "altura", "metrica", "metricas", "medida", "medidas")):
            return "get_patient_metrics"
        return "get_patient_profile"

    def _looks_like_patient_data_request(self, normalized: str) -> bool:
        if any(
            term in normalized
            for term in (
                "cadastrar",
                "cadastre",
                "criar",
                "crie",
                "registrar",
                "registre",
                "salvar",
                "salve",
                "atualizar",
                "atualize",
                "alterar",
                "altere",
            )
        ):
            return False

        return any(
            term in normalized
            for term in (
                "anos",
                "idade",
                "nascimento",
                "nasceu",
                "peso",
                "altura",
                "objetivo",
                "observacoes",
                "observacao",
                "condicoes",
                "condicao",
                "resumo",
                "resuma",
                "prontuario",
                "dados",
                "metricas",
                "metrica",
            )
        )

    def _extract_patient_query(self, raw: str, normalized: str) -> str | None:
        patterns = (
            r"\bpaciente\s+(?P<name>[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*(?:\s+[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*){0,4})",
            r"\b(?:do|da|de)\s+(?P<name>[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*(?:\s+[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*){0,4})",
            r"\b(?:o|a)\s+(?P<name>[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*(?:\s+[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'\-]*){0,4})",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, raw, flags=re.IGNORECASE):
                candidate = self._trim_patient_query(match.group("name"))
                if candidate:
                    return candidate

        words = [
            word
            for word in re.findall(r"[a-z0-9]+", normalized)
            if word not in PATIENT_QUERY_STOPWORDS and not word.isdigit()
        ]
        if 1 <= len(words) <= 4:
            return " ".join(words)
        return None

    def _trim_patient_query(self, value: str) -> str | None:
        words = re.findall(r"[a-z0-9]+", _normalize(value))
        cleaned: list[str] = []
        for word in words:
            if word in PATIENT_QUERY_STOPWORDS:
                break
            cleaned.append(word)
        return " ".join(cleaned) or None

    def _patient_profile_summary(self, profile: dict) -> str:
        name = profile.get("full_name") or "Paciente"
        birth_date = profile.get("birth_date")
        age = profile.get("age")
        if age is not None and birth_date:
            return (
                f"{name} tem {age} anos, considerando a data de nascimento "
                f"cadastrada: {_format_date_br(str(birth_date))}."
            )
        if not birth_date:
            return f"Não encontrei data de nascimento cadastrada para {name}."
        return f"Perfil de {name} consultado com sucesso."

    def _patient_metrics_summary(self, metrics: dict) -> str:
        latest_weight = metrics.get("latest_weight")
        if latest_weight:
            unit = latest_weight.get("unit") or ""
            recorded_at = latest_weight.get("recorded_at") or latest_weight.get("created_at")
            return (
                "Peso atual encontrado: "
                f"{latest_weight.get('value')} {unit}".strip()
                + (f" em {recorded_at}." if recorded_at else ".")
            )
        variable_count = len(metrics.get("variable_metrics") or [])
        main_count = len(metrics.get("main_metrics") or [])
        if variable_count or main_count:
            return f"Encontrei {variable_count + main_count} métricas cadastradas para o paciente."
        return "Não encontrei métricas cadastradas para esse paciente."

    def _patient_conditions_summary(self, conditions: list[dict]) -> str:
        if not conditions:
            return "Não encontrei condições clínicas cadastradas para esse paciente."
        titles = [
            condition.get("title")
            or condition.get("description")
            or condition.get("condition_type")
            or "condição"
            for condition in conditions[:5]
        ]
        return f"Condições encontradas: {', '.join(titles)}."

    def _patient_summary_text(self, payload: dict) -> str:
        profile = payload.get("profile") or {}
        metrics = payload.get("metrics") or {}
        conditions = payload.get("conditions") or []
        diets = payload.get("diets") or []
        workouts = payload.get("workouts") or []
        appointments = payload.get("appointments") or []
        parts = [
            self._patient_profile_summary(profile),
            self._patient_metrics_summary(metrics),
            self._patient_conditions_summary(conditions),
            f"Dietas cadastradas: {len(diets)}.",
            f"Treinos cadastrados: {len(workouts)}.",
            f"Agendamentos cadastrados: {len(appointments)}.",
        ]
        return " ".join(parts)

    def _classify_intent(self, user_message: str, *, has_pending_state: bool) -> str:
        normalized = _normalize(user_message)
        if _is_confirmation_message(normalized):
            return "confirm_pending_action" if has_pending_state else "answer_question"
        if _is_cancellation_message(normalized):
            return "cancel_pending_action" if has_pending_state else "answer_question"
        if self._looks_like_birth_date_update(normalized):
            return "update_patient_birth_date"
        if any(
            term in normalized
            for term in (
                "treino",
                "treinos",
                "training",
                "workout",
                "exercicio",
                "exercicios",
                "plano de treino",
                "tabela de treino",
            )
        ):
            if any(term in normalized for term in ("cadastr", "criar", "monte", "montar", "gerar", "salvar")):
                return "create_training_plan"
            if any(term in normalized for term in ("observacao", "observacoes", "nota", "adicion")):
                return "add_training_observation"
            return "answer_question"
        if any(term in normalized for term in ("refeicao", "cafe da manha", "almoco", "jantar", "lanche", "ceia")):
            if any(term in normalized for term in ("adicionar", "adicione", "colocar", "coloque")):
                return "add_food_to_meal"
        if self._looks_like_taco_request(normalized):
            return "taco_lookup"
        if self._looks_like_patient_data_request(normalized):
            return "patient_lookup"
        if any(term in normalized for term in ("lesao", "lesion", "machuc", "contus", "distens")):
            if any(term in normalized for term in ("cadastr", "registr", "adicion", "criar", "nova", "novo")):
                return "create_injury"
        if "peso" in normalized or any(term in normalized for term in ("engordei", "emagreci", "ganhei", "perdi")):
            return "update_weight"
        if any(term in normalized for term in ("consulta", "retorno", "agenda", "marcar", "reagendar")):
            return "create_appointment"
        return "answer_question"

    def _resolve_pending_action(
        self,
        *,
        pending_state: dict | None,
        user_message: str,
    ) -> tuple[str, dict] | None:
        if not pending_state:
            return None

        normalized = _normalize(user_message)
        if _is_cancellation_message(normalized):
            return None

        pending_action = pending_state.get("pending_action")
        payload = dict(pending_state.get("pending_payload") or {})
        payload["_state_id"] = pending_state["id"]
        payload["patient_id"] = pending_state.get("patient_id")

        if pending_action == "update_patient_birth_date" and payload.get("needs_day_month"):
            birth_date = _birth_date_from_day_month_year(
                user_message,
                payload.get("birth_year"),
            )
            if birth_date:
                payload.pop("needs_day_month", None)
                payload["birth_date"] = birth_date
                return "update_patient_birth_date", payload

        if not _is_confirmation_message(normalized):
            return None

        if pending_action in PENDING_TOOLS:
            return str(pending_action), payload
        return None

    def _normalize_training_plan_payload(self, arguments: dict, context: dict) -> dict:
        patient = context.get("patient") or {}
        profile = patient.get("profile") or context.get("profile") or {}
        patient_name = str(profile.get("full_name") or "Paciente").split(" ")[0]
        title = _sentence_text(
            str(arguments.get("title") or f"Treino adaptado para {patient_name}"),
            160,
        )
        objective = _optional_text(arguments.get("objective")) or patient.get("objective")
        restrictions = _text_list(arguments.get("restrictions"))
        if not restrictions:
            restrictions = [
                condition_summary(condition)
                for condition in context.get("conditions", [])
                if condition.get("condition_type") in {"injury", "disease", "observation"}
            ][:12]

        raw_days = arguments.get("days") or []
        if not raw_days and arguments.get("exercises"):
            raw_days = [
                {
                    "name": arguments.get("day_name") or "Treino A",
                    "focus": arguments.get("focus") or "Treino adaptado geral",
                    "exercises": arguments.get("exercises"),
                }
            ]

        days = []
        for day_index, raw_day in enumerate(raw_days):
            day_data = raw_day if isinstance(raw_day, dict) else {}
            raw_exercises = day_data.get("exercises") or []
            exercises = []
            for exercise in raw_exercises or []:
                normalized = self._normalize_training_exercise(exercise)
                if normalized:
                    exercises.append(normalized)
            if exercises:
                days.append(
                    {
                        "name": _sentence_text(
                            str(day_data.get("name") or f"Treino {chr(65 + min(day_index, 25))}"),
                            80,
                        ),
                        "focus": _optional_text(day_data.get("focus")) or "Treino adaptado geral",
                        "exercises": exercises,
                    }
                )

        return {
            "_intent": arguments.get("_intent"),
            "days": days,
            "objective": _sentence_text(objective, 300) if objective else None,
            "observations": _sentence_text(str(arguments.get("observations") or ""), 1000)
            if arguments.get("observations")
            else None,
            "patient_id": self._patient_id(context),
            "patient_name": _optional_text(arguments.get("patient_name")),
            "restrictions": restrictions,
            "title": title,
        }

    def _normalize_training_exercise(self, exercise: Any) -> dict | None:
        if not isinstance(exercise, dict):
            return None
        name = _optional_text(exercise.get("exercise_name") or exercise.get("name"))
        if not name:
            return None
        return {
            "exercise_name": _sentence_text(name, 160),
            "load_guidance": _optional_text(exercise.get("load_guidance") or exercise.get("load_info")),
            "muscle_group": _optional_text(exercise.get("muscle_group")),
            "notes": _optional_text(exercise.get("notes")),
            "reps": _sentence_text(str(exercise.get("reps") or "10-12"), 80),
            "rest": _optional_text(exercise.get("rest") or exercise.get("rest_time")),
            "sets": _positive_int(exercise.get("sets"), default=3),
        }

    def _validate_training_plan_payload(self, payload: dict) -> str | None:
        if not payload.get("patient_id"):
            return "Treino sem paciente valido."
        if not payload.get("title"):
            return "Treino sem titulo."
        if not payload.get("days"):
            return "Treino sem dias estruturados."
        exercise_count = sum(len(day.get("exercises") or []) for day in payload["days"])
        if exercise_count <= 0:
            return "Treino sem exercicios estruturados."
        for day in payload["days"]:
            for exercise in day.get("exercises") or []:
                if not exercise.get("exercise_name"):
                    return "Exercicio sem nome."
                if not exercise.get("sets") or not exercise.get("reps"):
                    return "Exercicio sem series ou repeticoes."
        return None

    def _training_plan_description(self, payload: dict) -> str:
        parts = []
        if payload.get("objective"):
            parts.append(f"Objetivo: {payload['objective']}")
        if payload.get("restrictions"):
            parts.append(f"Restricoes: {', '.join(payload['restrictions'])}")
        if payload.get("observations"):
            parts.append(f"Observacoes: {payload['observations']}")
        return "\n".join(parts) or "Treino criado pela IA do Star Nutri."

    def _fallback_tool_call(
        self,
        *,
        allowed_tools: set[str],
        chat_scope: str,
        context: dict,
        intent: str,
        user_message: str,
    ) -> tuple[str, dict] | None:
        raw = user_message.strip()
        normalized = _normalize(raw)

        injury = self._fallback_injury(raw, normalized, context)
        if intent == "create_injury" and injury and "register_injury" in allowed_tools:
            return "register_injury", injury

        weight = self._fallback_weight(raw, normalized, context)
        if intent == "update_weight" and weight and "register_weight_change" in allowed_tools:
            return "register_weight_change", weight

        food = self._fallback_food(raw, normalized, context)
        if (
            intent == "add_food_to_meal"
            and chat_scope == "nutritionist"
            and food
            and "add_taco_food_to_meal" in allowed_tools
        ):
            quantity_g = _quantity_grams(food.get("quantity"))
            if quantity_g is not None:
                return "add_taco_food_to_meal", {
                    **food,
                    "quantity_g": quantity_g,
                }
        if (
            intent == "add_food_to_meal"
            and chat_scope == "nutritionist"
            and food
            and "add_food_to_meal" in allowed_tools
        ):
            return "add_food_to_meal", food

        taco = self._fallback_taco(raw, normalized)
        if intent == "taco_lookup" and taco:
            if taco.get("quantity_g") and "calculate_taco_food_nutrients" in allowed_tools:
                return "calculate_taco_food_nutrients", taco
            if "search_taco_foods" in allowed_tools:
                return "search_taco_foods", taco

        birth_date = self._fallback_birth_date(raw, normalized, context)
        if (
            intent == "update_patient_birth_date"
            and chat_scope == "nutritionist"
            and birth_date
            and "update_patient_birth_date" in allowed_tools
        ):
            return "update_patient_birth_date", birth_date

        return None

    def _looks_actionable(self, user_message: str) -> bool:
        normalized = _normalize(user_message)
        return any(
            term in normalized
            for term in (
                "adicionar",
                "adicione",
                "alterar",
                "atualizar",
                "caloria",
                "calorias",
                "cadastrar",
                "cadastre",
                "cancelar",
                "corrige",
                "corrigir",
                "corrija",
                "criar",
                "deletar",
                "engordei",
                "emagreci",
                "exercicio",
                "exercicios",
                "excluir",
                "ganhei",
                "marcar",
                "monte",
                "montar",
                "perdi",
                "plano",
                "proteina",
                "proteinas",
                "registrar",
                "registre",
                "remover",
                "reagendar",
                "salvar",
                "tabela",
                "taco",
                "treino",
                "treinos",
            )
        )

    def _looks_like_taco_request(self, normalized: str) -> bool:
        if "taco" in normalized or "tabela brasileira" in normalized:
            return True
        has_quantity = bool(re.search(r"\b\d+(?:[,.]\d+)?\s*(?:g|gramas|kg)\b", normalized))
        has_nutrient = any(
            term in normalized
            for term in (
                "caloria",
                "calorias",
                "kcal",
                "macro",
                "macros",
                "nutriente",
                "nutrientes",
                "proteina",
                "proteinas",
                "carboidrato",
                "carboidratos",
                "gordura",
                "fibra",
                "sodio",
            )
        )
        return has_quantity and has_nutrient

    def _fallback_injury(
        self,
        raw: str,
        normalized: str,
        context: dict,
    ) -> dict | None:
        has_injury = any(
            term in normalized
            for term in (
                "lesao",
                "lesion",
                "machuc",
                "contus",
                "distens",
                "dor ",
                " dor",
            )
        )
        has_write_intent = any(
            term in normalized
            for term in (
                "cadastr",
                "registr",
                "adicion",
                "criar",
                "nova",
                "novo",
                "esta com",
                "ta com",
                "tem ",
            )
        )
        if not has_injury or not has_write_intent:
            return None

        body_part = self._extract_body_part(normalized)
        if not body_part:
            return None

        severity = self._extract_injury_severity(normalized)
        origin = self._extract_injury_origin(raw, normalized)
        return {
            "date": _sao_paulo_today(),
            "description": self._build_injury_description(body_part, origin),
            "local": body_part,
            "origin": origin,
            "patient_name": self._extract_patient_name(context, normalized),
            "severity": severity or "Não informado",
        }

    def _fallback_weight(
        self,
        raw: str,
        normalized: str,
        context: dict,
    ) -> dict | None:
        match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:kg|quilo|quilos)\b", normalized)
        if not match:
            return None

        amount = _number(match.group(1))
        if amount is None:
            return None

        if any(term in normalized for term in ("engordei", "ganhei", "aumentei")):
            return {
                "delta_kg": amount,
                "patient_name": self._extract_patient_name(context, normalized),
            }

        if any(term in normalized for term in ("emagreci", "perdi", "reduzi", "diminui")):
            return {
                "delta_kg": -amount,
                "patient_name": self._extract_patient_name(context, normalized),
            }

        if any(term in normalized for term in ("peso", "estou com", "estou pesando")):
            return {
                "current_weight_kg": amount,
                "patient_name": self._extract_patient_name(context, normalized),
            }

        return None

    def _fallback_food(
        self,
        raw: str,
        normalized: str,
        context: dict,
    ) -> dict | None:
        if not any(term in normalized for term in ("adicionar", "adicione", "colocar", "coloque")):
            return None

        match = re.search(
            r"(?:adicionar|adicione|colocar|coloque)\s+"
            r"(?P<quantity>\d+(?:[,.]\d+)?\s*(?:g|gramas|kg|ml|unidades?|fatias?|colheres?))\s+"
            r"(?:de\s+)?(?P<food>.+?)\s+"
            r"(?:no|na|ao|a)\s+(?P<meal>cafe da manha|cafe|almoço|almoco|jantar|lanche|ceia)",
            normalized,
        )
        if not match:
            return None

        return {
            "food_name": match.group("food").strip(),
            "meal_name": match.group("meal"),
            "patient_name": self._extract_patient_name(context, normalized),
            "quantity": match.group("quantity"),
        }

    def _fallback_taco(self, raw: str, normalized: str) -> dict | None:
        quantity = _quantity_grams(raw)
        food_name: str | None = None

        patterns = (
            r"(?:de|do|da)\s+(?P<food>[a-z0-9ãõáéíóúâêôç\s,-]+?)(?:\s+segundo|\s+na\s+taco|\s+pela\s+taco|\?|$)",
            r"taco\s+(?P<food>[a-z0-9ãõáéíóúâêôç\s,-]+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                food_name = match.group("food")
                break

        if not food_name:
            cleaned = re.sub(
                r"\b(?:quantas?|calorias?|kcal|tem|possui|segundo|taco|tabela|brasileira|"
                r"composicao|nutricional|nutrientes?|macros?|proteinas?|carboidratos?|"
                r"gorduras?|fibra|sodio|em|de|do|da|para|por|100g)\b",
                " ",
                normalized,
            )
            cleaned = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:g|gramas|kg)\b", " ", cleaned)
            food_name = " ".join(cleaned.split())

        if not food_name:
            return None

        payload: dict[str, Any] = {"query": food_name.strip()}
        if quantity is not None:
            payload["quantity_g"] = quantity
        return payload

    def _fallback_birth_date(
        self,
        raw: str,
        normalized: str,
        context: dict,
    ) -> dict | None:
        if not self._looks_like_birth_date_update(normalized):
            return None

        patient_id = self._patient_id(context) or None
        patient_name = (
            self._extract_patient_name(context, normalized)
            or self._extract_patient_query(raw, normalized)
        )

        full_date = _extract_birth_date(raw)
        if full_date:
            payload: dict[str, Any] = {
                "birth_date": full_date,
                "patient_name": patient_name,
            }
            if patient_id:
                payload["patient_id"] = patient_id
            return payload

        birth_year = _extract_birth_year(normalized)
        if birth_year is None:
            return None

        current_birth_date = _safe_birth_date((context.get("patient") or {}).get("birth_date"))
        if current_birth_date:
            current_date = datetime.fromisoformat(current_birth_date).date()
            birth_date = _compose_birth_date(
                birth_year,
                current_date.month,
                current_date.day,
            )
            if birth_date:
                payload = {
                    "birth_date": birth_date,
                    "birth_year": birth_year,
                    "patient_name": patient_name,
                }
                if patient_id:
                    payload["patient_id"] = patient_id
                return payload

        payload = {
            "birth_year": birth_year,
            "patient_name": patient_name,
        }
        if patient_id:
            payload["patient_id"] = patient_id
        return payload

    def _looks_like_birth_date_update(self, normalized: str) -> bool:
        has_birth_term = any(
            term in normalized
            for term in (
                "data de nascimento",
                "nascimento",
                "nasceu",
                "nascido",
                "nascida",
                "birth date",
                "born date",
                "dob",
            )
        )
        if not has_birth_term:
            return False

        has_write_intent = any(
            term in normalized
            for term in (
                "alter",
                "atualiz",
                "corrig",
                "editar",
                "mudar",
                "trocar",
                "ajust",
                "definir",
                "na verdade",
            )
        )
        has_inline_birth_value = bool(
            re.search(r"\b(?:nasceu|nascido|nascida)\s+(?:em|no dia|na data)?\s*\d", normalized)
            or (has_birth_term and re.search(r"\d{1,4}[./-]\d{1,2}", normalized))
        )
        return has_write_intent or has_inline_birth_value

    def _extract_body_part(self, normalized: str) -> str | None:
        known_parts = (
            "olho",
            "olhos",
            "cabeca",
            "cabeca",
            "face",
            "rosto",
            "coxa",
            "joelho",
            "ombro",
            "lombar",
            "costas",
            "perna",
            "panturrilha",
            "tornozelo",
            "quadril",
            "punho",
            "braco",
            "cotovelo",
            "peito",
            "pescoco",
        )
        for part in known_parts:
            if part in normalized:
                return part

        match = re.search(r"\b(?:na|no|em|do|da)\s+([a-z0-9 ]{3,32})", normalized)
        if not match:
            return None

        candidate = match.group(1).strip()
        return candidate.split(" do ")[0].split(" da ")[0].split(" para ")[0][:32]

    def _normalize_injury_payload(self, arguments: dict, context: dict, message: dict) -> dict:
        raw_message = str(message.get("content") or "")
        local = _optional_text(
            arguments.get("local")
            or arguments.get("body_part")
            or arguments.get("location")
            or arguments.get("injury_local")
        )
        severity = _optional_text(arguments.get("severity")) or "Não informado"
        origin = _optional_text(arguments.get("origin"))
        recommendations = _optional_text(arguments.get("recommendations"))
        notes = _optional_text(arguments.get("notes"))
        date = _optional_text(arguments.get("date") or arguments.get("started_at"))
        description = _optional_text(arguments.get("description"))

        if local:
            local = _title_text(local)

        if not date:
            date = _sao_paulo_today()
        else:
            date = _safe_date(date)

        raw_like_values = {
            _normalize(raw_message),
            _normalize(str(arguments.get("raw_arguments") or "")),
        }
        if description and (
            _normalize(description) in raw_like_values
            or self._looks_like_raw_injury_prompt(description)
        ):
            description = None
        if notes and (
            _normalize(notes) in raw_like_values
            or self._looks_like_raw_injury_prompt(notes)
        ):
            notes = None

        if not description:
            description = self._build_injury_description(local, origin)

        return {
            "date": date,
            "description": _sentence_text(description, 500),
            "local": _sentence_text(local or "", 120),
            "notes": _sentence_text(notes, 500) if notes else None,
            "origin": _sentence_text(origin, 240) if origin else None,
            "patient_id": self._patient_id(context),
            "patient_name": _optional_text(arguments.get("patient_name")),
            "recommendations": _sentence_text(recommendations, 500)
            if recommendations
            else None,
            "severity": _sentence_text(severity, 80),
            "_intent": arguments.get("_intent"),
        }

    def _extract_injury_severity(self, normalized: str) -> str | None:
        if any(term in normalized for term in ("gravissima", "gravissimo", "muito grave")):
            return "Gravíssima"
        if any(term in normalized for term in ("grave", "severa", "severo")):
            return "Grave"
        if any(term in normalized for term in ("moderada", "moderado", "media", "medio")):
            return "Moderada"
        if any(term in normalized for term in ("leve", "pequena", "pequeno")):
            return "Leve"
        return None

    def _extract_injury_origin(self, raw: str, normalized: str) -> str | None:
        raw_clean = " ".join(raw.strip().split())
        raw_match = re.search(
            r"(?:trauma|batida|impacto|queda|acidente)\s+(?:com|por|de|do|da)\s+(.+?)(?:[.!?]|$)",
            raw_clean,
            flags=re.IGNORECASE,
        )
        if raw_match:
            return raw_match.group(1).strip(" .,;:")[:180]

        match = re.search(
            r"(?:trauma|batida|impacto|queda|acidente)\s+(?:com|por|de|do|da)\s+(.+?)(?:[.!?]|$)",
            normalized,
        )
        if not match:
            if "trauma" in normalized:
                return "trauma"
            return None

        return match.group(1).strip()[:180]

    def _build_injury_description(self, local: str | None, origin: str | None) -> str:
        local_text = (local or "local não informado").strip().lower()
        if origin:
            origin_text = origin.strip().rstrip(".")
            if _normalize(origin_text) == "trauma":
                return f"Lesão no {local_text} decorrente de trauma."
            return f"Lesão no {local_text} decorrente de trauma com {origin_text}."
        return f"Lesão relatada no {local_text}."

    def _looks_like_raw_injury_prompt(self, value: str) -> bool:
        normalized = _normalize(value)
        has_action = any(
            term in normalized
            for term in ("cadastre", "cadastrar", "registre", "registrar", "adicione")
        )
        has_injury = "lesao" in normalized or "machuc" in normalized
        return has_action and has_injury

    def _extract_patient_name(self, context: dict, normalized: str) -> str | None:
        patient = context.get("patient") or {}
        profile = patient.get("profile") or context.get("profile") or {}
        full_name = str(profile.get("full_name") or "").strip()
        if not full_name:
            return None

        for token in _normalize(full_name).split():
            if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", normalized):
                return token

        return None

    def _macro_payload(self, diet: dict, arguments: dict) -> dict:
        mapping = {
            "calories": "calories",
            "protein_g": "protein",
            "carbs_g": "carbs",
            "fats_g": "fats",
        }
        payload: dict[str, float | int] = {}
        for input_key, diet_key in mapping.items():
            value = _number(arguments.get(input_key))
            if value is None:
                continue
            current = _number(diet.get(diet_key)) or 0
            total = current + value
            payload[diet_key] = int(total) if diet_key == "calories" else total
        return payload


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", ".").strip())
    except ValueError:
        return None


def _object_payload(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _friendly_tool_error(exc: Exception) -> str:
    message = str(exc).strip()
    if message.startswith("Não encontrei nenhum paciente chamado"):
        return message
    if message.startswith("Encontrei mais de um paciente chamado"):
        return message
    if message.startswith("Não identifiquei qual paciente"):
        return message
    return "Não foi possível concluir esta ação agora. Tente novamente em instantes."


def _calculate_taco_nutrients(food: dict, quantity_g: float) -> dict[str, float]:
    factor = quantity_g / 100
    return {
        "carbohydrate_g": _round_nutrient(food.get("carbohydrate_g"), factor),
        "energy_kcal": _round_nutrient(food.get("energy_kcal"), factor),
        "fiber_g": _round_nutrient(food.get("fiber_g"), factor),
        "lipid_g": _round_nutrient(food.get("lipid_g"), factor),
        "protein_g": _round_nutrient(food.get("protein_g"), factor),
        "sodium_mg": _round_nutrient(food.get("sodium_mg"), factor),
    }


def _round_nutrient(value: Any, factor: float) -> float:
    number = _number(value) or 0
    return round(number * factor, 2)


def _compact_taco_food(food: dict) -> dict:
    return {
        "id": food.get("id"),
        "code": food.get("code"),
        "name": food.get("name"),
        "category": food.get("category"),
        "energy_kcal": food.get("energy_kcal"),
        "protein_g": food.get("protein_g"),
        "carbohydrate_g": food.get("carbohydrate_g"),
        "lipid_g": food.get("lipid_g"),
        "fiber_g": food.get("fiber_g"),
        "sodium_mg": food.get("sodium_mg"),
    }


def _taco_food_summary(food: dict) -> str:
    return (
        f"{food.get('name')} por 100g: "
        f"{_format_optional_number(food.get('energy_kcal'))} kcal, "
        f"{_format_optional_number(food.get('protein_g'))}g proteinas, "
        f"{_format_optional_number(food.get('carbohydrate_g'))}g carboidratos, "
        f"{_format_optional_number(food.get('lipid_g'))}g lipidios."
    )


def _nutrient_summary(food: dict, nutrients: dict, quantity_g: float) -> str:
    return (
        f"{_format_number(quantity_g)}g de {food.get('name')} segundo a TACO: "
        f"{_format_optional_number(nutrients.get('energy_kcal'))} kcal, "
        f"{_format_optional_number(nutrients.get('protein_g'))}g proteinas, "
        f"{_format_optional_number(nutrients.get('carbohydrate_g'))}g carboidratos, "
        f"{_format_optional_number(nutrients.get('lipid_g'))}g lipidios, "
        f"{_format_optional_number(nutrients.get('fiber_g'))}g fibras."
    )


def _quantity_grams(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
        return number if number > 0 else None

    text = str(value).lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(kg|quilo|quilos|g|gramas)?", text)
    if not match:
        return None

    amount = _number(match.group(1))
    if amount is None or amount <= 0:
        return None
    unit = match.group(2) or "g"
    return amount * 1000 if unit in {"kg", "quilo", "quilos"} else amount


def _diet_totals(meals: list[dict]) -> dict[str, float]:
    totals = {
        "carbohydrate_g": 0.0,
        "energy_kcal": 0.0,
        "fiber_g": 0.0,
        "lipid_g": 0.0,
        "protein_g": 0.0,
        "sodium_mg": 0.0,
    }
    for meal in meals:
        meal_totals = _meal_totals(meal)
        for key, value in meal_totals.items():
            totals[key] = round(totals[key] + value, 2)
    return totals


def _meal_totals(meal: dict) -> dict[str, float]:
    item_totals = {
        "carbohydrate_g": 0.0,
        "energy_kcal": 0.0,
        "fiber_g": 0.0,
        "lipid_g": 0.0,
        "protein_g": 0.0,
        "sodium_mg": 0.0,
    }
    for item in meal.get("items") or []:
        item_totals["carbohydrate_g"] += _number(item.get("carbohydrate_g")) or 0
        item_totals["energy_kcal"] += _number(item.get("energy_kcal")) or 0
        item_totals["fiber_g"] += _number(item.get("fiber_g")) or 0
        item_totals["lipid_g"] += _number(item.get("lipid_g")) or 0
        item_totals["protein_g"] += _number(item.get("protein_g")) or 0
        item_totals["sodium_mg"] += _number(item.get("sodium_mg")) or 0

    if any(value > 0 for value in item_totals.values()):
        return {key: round(value, 2) for key, value in item_totals.items()}

    food_totals = {
        "carbohydrate_g": 0.0,
        "energy_kcal": 0.0,
        "fiber_g": 0.0,
        "lipid_g": 0.0,
        "protein_g": 0.0,
        "sodium_mg": 0.0,
    }
    for food in meal.get("foods") or []:
        food_totals["carbohydrate_g"] += (
            _number(food.get("carbohydrate_g")) or _number(food.get("carbs_g")) or 0
        )
        food_totals["energy_kcal"] += (
            _number(food.get("energy_kcal")) or _number(food.get("calories")) or 0
        )
        food_totals["fiber_g"] += _number(food.get("fiber_g")) or 0
        food_totals["lipid_g"] += (
            _number(food.get("lipid_g")) or _number(food.get("fats_g")) or 0
        )
        food_totals["protein_g"] += _number(food.get("protein_g")) or 0
        food_totals["sodium_mg"] += _number(food.get("sodium_mg")) or 0
    return {key: round(value, 2) for key, value in food_totals.items()}


def _format_optional_number(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "-"
    return _format_number(number)


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_value.lower().split())


def _same_recorded_day(record: dict, candidate: str) -> bool:
    current = record.get("recorded_at") or record.get("created_at")
    if not current:
        return False

    try:
        current_date = datetime.fromisoformat(
            str(current).replace("Z", "+00:00"),
        ).date()
        candidate_date = datetime.fromisoformat(
            str(candidate).replace("Z", "+00:00"),
        ).date()
    except ValueError:
        return False

    return current_date == candidate_date


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        raw_items = value
    else:
        raw_items = re.split(r"[,;\n]+", str(value))

    items: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _optional_text(item)
        if not text:
            continue
        normalized = _normalize(text)
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(_sentence_text(text, 180))
    return items


def _positive_int(value: Any, *, default: int) -> int:
    number = _number(value)
    if number is None or number <= 0:
        return default
    return max(1, int(number))


def _is_confirmation_message(normalized: str) -> bool:
    compact = normalized.strip(" .,!?:;")
    return compact in {
        "sim",
        "s",
        "ok",
        "okay",
        "pode",
        "pode sim",
        "confirmo",
        "confirmado",
        "adiciona",
        "adicione",
        "adicionar",
        "isso",
        "isso mesmo",
        "prosseguir",
        "pode prosseguir",
        "mande",
        "manda",
        "salva",
        "salvar",
    }


def _is_cancellation_message(normalized: str) -> bool:
    compact = normalized.strip(" .,!?:;")
    return compact in {
        "nao",
        "n",
        "cancela",
        "cancelar",
        "deixa",
        "deixa pra la",
        "nao precisa",
        "ignora",
        "pare",
        "parar",
    }


def condition_summary(condition: dict) -> str:
    condition_type = _optional_text(condition.get("condition_type")) or "condicao"
    title = _optional_text(condition.get("title"))
    local = _optional_text(condition.get("injury_local"))
    severity = _optional_text(condition.get("severity"))
    description = _optional_text(condition.get("description"))

    if local and condition_type == "injury":
        base = f"lesao em {local}"
    else:
        base = title or description or condition_type

    if severity and severity.lower() != "não informado":
        base = f"{base} ({severity})"
    return _sentence_text(base, 180)


def _title_text(value: str) -> str:
    parts = str(value).strip().split()
    return " ".join(part[:1].upper() + part[1:].lower() for part in parts)


def _sentence_text(value: str, max_length: int) -> str:
    text = " ".join(str(value).strip().split())
    if not text:
        return text
    text = text[:max_length].strip()
    return text[:1].upper() + text[1:]


def _safe_date(value: str) -> str:
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return _sao_paulo_today()


def _safe_birth_date(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return _extract_birth_date(text)

    if parsed.year < 1900 or parsed > _sao_paulo_now().date():
        return None
    return parsed.isoformat()


def _extract_birth_date(value: str) -> str | None:
    text = str(value).strip()

    iso_match = re.search(
        r"\b(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})\b",
        text,
    )
    if iso_match:
        return _compose_birth_date(
            _birth_year(iso_match.group("year")),
            int(iso_match.group("month")),
            int(iso_match.group("day")),
        )

    br_match = re.search(
        r"\b(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{2,4})\b",
        text,
    )
    if br_match:
        return _compose_birth_date(
            _birth_year(br_match.group("year")),
            int(br_match.group("month")),
            int(br_match.group("day")),
        )

    return None


def _extract_birth_year(normalized: str) -> int | None:
    patterns = (
        r"\b(?:nasceu|nascido|nascida)\s+(?:em|no ano de|ano de|no ano)?\s*(\d{2,4})\b",
        r"\b(?:nascimento|data de nascimento|dob|birth date|born date).*?(\d{2,4})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            year = _birth_year(match.group(1))
            if year:
                return year
    return None


def _birth_year(value: Any) -> int | None:
    if value is None:
        return None

    text = str(value).strip()
    if not re.fullmatch(r"\d{2,4}", text):
        return None

    year = int(text)
    current_year = _sao_paulo_now().year
    if len(text) <= 2:
        year = 2000 + year
        if year > current_year:
            year -= 100

    if year < 1900 or year > current_year:
        return None
    return year


def _compose_birth_date(year: int | None, month: int, day: int) -> str | None:
    if not year:
        return None
    try:
        candidate = datetime(year, month, day).date()
    except ValueError:
        return None
    if candidate.year < 1900 or candidate > _sao_paulo_now().date():
        return None
    return candidate.isoformat()


def _birth_date_from_day_month_year(value: str, birth_year: Any) -> str | None:
    full_date = _extract_birth_date(value)
    if full_date:
        return full_date

    year = _birth_year(birth_year)
    if not year:
        return None

    match = re.search(
        r"\b(?P<day>\d{1,2})[./-](?P<month>\d{1,2})(?:[./-]\d{2,4})?\b",
        str(value),
    )
    if not match:
        return None

    return _compose_birth_date(
        year,
        int(match.group("month")),
        int(match.group("day")),
    )


def _format_date_br(value: str) -> str:
    parsed = _safe_birth_date(value)
    if not parsed:
        return str(value)
    date_value = datetime.fromisoformat(parsed).date()
    return date_value.strftime("%d/%m/%Y")


def _sao_paulo_now() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=-3)))


def _sao_paulo_today() -> str:
    return _sao_paulo_now().date().isoformat()


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_patient_by_name",
            "description": (
                "Busca pacientes reais do nutricionista por nome completo, primeiro nome "
                "ou busca parcial sem diferenciar maiúsculas, minúsculas ou acentos. "
                "Use antes de afirmar que um paciente citado não existe."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_profile",
            "description": (
                "Lê o cadastro real de um paciente do nutricionista e retorna nome, gênero, "
                "data de nascimento, idade calculada, altura quando houver métrica, objetivo "
                "e observações. Use para perguntas sobre idade, nascimento, objetivo ou perfil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_metrics",
            "description": "Consulta métricas reais do paciente, incluindo peso atual quando cadastrado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_conditions",
            "description": "Consulta condições clínicas, alergias, restrições, lesões e observações clínicas cadastradas do paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_summary",
            "description": (
                "Consulta um resumo operacional real do paciente com cadastro, idade calculada, "
                "métricas recentes, condições, dietas, treinos e agenda."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient_profile",
            "description": (
                "Atualiza campos simples do perfil do paciente em foco. Use somente com paciente "
                "em foco e quando a alteração estiver clara."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "birth_date": {"type": "string"},
                    "full_name": {"type": "string"},
                    "gender": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "notes": {"type": "string"},
                    "objective": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "phone": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_injury",
            "description": (
                "Registra uma lesao, dor localizada ou problema fisico como condicao "
                "do paciente em foco. Use somente dados estruturados extraidos da "
                "intencao; nunca envie o prompt bruto como descricao ou notas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "description": "Data de inicio em YYYY-MM-DD. Use hoje se nao informada.",
                        "type": "string",
                    },
                    "description": {
                        "description": "Descricao clinica curta e estruturada, nunca o prompt bruto.",
                        "type": "string",
                    },
                    "local": {
                        "description": "Local anatomico da lesao, exemplo: Olho, Joelho, Ombro.",
                        "type": "string",
                    },
                    "notes": {
                        "description": "Observacoes opcionais curtas, sem copiar o prompt bruto.",
                        "type": "string",
                    },
                    "origin": {
                        "description": "Origem/causa objetiva, exemplo: trauma com cano atravessado.",
                        "type": "string",
                    },
                    "patient_id": {
                        "description": "ID do paciente em foco, quando conhecido pelo contexto operacional.",
                        "type": "string",
                    },
                    "patient_name": {"type": "string"},
                    "recommendations": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["local", "description", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_weight_change",
            "description": "Registra peso atual ou calcula novo peso a partir de uma alteracao em kg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_weight_kg": {"type": "number"},
                    "delta_kg": {"type": "number"},
                    "patient_name": {"type": "string"},
                    "recorded_at": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_progress",
            "description": "Registra uma metrica corporal simples, como cintura, quadril, percentual de gordura ou outra evolucao.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "recorded_at": {"type": "string"},
                },
                "required": ["metric_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_observation",
            "description": "Adiciona uma observacao relevante ao prontuario/contexto do paciente em foco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "observation": {"type": "string"},
                },
                "required": ["observation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_food_to_meal",
            "description": "Adiciona um alimento a uma refeicao da dieta ativa do paciente em foco. Uso exclusivo do nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_name": {"type": "string"},
                    "food_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "quantity": {"type": "string"},
                    "notes": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fats_g": {"type": "number"},
                },
                "required": ["meal_name", "food_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_taco_foods",
            "description": "Busca alimentos reais na Tabela Brasileira de Composição de Alimentos (TACO). Use antes de responder sobre alimento da TACO.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_taco_food",
            "description": "Obtém a composição por 100g de um alimento da TACO por ID ou por nome aproximado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_taco_food_nutrients",
            "description": "Calcula nutrientes de um alimento TACO para uma quantidade em gramas. Não use valores inventados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                    "quantity_g": {"type": "number"},
                    "quantity": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_taco_food_to_meal",
            "description": "Adiciona um alimento da TACO a uma refeição da dieta ativa do paciente em foco e calcula macros automaticamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                    "meal_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "quantity_g": {"type": "number"},
                    "quantity": {"type": "string"},
                },
                "required": ["meal_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient_birth_date",
            "description": (
                "Atualiza a data de nascimento do paciente em foco quando a nova data "
                "estiver claramente informada. Para ano abreviado, como 'nasceu em 98', "
                "use o dia e mes atuais do cadastro se existirem e converta para YYYY-MM-DD."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "birth_date": {
                        "description": "Data completa no formato YYYY-MM-DD.",
                        "type": "string",
                    },
                    "birth_year": {
                        "description": "Ano de nascimento quando apenas o ano foi informado.",
                        "type": "integer",
                    },
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Cria retorno/consulta na agenda para o paciente em foco. Uso exclusivo do nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "scheduled_at_iso": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_link": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["scheduled_at_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_patient_appointment",
            "description": "Cria um compromisso real na agenda do paciente para o nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "nutritionist_id": {"type": "string"},
                    "title": {"type": "string"},
                    "type": {"type": "string"},
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_link": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "type", "date", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_training_plan",
            "description": (
                "Cria e cadastra um plano de treino real para o paciente em foco. "
                "Use quando o usuario pedir para montar/salvar/cadastrar treino. "
                "Converta qualquer tabela em JSON estruturado com dias e exercicios; "
                "nunca envie markdown bruto ou texto unico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "restrictions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "observations": {"type": "string"},
                    "suggested_observation": {
                        "description": "Observacao extra a sugerir para confirmacao posterior, se fizer sentido.",
                        "type": "string",
                    },
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "focus": {"type": "string"},
                                "exercises": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "muscle_group": {"type": "string"},
                                            "exercise_name": {"type": "string"},
                                            "sets": {"type": "integer"},
                                            "reps": {"type": "string"},
                                            "rest": {"type": "string"},
                                            "load_guidance": {"type": "string"},
                                            "notes": {"type": "string"},
                                        },
                                        "required": ["exercise_name"],
                                    },
                                },
                            },
                            "required": ["name", "exercises"],
                        },
                    },
                },
                "required": ["title", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_workout_observation",
            "description": (
                "Adiciona uma observacao estruturada a um plano de treino existente, "
                "geralmente apos confirmacao curta de uma pending_action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "training_plan_id": {"type": "string"},
                    "observation": {"type": "string"},
                },
                "required": ["training_plan_id", "observation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Registra uma acao critica que precisa de confirmacao humana antes de executar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_description": {"type": "string"},
                    "pending_action": {
                        "description": "Nome da ferramenta real que sera executada apos confirmacao.",
                        "type": "string",
                    },
                    "pending_payload": {
                        "description": "Argumentos completos para executar a ferramenta real apos confirmacao.",
                        "type": "object",
                    },
                    "question": {"type": "string"},
                    "risk": {"type": "string"},
                    "target_entity": {"type": "string"},
                },
                "required": ["action_description", "pending_action", "pending_payload", "question"],
            },
        },
    },
]
