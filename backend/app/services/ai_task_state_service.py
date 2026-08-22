from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


ACTIVE_TASK_STATUSES = {
    "new",
    "understand",
    "needs_clarification",
    "waiting_user",
    "ready",
    "executing",
    "validating",
    "pending_confirmation",
    "completed",
}

TACO_TOOLS = {
    "resolve_taco_nutrition",
    "search_taco_foods",
    "get_taco_food",
    "calculate_taco_food_nutrients",
}

DOMAIN_TOOLS = {
    "nutrition": {
        "create_diet_plan",
        "update_diet_plan",
        "delete_diet_plan",
        "update_diet_meal",
        "delete_diet_meal",
        "add_food_to_meal",
        "add_taco_food_to_meal",
        *TACO_TOOLS,
    },
    "patients": {
        "search_patient_by_name",
        "get_patient_profile",
        "get_patient_summary",
        "update_patient_profile",
        "update_patient_birth_date",
    },
    "progress": {
        "get_patient_metrics",
        "register_weight_change",
        "register_progress",
    },
    "health": {
        "get_patient_conditions",
        "register_injury",
        "add_observation",
        "update_health_condition",
        "delete_health_condition",
    },
    "training": {
        "create_training_plan",
        "replace_training_plan",
        "update_workout",
        "delete_workout",
        "add_workout_exercise",
        "update_workout_exercise",
        "remove_workout_exercise",
        "add_workout_observation",
    },
    "scheduling": {
        "create_appointment",
        "create_patient_appointment",
    },
}

DOMAIN_PATTERNS = {
    "nutrition": (
        r"\b(taco|tako|tbca|tabela\s+(?:taco|tako)|alimentos?|calorias?|kcal|macros?|"
        r"proteinas?|carboidratos?|gorduras?|fibras?|sodio|dietas?|refeicoes?|cardapio)\b|"
        r"\b(analisando|avaliando)\b.*\b(cozid[oa]|cru[as]?|alimento|refeicao)\b"
    ),
    "patients": (
        r"\b(paciente|cadastro|perfil|data\s+de\s+nascimento|nascimento|idade)\b|"
        r"\b(atualize|altere|corrija)\b.*\b(objetivo|nascimento|perfil)\b"
    ),
    "progress": (
        r"\b(peso|pesagem|medida|metrica|progresso|evolucao|cintura|quadril|imc)\b"
    ),
    "health": (
        r"\b(lesao|lesoes|dor|alergia|restricao|condicao\s+clinica|prontuario)\b"
    ),
    "training": (
        r"\b(treino|treinos|exercicio|exercicios|musculacao|serie|repeticao)\b"
    ),
    "scheduling": (
        r"\b(agendar|agendamento|agenda|consulta\s+(?:para|com|em)|horario|retorno)\b"
    ),
}

CONTINUATION_PATTERN = re.compile(
    r"^(?:sim|nao|cozido|cozida|cru|crua|esse|essa|isso|o\s+primeiro|a\s+primeira|"
    r"pode|faca|faz|consulte|consultar|continue|continuar|pode\s+consultar|"
    r"faca\s+a\s+consulta|faz\s+a\s+consulta|faca\s+a\s+consulta\s+e\s+me\s+de\s+a\s+resposta|"
    r"\d+(?:[.,]\d+)?\s*(?:g|gramas?|kg|ml|unidades?))$"
)


@dataclass(frozen=True, slots=True)
class ActiveTask:
    domain: str
    intent: str
    slots: dict[str, Any]
    required_slots: list[str]
    missing_slots: list[str]
    ambiguous_slots: list[str]
    allowed_tools: set[str]
    status: str
    evidence: dict[str, Any]
    context_entities: dict[str, Any]
    state_id: str | None = None

    @property
    def is_ready(self) -> bool:
        return not self.missing_slots and not self.ambiguous_slots


