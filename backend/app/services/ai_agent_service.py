from __future__ import annotations

import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .openai_service import OpenAIChatService
from .supabase_workspace_service import SupabaseWorkspaceService


AUTO_TOOLS = {
    "add_food_to_meal",
    "add_observation",
    "add_workout_observation",
    "create_appointment",
    "create_training_plan",
    "register_injury",
    "register_progress",
    "register_weight_change",
}

NUTRITIONIST_TOOLS = AUTO_TOOLS | {"request_confirmation"}
PATIENT_TOOLS = {
    "add_observation",
    "register_injury",
    "register_progress",
    "register_weight_change",
    "request_confirmation",
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
            return []

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
            "Use sempre o paciente em foco; não altere dados de outro paciente citado por engano.\n"
            "Não invente valores, horários, macros ou medidas ausentes.\n"
            "Ações de deletar, cancelar, remover, sobrescrever plano completo ou apagar dados "
            "devem usar request_confirmation, nunca execução direta.\n"
            "Se a mensagem for pergunta, conversa geral ou ambígua, não chame nenhuma tool.\n\n"
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
                        "label": "Confirmacao necessaria",
                        "summary": arguments.get("question")
                        or arguments.get("action_description")
                        or "A acao precisa de confirmacao antes de executar.",
                    },
                    status="pending_confirmation",
                    tool_name=tool_name,
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
            if tool_name == "create_appointment":
                return await self._create_appointment(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    intent=intent,
                    message=message,
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
        except Exception as exc:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error=str(exc),
                intent=intent,
                message=message,
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
                tool_name="create_appointment",
            )

        nutritionist = context.get("nutritionist") or {}
        scheduled_at = str(arguments.get("scheduled_at_iso") or "").strip()
        if not nutritionist.get("id") or not scheduled_at:
            return await self._record_action(
                actor=actor,
                arguments=arguments,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                error="Consulta sem nutricionista ou horario valido.",
                message=message,
                status="skipped",
                tool_name="create_appointment",
            )

        datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        duplicate = await self.workspace.find_appointment(
            nutritionist_id=nutritionist["id"],
            patient_id=self._patient_id(context),
            scheduled_at=scheduled_at,
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
                tool_name="create_appointment",
            )

        created = await self.workspace.create_appointment_record(
            nutritionist_id=nutritionist["id"],
            patient_id=self._patient_id(context),
            title=str(arguments.get("title") or "Retorno nutricional")[:160],
            scheduled_at=scheduled_at,
            created_by=actor["id"],
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
                "summary": f"{created.get('title')} em {created.get('scheduled_at')}",
            },
            status="executed",
            tool_name="create_appointment",
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
        log = await self.workspace.insert_ai_action_log(
            {
                "actor_user_id": actor["id"],
                "user_id": actor["id"],
                "actor_role": actor["role"],
                "patient_id": self._patient_id(context),
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
        )
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
        return context["patient"]["id"]

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
        return str(patient_id) != self._patient_id(context)

    def _classify_intent(self, user_message: str, *, has_pending_state: bool) -> str:
        normalized = _normalize(user_message)
        if _is_confirmation_message(normalized):
            return "confirm_pending_action" if has_pending_state else "answer_question"
        if _is_cancellation_message(normalized):
            return "cancel_pending_action" if has_pending_state else "answer_question"
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
        if not _is_confirmation_message(normalized):
            return None

        pending_action = pending_state.get("pending_action")
        payload = dict(pending_state.get("pending_payload") or {})
        payload["_state_id"] = pending_state["id"]
        payload["patient_id"] = pending_state.get("patient_id")

        if pending_action == "add_workout_observation":
            return "add_workout_observation", payload
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
            and "add_food_to_meal" in allowed_tools
        ):
            return "add_food_to_meal", food

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
                "cadastrar",
                "cadastre",
                "cancelar",
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
                "registrar",
                "registre",
                "remover",
                "reagendar",
                "salvar",
                "tabela",
                "treino",
                "treinos",
            )
        )

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
            "name": "create_appointment",
            "description": "Cria retorno/consulta na agenda para o paciente em foco. Uso exclusivo do nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "scheduled_at_iso": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["scheduled_at_iso"],
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
                    "question": {"type": "string"},
                    "risk": {"type": "string"},
                },
                "required": ["action_description", "question"],
            },
        },
    },
]
