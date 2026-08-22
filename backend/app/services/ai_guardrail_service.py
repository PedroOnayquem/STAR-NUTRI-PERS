from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal


GuardrailAction = Literal["allow", "block", "safe_complete"]


@dataclass(frozen=True)
class GuardrailDecision:
    intent: str
    category: str
    action: GuardrailAction = "allow"
    response: str | None = None
    severity: str = "info"
    rule_ids: tuple[str, ...] = ()
    reason: str | None = None

    @property
    def blocked(self) -> bool:
        return self.action in {"block", "safe_complete"}

    @property
    def should_log(self) -> bool:
        return self.blocked or self.severity in {"warning", "high", "critical"}


@dataclass(frozen=True)
class OutputValidation:
    content: str
    allowed: bool
    category: str = "allowed"
    severity: str = "info"
    rule_ids: tuple[str, ...] = ()
    reason: str | None = None


PROMPT_INJECTION_PATTERNS = (
    r"\b(?:ignore|ignora|ignorem|desconsidere|esqueca|esque[cç]a|forget|disregard)\b.{0,100}\b(?:instru[cç][oõ]es|regras|prompt|sistema|anteriores|previous|system)\b",
    r"\b(?:agora voce e|you are now|modo desenvolvedor|developer mode|jailbreak|dan mode)\b",
    r"\b(?:finja|simule|pretenda)\b.{0,80}\b(?:sem regras|sem restri[cç][oõ]es|administrador|sistema)\b",
    r"(?:<\|(?:system|developer|assistant)\|>|\[/?(?:system|developer)\]|###\s*(?:system|developer))",
)

PROMPT_EXTRACTION_PATTERNS = (
    r"\b(?:mostre|revele|exiba|imprima|repita|copie|transcreva|retorne|show|reveal|print|repeat)\b.{0,100}\b(?:prompt|instru[cç][oõ]es internas|mensagem de sistema|system message|developer message)\b",
    r"\b(?:qual|quais|what)\b.{0,80}\b(?:seu prompt|prompt interno|system prompt|instru[cç][oõ]es de sistema)\b",
)

UNAUTHORIZED_DATA_PATTERNS = (
    r"\b(?:outro|outros|outra|outras)\s+pacientes?\b",
    r"\b(?:todos|lista de)\s+(?:os\s+)?pacientes?\b",
    r"\bdados?\s+(?:dos?|das?)\s+(?:outros?|outras?)\b",
    r"\bprontu[aá]rios?\s+(?:dos?|das?)\b",
)

INTERNAL_SYSTEM_PATTERNS = (
    r"\b(?:service[_ -]?role|openai[_ -]?api[_ -]?key|supabase[_ -]?key|chave secreta|api key|segredo interno)\b",
    r"\b(?:c[oó]digo fonte|vari[aá]veis de ambiente|logs internos|schema interno|credenciais)\b",
)

DANGEROUS_PATTERNS = (
    r"\b(?:me matar|suic[ií]dio|suicidar|autoles[aã]o|self[- ]?harm)\b",
    r"\b(?:parar de comer|ficar sem comer|vomitar depois|induzir v[oô]mito|laxante para emagrecer)\b",
    r"\b(?:dose letal|quantidade fatal|overdose)\b",
)

OUT_OF_SCOPE_PATTERNS = (
    r"\b(?:previs[aã]o do tempo|cotac[aã]o do d[oó]lar|placar do jogo|resultado da loteria)\b",
    r"\b(?:escreva|fa[cç]a|crie)\b.{0,40}\b(?:c[oó]digo|programa|script|contrato jur[ií]dico)\b",
)

NUTRITION_PATTERNS = (
    r"\b(?:nutri[cç][aã]o|dieta|alimenta[cç][aã]o|refei[cç][aã]o|alimento|calorias?|kcal|prote[ií]na|carboidrato|gordura|fibra|hidrata[cç][aã]o|taco)\b",
)

PATIENT_DATA_PATTERNS = (
    r"\b(?:paciente|prontu[aá]rio|exame|relat[oó]rio|arquivo|bioimped[aâ]ncia|peso|imc|m[eé]trica|condi[cç][aã]o|plano ativo)\b",
)