class AiTaskStateService:
    """Deterministic task continuity and tool-domain policy.

    The model may propose arguments, but it cannot erase persisted slots or
    escape the active task's domain. This class contains no process-global or
    user-specific state; every task is reconstructed from one conversation row.
    """

    def from_state(self, state: dict | None) -> ActiveTask | None:
        if not state:
            return None
        domain = str(state.get("task_domain") or "")
        intent = str(state.get("task_intent") or "")
        status = str(state.get("task_status") or "")
        if not domain or not intent or status not in ACTIVE_TASK_STATUSES:
            return None
        return ActiveTask(
            domain=domain,
            intent=intent,
            slots=dict(state.get("task_slots") or {}),
            required_slots=list(state.get("required_slots") or []),
            missing_slots=list(state.get("missing_slots") or []),
            ambiguous_slots=list(state.get("ambiguous_slots") or []),
            allowed_tools=set(state.get("allowed_tools") or DOMAIN_TOOLS.get(domain, set())),
            status=status,
            evidence=dict(state.get("task_evidence") or {}),
            context_entities=dict(state.get("context_entities") or {}),
            state_id=state.get("id"),
        )

    def prepare_turn(
        self,
        *,
        state: dict | None,
        user_message: str,
    ) -> ActiveTask | None:
        active = self.from_state(state)
        detected_domain = self.detect_domain(user_message)
        if (
            active
            and active.status == "completed"
            and not self.should_continue_completed(
                active=active,
                detected_domain=detected_domain,
                user_message=user_message,
            )
        ):
            active = None
        if active and not self.is_explicit_switch(
            active=active,
            detected_domain=detected_domain,
            user_message=user_message,
        ):
            if (
                active.domain == "nutrition"
                and active.intent != "taco_nutrition_lookup"
                and self.is_taco_lookup(user_message)
            ):
                slots = {
                    **active.slots,
                    **self.extract_taco_slots(user_message, continuation=True),
                }
                slots.setdefault("source", "TACO")
                required = ["food_name", "quantity_g", "source", "requested_nutrients"]
                missing = self._missing(required, slots)
                return ActiveTask(
                    domain="nutrition",
                    intent="taco_nutrition_lookup",
                    slots=slots,
                    required_slots=required,
                    missing_slots=missing,
                    ambiguous_slots=[],
                    allowed_tools=set(TACO_TOOLS),
                    status="ready" if not missing else "needs_clarification",
                    evidence=dict(active.evidence),
                    context_entities=dict(active.context_entities),
                    state_id=active.state_id,
                )
            return self.merge_user_message(active, user_message)
        return self.new_task(user_message, detected_domain=detected_domain)

    def new_task(
        self,
        user_message: str,
        *,
        detected_domain: str | None = None,
    ) -> ActiveTask | None:
        detected_domains = self.detect_domains(user_message)
        if len(detected_domains) > 1:
            return ActiveTask(
                domain="composite",
                intent="multi_domain_task",
                slots={},
                required_slots=[],
                missing_slots=[],
                ambiguous_slots=[],
                allowed_tools=set().union(
                    *(DOMAIN_TOOLS[domain] for domain in detected_domains)
                ),
                status="understand",
                evidence={},
                context_entities={},
            )
        domain = detected_domain or self.detect_domain(user_message)
        if not domain:
            return None

        if domain == "nutrition" and self.is_taco_lookup(user_message):
            slots = self.extract_taco_slots(user_message)
            slots.setdefault("source", "TACO")
            required = ["food_name", "quantity_g", "source", "requested_nutrients"]
            missing = self._missing(required, slots)
            return ActiveTask(
                domain="nutrition",
                intent="taco_nutrition_lookup",
                slots=slots,
                required_slots=required,
                missing_slots=missing,
                ambiguous_slots=[],
                allowed_tools=set(TACO_TOOLS),
                status="ready" if not missing else "needs_clarification",
                evidence={},
                context_entities={},
            )

        initial_slots = self.extract_taco_slots(user_message)
        return ActiveTask(
            domain=domain,
            intent=f"{domain}_task",
            slots=initial_slots if domain == "nutrition" else {},
            required_slots=[],
            missing_slots=[],
            ambiguous_slots=[],
            allowed_tools=set(DOMAIN_TOOLS.get(domain, set())),
            status="understand",
            evidence={},
            context_entities={},
        )

    def merge_user_message(self, active: ActiveTask, user_message: str) -> ActiveTask:
        if active.intent != "taco_nutrition_lookup":
            return active

        slots = dict(active.slots)
        updates = self.extract_taco_slots(user_message, continuation=True)
        previous_food = _normalize(slots.get("food_name"))
        updated_food = _normalize(updates.get("food_name"))
        if updated_food and previous_food and updated_food != previous_food:
            slots.pop("food_id", None)
            slots.pop("candidates", None)
            if "preparation" not in updates:
                slots.pop("preparation", None)
        slots.update({key: value for key, value in updates.items() if value not in (None, "", [])})

        preparation = updates.get("preparation")
        candidates = slots.get("candidates") if isinstance(slots.get("candidates"), list) else []
        if preparation and candidates:
            matching = [
                candidate
                for candidate in candidates
                if preparation in _normalize(candidate.get("name"))
            ]
            if len(matching) == 1:
                slots["food_id"] = matching[0].get("id")
                slots["food_name"] = matching[0].get("name")
                slots.pop("candidates", None)

        if preparation and slots.get("food_name") and not slots.get("food_id"):
            food_name = str(slots["food_name"])
            if preparation not in _normalize(food_name):
                slots["food_name"] = f"{food_name} {preparation}".strip()

        ambiguous = list(active.ambiguous_slots)
        if preparation or slots.get("food_id"):
            ambiguous = [slot for slot in ambiguous if slot not in {"preparation", "food_variant"}]
        missing = self._missing(active.required_slots, slots)
        return ActiveTask(
            domain=active.domain,
            intent=active.intent,
            slots=slots,
            required_slots=list(active.required_slots),
            missing_slots=missing,
            ambiguous_slots=ambiguous,
            allowed_tools=set(active.allowed_tools),
            status="ready" if not missing and not ambiguous else "waiting_user",
            evidence=dict(active.evidence),
            context_entities=dict(active.context_entities),
            state_id=active.state_id,
        )

    def merge_tool_arguments(
        self,
        active: ActiveTask | None,
        *,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        if not active or tool_name not in active.allowed_tools:
            return dict(arguments)
        persisted = {
            key: value
            for key, value in active.slots.items()
            if key not in {"candidates", "preparation"}
        }
        return {**persisted, **arguments}

    def from_action(self, active: ActiveTask, action: dict) -> ActiveTask:
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
        slots = {**active.slots, **arguments}
        evidence = dict(active.evidence)
        context_entities = dict(active.context_entities)
        ambiguous = list(active.ambiguous_slots)
        status = str(action.get("status") or "failed")

        if result.get("requires_clarification") or result.get("resolution") == "ambiguous":
            candidates = result.get("candidates")
            if isinstance(candidates, list):
                slots["candidates"] = candidates
            ambiguous = ["food_variant"] if active.intent == "taco_nutrition_lookup" else ["entity"]
            status = "waiting_user"
        elif action.get("success"):
            status = "validating"
            ambiguous = []
            evidence = self._merge_evidence(evidence, action)
            food = result.get("food") if isinstance(result.get("food"), dict) else {}
            if food.get("id"):
                slots["food_id"] = food["id"]
            if food.get("name"):
                slots["food_name"] = food["name"]
            patient_id = arguments.get("patient_id") or result.get("patient_id")
            if not patient_id and action.get("entity") == "patient":
                patient_id = result.get("entity_id")
            if patient_id:
                context_entities["patient_id"] = patient_id
        elif action.get("error_code") == "entity_not_found":
            status = "failed"
        elif action.get("status") == "blocked":
            status = "blocked"
        else:
            status = "waiting_user"

        missing = self._missing(active.required_slots, slots)
        return ActiveTask(
            domain=active.domain,
            intent=active.intent,
            slots=slots,
            required_slots=list(active.required_slots),
            missing_slots=missing,
            ambiguous_slots=ambiguous,
            allowed_tools=set(active.allowed_tools),
            status=status,
            evidence=evidence,
            context_entities=context_entities,
            state_id=active.state_id,
        )

    def payload(
        self,
        active: ActiveTask,
        *,
        conversation_id: str,
        user_id: str,
        patient_id: str | None,
        last_message_id: str,
        expires_at: str,
        status: str | None = None,
    ) -> dict:
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "patient_id": patient_id,
            "state_kind": "task",
            "pending_action": None,
            "pending_payload": {},
            "task_domain": active.domain,
            "task_intent": active.intent,
            "task_status": status or active.status,
            "task_slots": active.slots,
            "required_slots": active.required_slots,
            "missing_slots": active.missing_slots,
            "ambiguous_slots": active.ambiguous_slots,
            "allowed_tools": sorted(active.allowed_tools),
            "task_evidence": active.evidence,
            "context_entities": active.context_entities,
            "last_message_id": last_message_id,
            "expires_at": expires_at,
        }

    def detect_domain(self, user_message: str) -> str | None:
        matches = self.detect_domains(user_message)
        if not matches:
            return None
        priority = ["patients", "progress", "health", "training", "scheduling", "nutrition"]
        return next(domain for domain in priority if domain in matches)

    def detect_domains(self, user_message: str) -> list[str]:
        normalized = _normalize(user_message)
        return [
            domain
            for domain, pattern in DOMAIN_PATTERNS.items()
            if re.search(pattern, normalized)
        ]

    def is_explicit_switch(
        self,
        *,
        active: ActiveTask,
        detected_domain: str | None,
        user_message: str,
    ) -> bool:
        if not detected_domain or detected_domain == active.domain:
            return False
        normalized = _normalize(user_message)
        if self.is_continuation(user_message):
            return False
        return bool(
            re.search(r"\b(agora|mudando|outro assunto|procure|busque|cadastre|registre|crie|atualize|exclua)\b", normalized)
            or len(normalized.split()) >= 4
        )

    def is_continuation(self, user_message: str) -> bool:
        normalized = " ".join(_normalize(user_message).split())
        return bool(CONTINUATION_PATTERN.fullmatch(normalized)) or len(normalized.split()) <= 2

    def is_referential_followup(self, user_message: str) -> bool:
        normalized = " ".join(_normalize(user_message).split())
        return self.is_continuation(user_message) or bool(
            re.search(
                r"^(?:e\b|agora\b.*\b(?:isso|ele|ela|esse|essa|mesmo|mesma)\b)|"
                r"\b(?:dele|dela|disso|desse|dessa|mesmo paciente|mesma paciente|"
                r"esse alimento|essa comida|esse treino|esse plano|o anterior|a anterior|"
                r"qual deles|qual delas|qual tem mais|qual teve mais|quanto teria)\b",
                normalized,
            )
        )

    def should_continue_completed(
        self,
        *,
        active: ActiveTask,
        detected_domain: str | None,
        user_message: str,
    ) -> bool:
        if self.is_referential_followup(user_message):
            return detected_domain in {None, active.domain}
        return False

    def is_comparison_request(self, user_message: str) -> bool:
        normalized = _normalize(user_message)
        return bool(
            re.search(
                r"\b(qual|quais|compare|comparar|comparacao)\b.*\b(mais|menos|maior|menor)\b",
                normalized,
            )
        )

    def is_taco_lookup(self, user_message: str) -> bool:
        normalized = _normalize(user_message)
        source = bool(re.search(r"\b(ta[ck]o|tbca|tabela)\b", normalized))
        nutrient = bool(re.search(r"\b(caloria|calorias|kcal|macro|nutriente|proteina|carboidrato|gordura|fibra|sodio)\b|\bquanto\s+tem\b", normalized))
        return source or nutrient

    def extract_taco_slots(self, user_message: str, *, continuation: bool = False) -> dict[str, Any]:
        normalized = _normalize(user_message)
        slots: dict[str, Any] = {}

        quantity = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(g|gramas?|kg)\b", normalized)
        if quantity:
            value = float(quantity.group(1).replace(",", "."))
            if quantity.group(2) == "kg":
                value *= 1000
            slots["quantity_g"] = value
            slots["unit"] = "g"

        preparation_match = re.search(
            r"\b(cozid[oa]s?|cru[as]?|assad[oa]s?|frit[oa]s?|grelhad[oa]s?|refogad[oa]s?)\b",
            normalized,
        )
        if preparation_match:
            preparation = preparation_match.group(1)
            if preparation.startswith("cozid"):
                preparation = "cozido"
            elif preparation.startswith("cru"):
                preparation = "cru"
            slots["preparation"] = preparation

        nutrients = []
        if re.search(r"\b(caloria|calorias|kcal|energia)\b", normalized):
            nutrients.append("energy_kcal")
        elif re.search(r"\bquanto\s+tem\b", normalized):
            nutrients.append("energy_kcal")
        if re.search(r"\b(proteina|proteinas)\b", normalized):
            nutrients.append("protein_g")
        if re.search(r"\b(carboidrato|carboidratos)\b", normalized):
            nutrients.append("carbohydrate_g")
        if re.search(r"\b(gordura|gorduras|lipidio|lipidios)\b", normalized):
            nutrients.append("lipid_g")
        if re.search(r"\b(fibra|fibras)\b", normalized):
            nutrients.append("fiber_g")
        if re.search(r"\b(sodio)\b", normalized):
            nutrients.append("sodium_mg")
        if nutrients:
            slots["requested_nutrients"] = nutrients

        if re.search(r"\b(ta[ck]o|tabela\s+brasileira\s+de\s+composicao|tebela\s+ta[ck]o)\b", normalized):
            slots["source"] = "TACO"
        elif re.search(r"\btbca\b", normalized):
            slots["source"] = "TBCA"

        if not continuation or len(normalized.split()) > 3:
            food_match = re.search(
                r"\b(?:de|do|da)\s+(?:\d+(?:[.,]\d+)?\s*(?:g|gramas?|kg)\s+de\s+)?(.+?)(?:\s+segundo|\s+(?:na|pela)\s+(?:tebela|tabela)|[?.!]|$)",
                normalized,
            )
            if not food_match:
                food_match = re.search(
                    r"\b(?:trocar|substituir|mudar)\s+(?:isso\s+)?(?:por|para)\s+(.+?)(?:[?.!]|$)",
                    normalized,
                )
            if food_match:
                food_name = food_match.group(1).strip()
                food_name = re.sub(r"\b(?:ta[ck]o|tbca)\b.*$", "", food_name).strip()
                if food_name:
                    slots["food_name"] = food_name
            elif re.search(r"\b(analisando|avaliando)\b", normalized):
                context_food = re.search(
                    r"\b(?:analisando|avaliando)\s+(.+?)(?:[?.!]|$)",
                    normalized,
                )
                if context_food:
                    slots["food_name"] = context_food.group(1).strip()

        return slots

    def _merge_evidence(self, evidence: dict[str, Any], action: dict) -> dict[str, Any]:
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        arguments = action.get("arguments") if isinstance(action.get("arguments"), dict) else {}
        item = {
            "source_type": "FACT_FROM_TOOL",
            "tool": action.get("tool") or action.get("operation"),
            "entity": action.get("entity"),
            "entity_id": action.get("entity_id"),
            "arguments": {
                key: arguments.get(key)
                for key in (
                    "food_id", "food_name", "patient_id", "patient_name",
                    "quantity_g", "requested_nutrients",
                )
                if arguments.get(key) not in (None, "", [])
            },
            "result": {
                key: result.get(key)
                for key in (
                    "food", "nutrients", "reference", "source", "resolution",
                    "summary", "patient_id", "entity_id",
                )
                if result.get(key) not in (None, "", [], {})
            },
        }
        items = list(evidence.get("items") or [])
        items.append(item)
        return {"items": items[-8:], "latest": item}

    def _missing(self, required: list[str], slots: dict[str, Any]) -> list[str]:
        return [slot for slot in required if slots.get(slot) in (None, "", [])]


def _normalize(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()
