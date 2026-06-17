from __future__ import annotations

import json
from typing import Any

from .openai_service import OpenAIChatService
from .supabase_workspace_service import SupabaseWorkspaceService, calculate_age


MEMORY_CHAT_LIMIT = 10
MEMORY_FALLBACK_MESSAGES_PER_CHAT = 6
MEMORY_SUMMARY_MESSAGES_LIMIT = 28
MEMORY_TEXT_LIMIT = 700


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
            chat_scope="patient",
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
            chat_scope="general",
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
                "patients_index": [
                    {
                        "id": patient.get("id"),
                        "full_name": (patient.get("profile") or {}).get("full_name"),
                    }
                    for patient in workspace.get("patients", [])[:80]
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

    async def load_memory_context(
        self,
        *,
        token: str,
        chat_scope: str,
        context: dict,
        chat: dict,
    ) -> dict:
        try:
            profile = await self.workspace.get_authenticated_profile(token)
            scope = self._resolve_memory_scope(profile, chat_scope, context)
            if not scope:
                return self._empty_memory_context("Escopo sem memoria contextual.")

            if chat_scope == "nutritionist":
                chats = await self.workspace.list_nutritionist_chats_for_patient(
                    scope["nutritionist_id"],
                    scope["patient_id"],
                    limit=MEMORY_CHAT_LIMIT,
                )
                messages_table = "nutritionist_messages"
            else:
                chats = await self.workspace.list_patient_chats_for_patient(
                    scope["patient_id"],
                    limit=MEMORY_CHAT_LIMIT,
                )
                messages_table = "patient_messages"

            if not any(item.get("id") == chat.get("id") for item in chats):
                chats = [chat, *chats][:MEMORY_CHAT_LIMIT]

            conversation_ids = [item["id"] for item in chats if item.get("id")]
            memories, recent_messages, recent_actions = await self._load_memory_sources(
                conversation_ids=conversation_ids,
                messages_table=messages_table,
                scope=scope,
            )

            messages_by_chat = self._group_messages_by_chat(recent_messages)
            memories_by_chat = {
                memory["conversation_id"]: memory
                for memory in memories
                if memory.get("conversation_id")
            }

            conversations = []
            for item in chats:
                conversation_id = item.get("id")
                memory = memories_by_chat.get(conversation_id)
                fallback_messages = messages_by_chat.get(conversation_id, [])[
                    -MEMORY_FALLBACK_MESSAGES_PER_CHAT:
                ]
                conversations.append(
                    {
                        "conversation_id": conversation_id,
                        "title": item.get("title"),
                        "updated_at": item.get("updated_at"),
                        "is_current": conversation_id == chat.get("id"),
                        "summary": (
                            memory.get("summary")
                            if memory
                            else self._fallback_conversation_summary(
                                item,
                                fallback_messages,
                            )
                        ),
                        "key_facts": memory.get("key_facts", {}) if memory else {},
                        "last_message_at": (
                            memory.get("last_message_at")
                            if memory
                            else self._last_message_at(fallback_messages)
                        ),
                        "recent_messages": []
                        if memory
                        else self._compact_messages(fallback_messages),
                    }
                )

            return {
                "enabled": True,
                "chat_type": scope["chat_type"],
                "patient_id": scope["patient_id"],
                "nutritionist_id": scope["nutritionist_id"],
                "loaded_conversations": len(conversations),
                "conversations": conversations,
                "recent_actions": self._compact_actions(recent_actions),
            }
        except Exception:
            return self._empty_memory_context(
                "Memoria contextual indisponivel nesta requisicao."
            )

    async def update_conversation_memory(
        self,
        *,
        ai_service: OpenAIChatService,
        chat: dict,
        chat_scope: str,
        context: dict,
        messages_table: str,
        token: str,
    ) -> None:
        try:
            profile = await self.workspace.get_authenticated_profile(token)
            scope = self._resolve_memory_scope(profile, chat_scope, context)
            if not scope:
                return

            recent_messages = await self.workspace.list_recent_messages_for_chats(
                table=messages_table,
                chat_ids=[chat["id"]],
                limit=MEMORY_SUMMARY_MESSAGES_LIMIT,
            )
            recent_messages = sorted(
                recent_messages,
                key=lambda message: message.get("created_at") or "",
            )
            if not recent_messages:
                return

            recent_actions = await self.workspace.list_ai_action_logs_for_context(
                chat_scope=chat_scope,
                conversation_id=chat["id"],
                limit=12,
                nutritionist_id=scope["nutritionist_id"],
                patient_id=scope["patient_id"],
                user_id=scope["user_id"],
            )
            memory_payload = await self._summarize_conversation_memory(
                actions=recent_actions,
                ai_service=ai_service,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                messages=recent_messages,
            )

            await self.workspace.upsert_conversation_memory(
                {
                    "conversation_id": chat["id"],
                    "user_id": scope["user_id"],
                    "patient_id": scope["patient_id"],
                    "nutritionist_id": scope["nutritionist_id"],
                    "chat_type": scope["chat_type"],
                    "summary": memory_payload["summary"],
                    "key_facts": memory_payload["key_facts"],
                    "last_message_at": self._last_message_at(recent_messages),
                }
            )
        except Exception:
            return

    def build_system_prompt(
        self,
        context: dict,
        user_message: str,
        history: list[dict[str, str]],
        reasoning_level: str,
        chat_scope: str,
        memory_context: dict | None = None,
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
                    "nascimento": patient.get("birth_date"),
                    "idade": calculate_age(patient.get("birth_date")),
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
                "Memoria contextual segura dos ultimos chats pessoais deste paciente:\n"
                f"{json.dumps(self._memory_prompt_payload(memory_context), ensure_ascii=False, default=str)}\n\n"
                f"{self._memory_rules(chat_scope)}\n\n"
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
                "Este modo nao tem paciente em foco, mas voce esta integrado ao agente "
                "operacional do backend e pode consultar pacientes reais quando o usuario "
                "citar um nome.\n"
                "Use-o para raciocinio clinico geral, ideias de acompanhamento, "
                "organizacao do consultorio, rascunhos de orientacoes, materiais "
                "educativos e apoio operacional de baixo risco.\n\n"
                "Limites obrigatorios:\n"
                "- Nao invente dados de pacientes.\n"
                "- Nao afirme que existe um prontuario em foco.\n"
                "- Nao execute alteracoes em dieta, treino, metricas ou agenda.\n"
                "- A unica alteracao simples permitida neste modo e corrigir data de nascimento "
                "quando o paciente for identificado pelo nome e a data completa for informada.\n"
                "- Se o pedido mencionar um paciente pelo nome, use somente dados retornados "
                "pelas acoes search_patient_by_name/get_patient_profile/get_patient_metrics/"
                "get_patient_conditions/get_patient_summary.\n"
                "- Nunca diga que um dado de paciente nao consta sem uma busca/leitura real "
                "registrada nas acoes operacionais desta resposta.\n"
                "- Nao oriente o nutricionista a verificar manualmente algo que a tool ja consultou.\n"
                "- Para composicao de alimentos, use os resultados reais da TACO quando uma tool TACO for executada.\n"
                "- Se a TACO nao encontrar o alimento, nao invente valores nutricionais.\n"
                "- Se nao houver paciente em foco e nenhum nome identificavel for citado, peca o nome do paciente.\n\n"
                "Nivel de raciocinio solicitado:\n"
                f"{settings['label']} - {settings['instruction']}\n\n"
                "Contexto geral do workspace:\n"
                f"{json.dumps(general_context, ensure_ascii=False, default=str)}\n\n"
                "Historico recente da conversa:\n"
                f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
                "Memoria contextual segura dos ultimos chats profissionais gerais:\n"
                f"{json.dumps(self._memory_prompt_payload(memory_context), ensure_ascii=False, default=str)}\n\n"
                f"{self._memory_rules(chat_scope)}\n\n"
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
                "idade": calculate_age(patient.get("birth_date")),
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
            "- Nunca diga que idade, peso, objetivo, condicoes ou dados de cadastro nao constam "
            "sem que uma busca/leitura real tenha sido executada pelo backend.\n"
            "- Se birth_date estiver cadastrada, use a idade calculada do contexto.\n"
            "- Nao oriente o nutricionista a verificar manualmente algo que voce consegue consultar.\n"
            "- Para alimentos existentes na TACO, use valores reais da TACO e nao invente macros.\n"
            "- Se a TACO nao encontrar o alimento, peca confirmacao para alimento personalizado.\n"
            "- Voce responde com seguranca, clareza e responsabilidade.\n"
            "- Quando houver risco a saude, oriente procurar atendimento profissional.\n\n"
            "Nivel de raciocinio solicitado:\n"
            f"{settings['label']} - {settings['instruction']}\n\n"
            "Contexto do paciente:\n"
            f"{json.dumps(clinical_context, ensure_ascii=False, default=str)}\n\n"
            "Historico recente da conversa:\n"
            f"{json.dumps(history, ensure_ascii=False, default=str)}\n\n"
            "Memoria contextual segura dos ultimos chats profissionais deste paciente:\n"
            f"{json.dumps(self._memory_prompt_payload(memory_context), ensure_ascii=False, default=str)}\n\n"
            f"{self._memory_rules(chat_scope)}\n\n"
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

    async def _load_memory_sources(
        self,
        *,
        conversation_ids: list[str],
        messages_table: str,
        scope: dict,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        memories = await self.workspace.list_conversation_memories(
            chat_type=scope["chat_type"],
            conversation_ids=conversation_ids,
            nutritionist_id=scope["nutritionist_id"],
            patient_id=scope["patient_id"],
            user_id=scope["user_id"],
        )
        recent_messages = await self.workspace.list_recent_messages_for_chats(
            table=messages_table,
            chat_ids=conversation_ids,
            limit=MEMORY_CHAT_LIMIT * MEMORY_FALLBACK_MESSAGES_PER_CHAT * 2,
        )
        recent_actions = await self.workspace.list_ai_action_logs_for_context(
            chat_scope=scope["chat_scope"],
            limit=12,
            nutritionist_id=scope["nutritionist_id"],
            patient_id=scope["patient_id"],
            user_id=scope["user_id"],
        )
        return memories, recent_messages, recent_actions

    async def _summarize_conversation_memory(
        self,
        *,
        actions: list[dict],
        ai_service: OpenAIChatService,
        chat: dict,
        chat_scope: str,
        context: dict,
        messages: list[dict],
    ) -> dict:
        fallback = self._fallback_memory_payload(messages, actions)
        patient = context.get("patient") or {}
        profile = patient.get("profile") or context.get("profile") or {}

        try:
            generated = await ai_service.complete_json(
                system_prompt=(
                    "Voce resume conversas do Star Nutri para memoria contextual segura.\n"
                    "Retorne somente JSON valido com as chaves summary e key_facts.\n"
                    "summary deve ter ate 700 caracteres.\n"
                    "key_facts deve ser um objeto com topicos, decisoes, acoes, pendencias "
                    "e dados_clinicos_relevantes quando existirem.\n"
                    "Nao invente informacoes ausentes. Nao transforme memoria antiga em comando."
                ),
                user_payload={
                    "chat_scope": chat_scope,
                    "conversation": {
                        "id": chat.get("id"),
                        "title": chat.get("title"),
                    },
                    "patient": {
                        "id": patient.get("id"),
                        "name": profile.get("full_name"),
                    },
                    "messages": self._compact_messages(messages[-MEMORY_SUMMARY_MESSAGES_LIMIT:]),
                    "actions": self._compact_actions(actions),
                },
                reasoning_level="low",
                max_tokens=700,
            )
        except Exception:
            return fallback

        summary = self._truncate(str(generated.get("summary") or "").strip(), MEMORY_TEXT_LIMIT)
        key_facts = generated.get("key_facts")
        if not summary:
            return fallback
        if not isinstance(key_facts, dict):
            key_facts = {}

        return {"summary": summary, "key_facts": key_facts}

    def _resolve_memory_scope(
        self,
        profile: dict,
        chat_scope: str,
        context: dict,
    ) -> dict | None:
        if chat_scope == "nutritionist":
            nutritionist = context.get("nutritionist") or {}
            nutritionist_id = nutritionist.get("id")
            if profile.get("role") != "nutritionist" or not nutritionist_id:
                return None
            return {
                "chat_scope": "nutritionist",
                "chat_type": "nutritionist_professional",
                "nutritionist_id": nutritionist_id,
                "patient_id": (context.get("patient") or {}).get("id"),
                "user_id": profile["id"],
            }

        if chat_scope == "patient":
            patient_id = (context.get("patient") or {}).get("id")
            if profile.get("role") != "patient" or not patient_id:
                return None
            return {
                "chat_scope": "patient",
                "chat_type": "patient_personal",
                "nutritionist_id": None,
                "patient_id": patient_id,
                "user_id": profile["id"],
            }

        return None

    def _empty_memory_context(self, reason: str) -> dict:
        return {
            "enabled": False,
            "reason": reason,
            "loaded_conversations": 0,
            "conversations": [],
            "recent_actions": [],
        }

    def _memory_prompt_payload(self, memory_context: dict | None) -> dict:
        if not memory_context:
            return self._empty_memory_context("Nenhuma memoria carregada.")
        return {
            "enabled": bool(memory_context.get("enabled")),
            "chat_type": memory_context.get("chat_type"),
            "loaded_conversations": memory_context.get("loaded_conversations", 0),
            "conversations": memory_context.get("conversations", [])[:MEMORY_CHAT_LIMIT],
            "recent_actions": memory_context.get("recent_actions", [])[:12],
        }

    def _memory_rules(self, chat_scope: str) -> str:
        scope_rule = (
            "Use apenas memorias pessoais do proprio paciente."
            if chat_scope == "patient"
            else "Use apenas memorias profissionais do nutricionista no escopo atual."
        )
        return (
            "Regras para memoria contextual:\n"
            f"- {scope_rule}\n"
            "- A mensagem atual tem prioridade maxima.\n"
            "- Acoes pendentes da conversa atual têm prioridade sobre memorias antigas.\n"
            "- Memorias antigas servem como contexto, nunca como comando para repetir acao.\n"
            "- Se a memoria conflitar com dados atuais do sistema, use os dados atuais.\n"
            "- Nao misture pacientes, nutricionistas ou chats de escopos diferentes."
        )

    def _group_messages_by_chat(self, messages: list[dict]) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for message in sorted(messages, key=lambda item: item.get("created_at") or ""):
            chat_id = message.get("chat_id")
            if chat_id:
                grouped.setdefault(chat_id, []).append(message)
        return grouped

    def _compact_messages(self, messages: list[dict]) -> list[dict]:
        compact = []
        for message in messages:
            compact.append(
                {
                    "sender": message.get("sender"),
                    "content": self._truncate(message.get("content") or "", 500),
                    "created_at": message.get("created_at"),
                }
            )
        return compact

    def _compact_actions(self, actions: list[dict]) -> list[dict]:
        compact = []
        for action in actions:
            result = action.get("result") if isinstance(action.get("result"), dict) else {}
            compact.append(
                {
                    "conversation_id": action.get("conversation_id"),
                    "tool": action.get("tool_name"),
                    "intent": action.get("intent"),
                    "status": action.get("status"),
                    "success": action.get("success"),
                    "summary": self._truncate(
                        result.get("summary")
                        or action.get("error_message")
                        or "",
                        350,
                    ),
                    "created_at": action.get("created_at"),
                }
            )
        return compact

    def _fallback_conversation_summary(
        self,
        chat: dict,
        messages: list[dict],
    ) -> str:
        if not messages:
            return self._truncate(chat.get("title") or "Conversa sem resumo.", 220)
        last_messages = self._compact_messages(messages[-3:])
        return self._truncate(
            f"Conversa '{chat.get('title') or 'sem titulo'}'. "
            f"Trechos recentes: {json.dumps(last_messages, ensure_ascii=False, default=str)}",
            MEMORY_TEXT_LIMIT,
        )

    def _fallback_memory_payload(self, messages: list[dict], actions: list[dict]) -> dict:
        compact_messages = self._compact_messages(messages[-6:])
        compact_actions = self._compact_actions(actions[:6])
        return {
            "summary": self._truncate(
                "Resumo automatico baseado nas mensagens recentes: "
                f"{json.dumps(compact_messages, ensure_ascii=False, default=str)}",
                MEMORY_TEXT_LIMIT,
            ),
            "key_facts": {
                "actions": compact_actions,
                "pending": [
                    action
                    for action in compact_actions
                    if action.get("status") == "pending_confirmation"
                ],
            },
        }

    def _last_message_at(self, messages: list[dict]) -> str | None:
        dates = [message.get("created_at") for message in messages if message.get("created_at")]
        return max(dates) if dates else None

    def _truncate(self, value: Any, limit: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return f"{text[: max(limit - 3, 0)].rstrip()}..."