SECRET_OUTPUT_PATTERNS = (
    r"\b(?:OPENAI_API_KEY|SUPABASE_SERVICE_ROLE_KEY|service_role)\b",
    r"\bBearer\s+[A-Za-z0-9._~-]{20,}\b",
    r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    r"\b(?:system prompt|developer message|mensagem de sistema)\s*[:=]",
)

WRITE_SUCCESS_PATTERNS = (
    r"\b(?:cadastrei|registrei|salvei|atualizei|alterei|agendei|criei|removi|exclu[ií])\b",
)

PATIENT_WRITE_VERBS = (
    "adicionar",
    "adicione",
    "alterar",
    "altere",
    "apagar",
    "apague",
    "atualizar",
    "atualize",
    "cadastrar",
    "cadastre",
    "colocar",
    "coloque",
    "criar",
    "crie",
    "editar",
    "edite",
    "excluir",
    "exclua",
    "mudar",
    "mude",
    "registrar",
    "registre",
    "remover",
    "remova",
    "salvar",
    "salve",
    "substituir",
    "substitua",
    "trocar",
    "troque",
)
PATIENT_WRITE_TARGETS = (
    "dieta",
    "lesao",
    "medida",
    "observacao",
    "peso",
    "plano alimentar",
    "prontuario",
    "treino",
)
MUTATING_ACTION_TOOLS = {
    "add_food_to_meal",
    "add_observation",
    "add_taco_food_to_meal",
    "add_workout_observation",
    "create_appointment",
    "create_diet_plan",
    "create_patient_appointment",
    "create_training_plan",
    "register_injury",
    "register_progress",
    "register_weight_change",
    "update_patient_birth_date",
    "update_patient_profile",
    "update_diet_plan",
}

DOCUMENT_CLAIM_PATTERN = re.compile(
    r"\b(?:seu|o|no)\s+(?:exame|arquivo|relat[oó]rio|documento)\b.{0,80}\b(?:mostra|mostrou|indica|indicou|consta|apresenta)\b",
    re.IGNORECASE | re.DOTALL,
)

NUTRIENT_NUMBER_PATTERN = re.compile(
    r"\b\d+(?:[,.]\d+)?\s*kcal\b|"
    r"\b\d+(?:[,.]\d+)?\s*(?:kcal|g|mg)\b.{0,45}\b(?:prote[ií]na|carboidrato|gordura|fibra|por[cç][aã]o|100\s*g)\b|"
    r"\b(?:prote[ií]na|carboidrato|gordura|fibra|por[cç][aã]o|100\s*g)\b.{0,45}\b\d+(?:[,.]\d+)?\s*(?:kcal|g|mg)\b",
    re.IGNORECASE | re.DOTALL,
)

PATIENT_NUMBER_PATTERN = re.compile(
    r"\b(?:seu\s+)?(?:peso|imc|percentual de gordura|gordura corporal|massa muscular)\b[^\d]{0,25}(\d+(?:[,.]\d+)?)",
    re.IGNORECASE,
)

UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


