from __future__ import annotations

import json
import unicodedata
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from .openai_service import OpenAIChatService
from .supabase_workspace_service import SupabaseWorkspaceService


AUTO_TOOLS = {
    "add_food_to_meal",
    "add_observation",
    "create_appointment",
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
        tools = [
            tool
            for tool in AGENT_TOOLS
            if tool["function"]["name"] in allowed_tools
        ]

        try:
            decision = await self.ai_service.complete_with_tools(
                system_prompt=self._build_tool_prompt(chat_scope, context, profile),
                history=history,
                reasoning_level=reasoning_level,
                tools=tools,
                user_message=user_message,
            )
        except Exception:
            return []

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
        now = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
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
            "metricas_recentes": context.get("variable_metrics", [])[:8],
        }

        return (
            "Você é o orquestrador de tools do agente Star Nutri.\n"
            "Sua tarefa é decidir se a mensagem exige ações reais no sistema.\n"
            "Chame tools somente quando houver intenção clara, entidade suficiente e baixo risco.\n"
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
                message=message,
                status="skipped",
                tool_name=tool_name,
            )

        try:
            if tool_name == "request_confirmation":
                return await self._record_action(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
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
                    message=message,
                )
            if tool_name == "register_weight_change":
                return await self._register_weight_change(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    message=message,
                )
            if tool_name == "register_progress":
                return await self._register_progress(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    message=message,
                )
            if tool_name == "add_observation":
                return await self._add_observation(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    message=message,
                )
            if tool_name == "add_food_to_meal":
                return await self._add_food_to_meal(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
                    message=message,
                )
            if tool_name == "create_appointment":
                return await self._create_appointment(
                    actor=actor,
                    arguments=arguments,
                    chat=chat,
                    chat_scope=chat_scope,
                    context=context,
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
        message: dict,
    ) -> dict:
        patient_id = self._patient_id(context)
        body_part = str(arguments.get("body_part") or "").strip()
        description = str(arguments.get("description") or "").strip()
        severity = _optional_text(arguments.get("severity"))
        if not body_part or not description:
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

        title = f"Lesao em {body_part}"[:120]
        duplicate = await self.workspace.find_similar_health_condition(
            patient_id=patient_id,
            condition_type="injury",
            title=title,
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
            description=description,
            severity=severity,
        )
        return await self._record_action(
            actor=actor,
            after_state=created,
            arguments=arguments,
            chat=chat,
            chat_scope=chat_scope,
            context=context,
            message=message,
            result={"label": "Lesao registrada", "summary": title},
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
        requires_confirmation: bool = False,
        result: dict | None = None,
    ) -> dict:
        log = await self.workspace.insert_ai_action_log(
            {
                "actor_user_id": actor["id"],
                "actor_role": actor["role"],
                "patient_id": self._patient_id(context),
                "nutritionist_id": (context.get("nutritionist") or {}).get("id"),
                "chat_scope": chat_scope,
                "chat_id": chat["id"],
                "message_id": message["id"],
                "tool_name": tool_name,
                "status": status,
                "requires_confirmation": requires_confirmation,
                "input": arguments,
                "result": result or {},
                "before_state": before_state,
                "after_state": after_state,
                "error": error,
            }
        )
        return {
            "error": error,
            "label": (result or {}).get("label") or tool_name,
            "log_id": log["id"],
            "requires_confirmation": requires_confirmation,
            "status": status,
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


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "register_injury",
            "description": "Registra uma lesao, dor localizada ou problema fisico como condicao do paciente em foco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "body_part": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
                "required": ["body_part", "description"],
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