class AiGuardrailService:
    """Deterministic security boundary around the existing AI orchestration.

    Authorization remains in SupabaseWorkspaceService. This service classifies
    untrusted text and validates what is allowed to cross the model boundary.
    It deliberately does not use the model to decide whether model access is safe.
    """

    def evaluate_context(
        self,
        *,
        actor: dict,
        chat_scope: str,
        context: dict,
        chat: dict,
    ) -> GuardrailDecision:
        role = actor.get("role")
        patient = context.get("patient") or {}
        nutritionist = context.get("nutritionist") or {}

        if chat_scope not in {"nutritionist", "patient"}:
            return self._context_block("Escopo de chat desconhecido.", "GR-CTX-001")
        if role != chat_scope:
            return self._context_block(
                "O papel autenticado nao corresponde ao escopo do chat.",
                "GR-AUTH-001",
            )
        if chat_scope == "patient":
            if not patient.get("id") or chat.get("patient_id") != patient.get("id"):
                return self._context_block(
                    "O chat pessoal nao pertence ao paciente autenticado.",
                    "GR-AUTH-002",
                )
        else:
            if not nutritionist.get("id") or chat.get("nutritionist_id") != nutritionist.get("id"):
                return self._context_block(
                    "O chat profissional nao pertence ao nutricionista autenticado.",
                    "GR-AUTH-003",
                )
            if patient and chat.get("patient_id") != patient.get("id"):
                return self._context_block(
                    "O paciente do contexto nao corresponde ao paciente do chat.",
                    "GR-AUTH-004",
                )

        return GuardrailDecision(intent="context_validation", category="allowed")

    def evaluate_input(
        self,
        message: str,
        *,
        actor: dict,
        chat_scope: str,
        context: dict,
    ) -> GuardrailDecision:
        normalized = _normalize(message)

        if _matches_any(normalized, PROMPT_EXTRACTION_PATTERNS):
            return GuardrailDecision(
                intent="prompt_extraction",
                category="prompt_extraction",
                action="block",
                response=(
                    "Não posso revelar prompts, instruções internas ou configurações do sistema. "
                    "Posso continuar ajudando com nutrição e com os dados autorizados deste atendimento."
                ),
                severity="high",
                rule_ids=("GR-INJ-002", "GR-PRIV-003"),
                reason="Tentativa de extrair instrucoes internas.",
            )

        injection_candidate = re.sub(
            r"\b(?:nao|nunca)\s+(?:ignore|desconsidere|esqueca)\b",
            "mantenha",
            normalized,
        )
        if _matches_any(injection_candidate, PROMPT_INJECTION_PATTERNS):
            return GuardrailDecision(
                intent="prompt_injection",
                category="prompt_injection",
                action="block",
                response=(
                    "Não posso ignorar as regras de segurança nem alterar meu nível de acesso. "
                    "Posso ajudar normalmente dentro do seu perfil e dos dados autorizados."
                ),
                severity="high",
                rule_ids=("GR-INJ-001",),
                reason="Instrucao para substituir ou ignorar regras do sistema.",
            )

        if actor.get("role") == "patient" and _is_patient_write_request(normalized):
            return GuardrailDecision(
                intent="patient_write_request",
                category="write_not_allowed",
                action="safe_complete",
                response=(
                    "Posso orientar e consultar os dados disponíveis para você, mas não posso "
                    "alterar informações persistidas pelo chat. Use a funcionalidade apropriada "
                    "do Star Nutri ou peça ao seu nutricionista para fazer essa alteração."
                ),
                severity="warning",
                rule_ids=("GR-AUTH-006",),
                reason="Paciente solicitou alteracao persistente pela IA.",
            )

        if _matches_any(normalized, INTERNAL_SYSTEM_PATTERNS):
            return GuardrailDecision(
                intent="internal_system_access",
                category="sensitive_internal_data",
                action="block",
                response=(
                    "Não posso fornecer credenciais, detalhes internos ou informações de segurança "
                    "do sistema. Posso ajudar com as funcionalidades disponíveis no Star Nutri."
                ),
                severity="critical",
                rule_ids=("GR-PRIV-001", "GR-SEC-001"),
                reason="Solicitacao de segredo ou detalhe interno.",
            )

        asks_for_other_patients = _matches_any(normalized, UNAUTHORIZED_DATA_PATTERNS)
        focused_patient = (context.get("patient") or {}).get("id")
        if asks_for_other_patients and (
            actor.get("role") == "patient" or (chat_scope == "nutritionist" and focused_patient)
        ):
            return GuardrailDecision(
                intent="unauthorized_patient_access",
                category="unauthorized_access",
                action="block",
                response=(
                    "Não posso acessar ou revelar dados de outros pacientes. "
                    "Posso ajudar apenas com os dados autorizados no contexto atual."
                ),
                severity="critical",
                rule_ids=("GR-AUTH-005", "GR-PRIV-001"),
                reason="Tentativa de acessar dados fora do escopo autorizado.",
            )

        if _matches_any(normalized, DANGEROUS_PATTERNS):
            return GuardrailDecision(
                intent="dangerous_health_request",
                category="dangerous_request",
                action="safe_complete",
                response=(
                    "Não posso orientar uma prática que coloque sua saúde em risco. "
                    "Se houver risco imediato, procure um serviço de emergência ou alguém de confiança agora. "
                    "Também posso ajudar a formular uma mensagem segura para seu nutricionista ou médico."
                ),
                severity="critical",
                rule_ids=("GR-SAFE-001",),
                reason="Pedido com risco relevante a saude.",
            )

        if _matches_any(normalized, OUT_OF_SCOPE_PATTERNS):
            return GuardrailDecision(
                intent="out_of_scope",
                category="out_of_scope",
                action="safe_complete",
                response=(
                    "Esse pedido está fora do escopo do assistente do Star Nutri. "
                    "Posso ajudar com nutrição, rotina, acompanhamento e dados autorizados do atendimento."
                ),
                severity="info",
                rule_ids=("GR-SCOPE-001",),
                reason="Solicitacao claramente fora do escopo do produto.",
            )

        if _matches_any(normalized, PATIENT_DATA_PATTERNS):
            return GuardrailDecision(intent="patient_data", category="patient_data")
        if _matches_any(normalized, NUTRITION_PATTERNS):
            return GuardrailDecision(intent="nutrition", category="nutrition")
        return GuardrailDecision(intent="normal", category="normal")

    def sanitize_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []
        for item in history:
            role = item.get("role")
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content") or "")[:4000]
            normalized = _normalize(content)
            unsafe = _matches_any(
                normalized,
                (*PROMPT_INJECTION_PATTERNS, *PROMPT_EXTRACTION_PATTERNS),
            )
            sanitized.append(
                {
                    "role": role,
                    "content": (
                        "[Mensagem anterior omitida pela camada de segurança.]"
                        if unsafe
                        else content
                    ),
                }
            )
        return sanitized

    def validate_output(
        self,
        content: str,
        *,
        actor: dict,
        context: dict,
        agent_actions: list[dict],
    ) -> OutputValidation:
        clean = content.strip()
        if not clean:
            return self._blocked_output(
                "A IA não produziu uma resposta válida. Tente novamente.",
                "empty_output",
                "GR-OUT-001",
                "Resposta vazia.",
            )

        if len(clean) > 24000:
            return self._blocked_output(
                "A resposta gerada excedeu o limite seguro. Reformule o pedido em partes menores.",
                "oversized_output",
                "GR-OUT-002",
                "Resposta acima do limite seguro.",
            )

        if _matches_any(clean, SECRET_OUTPUT_PATTERNS, normalize=False):
            return self._blocked_output(
                "Não posso exibir informações internas ou credenciais do sistema.",
                "sensitive_output",
                "GR-OUT-003",
                "A resposta continha um padrao de informacao interna.",
                severity="critical",
            )

        authorized_ids = {
            str(value)
            for value in (
                actor.get("id"),
                (context.get("patient") or {}).get("id"),
                (context.get("nutritionist") or {}).get("id"),
            )
            if value
        }
        foreign_ids = {match.group(0) for match in UUID_PATTERN.finditer(clean)} - authorized_ids
        if foreign_ids:
            return self._blocked_output(
                "A resposta foi retida porque continha identificadores não autorizados.",
                "unauthorized_identifier",
                "GR-OUT-004",
                "A resposta continha identificador fora do contexto.",
                severity="critical",
            )

        if actor.get("role") == "patient" and _matches_any(
            _normalize(clean), UNAUTHORIZED_DATA_PATTERNS
        ):
            return self._blocked_output(
                "Não posso fornecer informações sobre outros pacientes.",
                "cross_patient_output",
                "GR-OUT-005",
                "A resposta mencionava dados de outros pacientes.",
                severity="critical",
            )

        successful_actions = [
            action
            for action in agent_actions
            if action.get("success") is True
            and action.get("status") == "executed"
        ]
        successful_mutations = [
            action for action in successful_actions
            if action.get("tool") in MUTATING_ACTION_TOOLS
        ]
        if not successful_mutations and _matches_any(
            _normalize(clean), WRITE_SUCCESS_PATTERNS
        ):
            return self._blocked_output(
                "Nenhuma alteração foi executada no sistema. Posso tentar novamente com os dados necessários.",
                "unsupported_action_claim",
                "GR-OUT-006",
                "A resposta alegava uma acao sem execucao confirmada.",
                severity="high",
            )

        document_sources = self.document_sources(context)
        has_import_metrics = any(
            metric.get("source_import_id")
            for metric in context.get("variable_metrics", [])
            if isinstance(metric, dict)
        )
        if DOCUMENT_CLAIM_PATTERN.search(clean) and not (document_sources or has_import_metrics):
            return self._blocked_output(
                "Não encontrei um exame ou arquivo autorizado no contexto para sustentar essa afirmação.",
                "unsupported_document_claim",
                "GR-OUT-007",
                "A resposta atribuia informacao a arquivo inexistente no contexto.",
                severity="high",
            )

        grounded_numbers = self._grounded_numbers(context, successful_actions)
        for match in PATIENT_NUMBER_PATTERN.finditer(clean):
            value = _canonical_number(match.group(1))
            if value and value not in grounded_numbers:
                return self._blocked_output(
                    "Não posso afirmar esse valor como dado do paciente porque ele não está no contexto autorizado.",
                    "unsupported_patient_fact",
                    "GR-OUT-008",
                    "A resposta continha medida do paciente sem base no contexto.",
                    severity="high",
                )

        nutrient_matches = list(NUTRIENT_NUMBER_PATTERN.finditer(clean))
        if nutrient_matches:
            authoritative_nutrition_actions = [
                action
                for action in successful_actions
                if action.get("tool")
                in {
                    "add_taco_food_to_meal",
                    "calculate_taco_food_nutrients",
                    "compare_nutrition_evidence",
                    "get_taco_food",
                    "resolve_taco_nutrition",
                }
                and (action.get("result") or {}).get("resolution")
                not in {"ambiguous", "not_found", "missing_query"}
            ]
            nutrient_numbers = self._numbers_from(
                {
                    "diets": context.get("diets", []),
                    "actions": [
                        action.get("result")
                        for action in authoritative_nutrition_actions
                    ],
                }
            )
            nutrient_numbers.update(
                self._derived_nutrition_totals(authoritative_nutrition_actions)
            )
            claimed_numbers = {
                _canonical_number(value)
                for nutrient_match in nutrient_matches
                for value in re.findall(
                    r"\d+(?:[,.]\d+)?",
                    nutrient_match.group(0),
                )
                if _canonical_number(value) not in {"", "100"}
            }
            if claimed_numbers and not claimed_numbers.issubset(nutrient_numbers):
                return self._blocked_output(
                    "Para informar valores nutricionais exatos, preciso consultar uma fonte disponível, como a TACO.",
                    "unsupported_nutrition_fact",
                    "GR-OUT-009",
                    "A resposta continha valor nutricional exato sem fonte no contexto.",
                    severity="high",
                )
            if authoritative_nutrition_actions and "taco" not in _normalize(clean):
                return self._blocked_output(
                    "Os valores foram consultados na TACO, mas a resposta não identificou a fonte com clareza.",
                    "missing_nutrition_source",
                    "GR-OUT-010",
                    "A resposta omitiu a fonte TACO usada no calculo nutricional.",
                    severity="warning",
                )

        return OutputValidation(content=clean, allowed=True)

    def document_sources(self, context: dict, *, limit: int = 12) -> list[dict]:
        sources: list[dict] = []
        for item in (context.get("imports") or [])[:limit]:
            if not isinstance(item, dict) or item.get("status") == "failed":
                continue
            extracted = item.get("extracted_payload")
            if not isinstance(extracted, dict):
                extracted = {}
            sources.append(
                {
                    "id": item.get("id"),
                    "name": item.get("original_file_name"),
                    "type": item.get("file_type") or item.get("source_type"),
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                    "patient": extracted.get("patient") or {},
                    "metrics": extracted.get("metrics") or {},
                    "measurement": extracted.get("measurement") or {},
                    "warnings": (extracted.get("warnings") or [])[:8],
                    "confidence": item.get("confidence_payload") or extracted.get("confidence") or {},
                }
            )
        return sources

    def event_payload(
        self,
        *,
        actor: dict,
        chat: dict,
        chat_scope: str,
        context: dict,
        stage: str,
        category: str,
        action: str,
        severity: str,
        rule_ids: tuple[str, ...],
        reason: str | None,
        content: str | None = None,
        message_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        patient = context.get("patient") or {}
        nutritionist = context.get("nutritionist") or {}
        return {
            "actor_user_id": actor.get("id"),
            "actor_role": actor.get("role"),
            "patient_id": patient.get("id"),
            "nutritionist_id": nutritionist.get("id"),
            "chat_scope": chat_scope,
            "chat_id": chat.get("id"),
            "message_id": message_id,
            "stage": stage,
            "category": category,
            "action": action,
            "severity": severity,
            "rule_ids": list(rule_ids),
            "content_hash": self.content_hash(content) if content else None,
            # Avoid duplicating clinical/user content in security telemetry. The
            # hash is sufficient for correlation with the authorized message row.
            "redacted_excerpt": None,
            "reason": reason,
            "metadata": metadata or {},
        }

    @staticmethod
    def content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def redacted_excerpt(content: str, *, limit: int = 180) -> str:
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", content)
        value = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[cpf]", value)
        value = re.sub(r"\b(?:\+?55\s*)?\(?\d{2}\)?\s*\d{4,5}[-\s]?\d{4}\b", "[telefone]", value)
        value = UUID_PATTERN.sub("[id]", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value[:limit]

    def authorized_context_json(self, payload: Any) -> str:
        """Serialize authorized data with explicit boundaries for prompts."""
        return json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/")

    def _grounded_numbers(self, context: dict, actions: list[dict]) -> set[str]:
        return self._numbers_from(
            {
                "main_metrics": context.get("main_metrics", []),
                "variable_metrics": context.get("variable_metrics", []),
                "documents": self.document_sources(context),
                "actions": [action.get("result") for action in actions],
            }
        )

    def _derived_nutrition_totals(self, actions: list[dict]) -> set[str]:
        nutrient_keys = {
            "energy_kcal",
            "protein_g",
            "carbohydrate_g",
            "lipid_g",
            "fiber_g",
            "sodium_mg",
        }
        values_by_nutrient: dict[str, list[float]] = {
            key: [] for key in nutrient_keys
        }
        for action in actions:
            nutrients = (action.get("result") or {}).get("nutrients") or {}
            if not isinstance(nutrients, dict):
                continue
            for key in nutrient_keys:
                value = nutrients.get(key)
                if isinstance(value, int | float):
                    values_by_nutrient[key].append(float(value))

        return {
            _canonical_number(str(round(sum(values), 2)))
            for values in values_by_nutrient.values()
            if len(values) >= 2
        }

    def _numbers_from(self, payload: Any) -> set[str]:
        numbers: set[str] = set()

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)
            elif isinstance(value, int | float):
                numbers.add(_canonical_number(str(value)))
            elif isinstance(value, str) and re.fullmatch(r"-?\d+(?:[.,]\d+)?", value.strip()):
                numbers.add(_canonical_number(value))

        visit(payload)
        return {value for value in numbers if value}

    def _context_block(self, reason: str, rule_id: str) -> GuardrailDecision:
        return GuardrailDecision(
            intent="context_validation",
            category="unauthorized_context",
            action="block",
            response="Não foi possível validar o acesso a esta conversa.",
            severity="critical",
            rule_ids=(rule_id,),
            reason=reason,
        )

    def _blocked_output(
        self,
        safe_content: str,
        category: str,
        rule_id: str,
        reason: str,
        *,
        severity: str = "high",
    ) -> OutputValidation:
        return OutputValidation(
            content=safe_content,
            allowed=False,
            category=category,
            severity=severity,
            rule_ids=(rule_id,),
            reason=reason,
        )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_value.lower().split())


def _matches_any(value: str, patterns: tuple[str, ...], *, normalize: bool = False) -> bool:
    candidate = _normalize(value) if normalize else value
    return any(re.search(pattern, candidate, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _is_patient_write_request(value: str) -> bool:
    has_write_verb = any(re.search(rf"\b{re.escape(verb)}\b", value) for verb in PATIENT_WRITE_VERBS)
    has_target = any(target in value for target in PATIENT_WRITE_TARGETS)
    persist_phrase = bool(
        re.search(r"\b(?:na|no)\s+(?:aba|sistema|historico|prontuario)\b", value)
    )
    return has_write_verb and (has_target or persist_phrase)


def _canonical_number(value: str) -> str:
    try:
        number = float(value.strip().replace(",", "."))
    except (TypeError, ValueError):
        return ""
    return f"{number:.6f}".rstrip("0").rstrip(".")
