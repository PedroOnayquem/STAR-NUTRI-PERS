import json
import logging
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...schemas.chat import CreateChatSessionRequest, SendChatMessageRequest
from ...core.config import settings
from ...services.ai_agent_service import AiAgentService
from ...services.ai_guardrail_service import AiGuardrailService, GuardrailDecision
from ...services.chat_context_service import ChatContextService
from ...services.openai_service import OpenAIChatService
from ...services.file_monitoring_service import FileMonitoringService
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/chat", tags=["chat"])
legacy_router = APIRouter(tags=["chat-legacy"])
logger = logging.getLogger(__name__)


@router.get("/sessions")
async def list_chat_sessions(
    patient_id: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    profile = await workspace.get_authenticated_profile(token)
    if profile["role"] == "nutritionist":
        return await list_nutritionist_chat_sessions(patient_id=patient_id, token=token)
    if profile["role"] == "patient":
        return await list_patient_chat_sessions(token)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem acesso ao chat.")


@router.get("/nutritionist/sessions")
async def list_nutritionist_chat_sessions(
    patient_id: str | None = None,
    chat_scope: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    try:
        workspace = SupabaseWorkspaceService()
        return await workspace.list_authorized_nutritionist_chats(
            token,
            patient_id,
            chat_scope=chat_scope,
        )
    except Exception as exc:
        _raise_session_error(exc)


@router.get("/patient/sessions")
async def list_patient_chat_sessions(
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    return await workspace.list_authorized_patient_chats(token)


@router.post("/sessions")
async def create_chat_session(
    payload: CreateChatSessionRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    workspace = SupabaseWorkspaceService()
    profile = await workspace.get_authenticated_profile(token)
    if profile["role"] == "nutritionist":
        return await create_nutritionist_chat_session(payload, token)
    if profile["role"] == "patient":
        return await create_patient_chat_session(payload, token)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem acesso ao chat.")


@router.post("/nutritionist/sessions")
async def create_nutritionist_chat_session(
    payload: CreateChatSessionRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    try:
        workspace = SupabaseWorkspaceService()
        return await workspace.create_authorized_nutritionist_chat(
            token,
            payload.patient_id,
            payload.title,
            chat_scope=payload.chat_scope,
        )
    except Exception as exc:
        _raise_session_error(exc)


@router.post("/patient/sessions")
async def create_patient_chat_session(
    payload: CreateChatSessionRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    workspace = SupabaseWorkspaceService()
    return await workspace.create_authorized_patient_chat(token, payload.title)


@router.get("/sessions/{session_id}/messages")
async def list_chat_messages(
    session_id: str,
    limit: int = 120,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    profile = await workspace.get_authenticated_profile(token)
    if profile["role"] == "nutritionist":
        return await list_nutritionist_chat_messages(
            session_id,
            limit,
            offset,
            token,
        )
    return await list_patient_chat_messages(session_id, limit, offset, token)


@router.get("/nutritionist/sessions/{session_id}/messages")
async def list_nutritionist_chat_messages(
    session_id: str,
    limit: int = 120,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    safe_limit = min(max(limit, 1), 300)
    safe_offset = max(offset, 0)
    return await workspace.list_authorized_nutritionist_messages(
        token,
        session_id,
        limit=safe_limit,
        offset=safe_offset,
    )


@router.get("/patient/sessions/{session_id}/messages")
async def list_patient_chat_messages(
    session_id: str,
    limit: int = 120,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    safe_limit = min(max(limit, 1), 300)
    safe_offset = max(offset, 0)
    return await workspace.list_authorized_patient_messages(
        token,
        session_id,
        limit=safe_limit,
        offset=safe_offset,
    )


@router.post("/send")
async def send_chat_message(
    payload: SendChatMessageRequest,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    workspace = SupabaseWorkspaceService()
    profile = await workspace.get_authenticated_profile(token)
    if profile["role"] == "nutritionist":
        return await send_nutritionist_chat_message(payload, token)
    if profile["role"] == "patient":
        return await send_patient_chat_message(payload, token)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem acesso ao chat.")


@router.post("/nutritionist/send")
async def send_nutritionist_chat_message(
    payload: SendChatMessageRequest,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    workspace = SupabaseWorkspaceService()
    context_service = ChatContextService(workspace)
    context, chat, sender = await context_service.resolve_nutritionist_context(
        token,
        payload.patient_id,
        payload.session_id,
    )
    return await _stream_chat_response(
        chats_table="nutritionist_chats",
        chat_scope="nutritionist",
        context=context,
        context_service=context_service,
        messages_table="nutritionist_messages",
        payload=payload,
        sender=sender,
        session=chat,
        token=token,
        workspace=workspace,
    )


@router.post("/patient/send")
async def send_patient_chat_message(
    payload: SendChatMessageRequest,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    workspace = SupabaseWorkspaceService()
    context_service = ChatContextService(workspace)
    context, chat, sender = await context_service.resolve_patient_context(
        token,
        payload.session_id,
    )
    return await _stream_chat_response(
        chats_table="patient_chats",
        chat_scope="patient",
        context=context,
        context_service=context_service,
        messages_table="patient_messages",
        payload=payload,
        sender=sender,
        session=chat,
        token=token,
        workspace=workspace,
    )


@legacy_router.get("/chats")
async def list_legacy_chat_sessions(
    patient_id: str | None = None,
    limit: int = 80,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    return await _list_legacy_chats(patient_id, limit, offset, token)


@legacy_router.get("/chats_limit={legacy_query:path}")
async def list_legacy_chat_sessions_from_broken_query(
    legacy_query: str,
    patient_id: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    limit, offset = _parse_legacy_limit_offset(legacy_query)
    return await _list_legacy_chats(patient_id, limit, offset, token)


@legacy_router.get("/chat_nutritionist/sessions")
async def list_legacy_nutritionist_sessions(
    patient_id: str | None = None,
    limit: int = 80,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    sessions = await list_nutritionist_chat_sessions(patient_id=patient_id, token=token)
    return sessions[offset : offset + limit]


@legacy_router.get("/chat_patient/sessions")
async def list_legacy_patient_sessions(
    limit: int = 80,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    sessions = await list_patient_chat_sessions(token)
    return sessions[offset : offset + limit]


@legacy_router.get("/chat_nutritionist/sessions/{session_id}/messages")
async def list_legacy_nutritionist_messages(
    session_id: str,
    limit: int = 120,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    return await list_nutritionist_chat_messages(session_id, limit, offset, token)


@legacy_router.get("/chat_patient/sessions/{session_id}/messages")
async def list_legacy_patient_messages(
    session_id: str,
    limit: int = 120,
    offset: int = 0,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    return await list_patient_chat_messages(session_id, limit, offset, token)


@legacy_router.post("/chat_nutritionist/send")
async def send_legacy_nutritionist_message(
    raw_payload: dict,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    return await send_nutritionist_chat_message(_normalize_legacy_payload(raw_payload), token)


@legacy_router.post("/chat_patient/send")
async def send_legacy_patient_message(
    raw_payload: dict,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    return await send_patient_chat_message(_normalize_legacy_payload(raw_payload), token)


async def _stream_chat_response(
    *,
    chats_table: str,
    chat_scope: str,
    context: dict,
    context_service: ChatContextService,
    messages_table: str,
    payload: SendChatMessageRequest,
    sender: str,
    session: dict,
    token: str,
    workspace: SupabaseWorkspaceService,
) -> StreamingResponse:
    guardrails = AiGuardrailService()
    actor = await workspace.get_authenticated_profile(token)
    context_decision = guardrails.evaluate_context(
        actor=actor,
        chat_scope=chat_scope,
        context=context,
        chat=session,
    )
    if context_decision.blocked:
        await _record_guardrail_event_safely(
            workspace=workspace,
            guardrails=guardrails,
            actor=actor,
            chat=session,
            chat_scope=chat_scope,
            context=context,
            decision=context_decision,
            stage="context",
            content=None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=context_decision.response or "Acesso ao contexto nao autorizado.",
        )

    if settings.app_env == "development":
        print(
            "[chat] request",
            {
                "chat_scope": chat_scope,
                "content_length": len(payload.content),
                "patient_id": payload.patient_id,
                "session_id": session.get("id"),
            },
        )

    user_message = await workspace.insert_chat_message(
        messages_table=messages_table,
        chats_table=chats_table,
        chat_id=session["id"],
        sender=sender,
        content=payload.content,
        metadata={
            "reasoning_level": payload.reasoning_level,
            "scope": chat_scope,
            "source": "star_nutri_app",
        },
    )
    await workspace.maybe_update_chat_title(
        table=chats_table,
        chat=session,
        content=payload.content,
    )

    input_decision = guardrails.evaluate_input(
        payload.content,
        actor=actor,
        chat_scope=chat_scope,
        context=context,
    )
    if input_decision.should_log:
        await _record_guardrail_event_safely(
            workspace=workspace,
            guardrails=guardrails,
            actor=actor,
            chat=session,
            chat_scope=chat_scope,
            context=context,
            decision=input_decision,
            stage="input",
            content=payload.content,
            message_id=user_message["id"],
        )

    if input_decision.blocked:
        return _guardrail_response(
            chats_table=chats_table,
            chat_scope=chat_scope,
            decision=input_decision,
            messages_table=messages_table,
            session=session,
            user_message=user_message,
            workspace=workspace,
        )

    reasoning_settings = context_service.get_reasoning_settings(payload.reasoning_level)
    if chat_scope == "nutritionist":
        session_messages = await workspace.list_authorized_nutritionist_messages(
            token,
            session["id"],
            limit=reasoning_settings["history_limit"] + 1,
        )
    else:
        session_messages = await workspace.list_authorized_patient_messages(
            token,
            session["id"],
            limit=reasoning_settings["history_limit"] + 1,
        )
    history = context_service.build_history_from_messages(
        session_messages,
        exclude_message_id=user_message["id"],
        limit=reasoning_settings["history_limit"],
    )
    history = guardrails.sanitize_history(history)
    memory_context = await context_service.load_memory_context(
        chat=session,
        chat_scope=chat_scope,
        context=context,
        token=token,
    )
    if settings.app_env == "development":
        print(
            "[chat] context loaded",
            {
                "chat_scope": chat_scope,
                "memory_conversations": memory_context.get("loaded_conversations", 0),
                "patient_id": (context.get("patient") or {}).get("id"),
                "session_id": session.get("id"),
            },
        )
    try:
        await FileMonitoringService().record_ai_context_usage(
            token=token,
            context=context,
            chat_scope=chat_scope,
            chat_id=session["id"],
            message_id=user_message["id"],
            metric_limit=reasoning_settings["metric_limit"],
        )
    except Exception:
        # Telemetry must never prevent a clinical chat response.
        logger.exception(
            "Could not record imported-file AI context usage",
            extra={"chat_scope": chat_scope, "chat_id": session.get("id")},
        )
    system_prompt = context_service.build_system_prompt(
        context,
        payload.content,
        history,
        payload.reasoning_level,
        chat_scope,
        memory_context,
    )
    ai_service = OpenAIChatService()
    agent_service = AiAgentService(workspace, ai_service)

    async def event_stream():
        answer = ""
        yield _event("session", {"session_id": session["id"]})

        try:
            agent_actions = await agent_service.run(
                chat=session,
                chat_scope=chat_scope,
                context=context,
                history=history,
                reasoning_level=payload.reasoning_level,
                token=token,
                user_message=payload.content,
                user_message_record=user_message,
            )
            for action in agent_actions:
                yield _event("action", action)

            deterministic_answer = _answer_from_agent_actions(agent_actions)
            if not deterministic_answer and _looks_like_write_request(payload.content):
                deterministic_answer = (
                    "Não foi possível concluir esta ação. Nenhuma operação foi executada "
                    "no banco de dados, então nenhuma alteração foi salva."
                )

            if deterministic_answer:
                answer = deterministic_answer
            else:
                response_prompt = _with_agent_actions(system_prompt, agent_actions)
                async for delta in ai_service.stream_chat(
                    system_prompt=response_prompt,
                    history=history,
                    reasoning_level=payload.reasoning_level,
                    user_message=payload.content,
                ):
                    answer += delta

            output_validation = guardrails.validate_output(
                answer,
                actor=actor,
                context=context,
                agent_actions=agent_actions,
            )
            if not output_validation.allowed:
                await _record_guardrail_event_safely(
                    workspace=workspace,
                    guardrails=guardrails,
                    actor=actor,
                    chat=session,
                    chat_scope=chat_scope,
                    context=context,
                    stage="output",
                    content=answer,
                    message_id=user_message["id"],
                    output_validation=output_validation,
                )
            answer = output_validation.content
            yield _event("delta", {"content": answer})

            saved = await workspace.insert_chat_message(
                messages_table=messages_table,
                chats_table=chats_table,
                chat_id=session["id"],
                sender="ai",
                content=answer.strip(),
                metadata={
                    "model": ai_service.model,
                    "agent_actions": agent_actions,
                    "reasoning_level": payload.reasoning_level,
                    "scope": chat_scope,
                    "source": "openai",
                    "memory_context_loaded": memory_context.get("loaded_conversations", 0),
                    "guardrail_input_category": input_decision.category,
                    "guardrail_output_allowed": output_validation.allowed,
                },
                touch_chat=False,
            )
            await context_service.update_conversation_memory(
                ai_service=ai_service,
                chat=session,
                chat_scope=chat_scope,
                context=context,
                messages_table=messages_table,
                token=token,
            )
            yield _event("done", {"message": saved})
        except Exception as exc:
            if settings.app_env == "development":
                print("Erro real no stream do chat:", repr(exc))
            await _record_guardrail_event_safely(
                workspace=workspace,
                guardrails=guardrails,
                actor=actor,
                chat=session,
                chat_scope=chat_scope,
                context=context,
                stage="provider",
                content=None,
                message_id=user_message["id"],
                provider_error=True,
            )
            yield _event(
                "error",
                {"detail": "Não foi possível concluir esta ação agora. Tente novamente em instantes."},
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _guardrail_response(
    *,
    chats_table: str,
    chat_scope: str,
    decision: GuardrailDecision,
    messages_table: str,
    session: dict,
    user_message: dict,
    workspace: SupabaseWorkspaceService,
) -> StreamingResponse:
    async def event_stream():
        response = decision.response or "Não posso atender a essa solicitação."
        yield _event("session", {"session_id": session["id"]})
        saved = await workspace.insert_chat_message(
            messages_table=messages_table,
            chats_table=chats_table,
            chat_id=session["id"],
            sender="ai",
            content=response,
            metadata={
                "source": "guardrail",
                "scope": chat_scope,
                "guardrail_category": decision.category,
                "guardrail_action": decision.action,
                "guardrail_rule_ids": list(decision.rule_ids),
                "in_reply_to": user_message.get("id"),
            },
            touch_chat=False,
        )
        yield _event("delta", {"content": response})
        yield _event("done", {"message": saved})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def _record_guardrail_event_safely(
    *,
    workspace: SupabaseWorkspaceService,
    guardrails: AiGuardrailService,
    actor: dict,
    chat: dict,
    chat_scope: str,
    context: dict,
    stage: str,
    content: str | None,
    message_id: str | None = None,
    decision: GuardrailDecision | None = None,
    output_validation=None,
    provider_error: bool = False,
) -> None:
    if decision:
        category = decision.category
        action = "safe_completed" if decision.action == "safe_complete" else "blocked"
        severity = decision.severity
        rule_ids = decision.rule_ids
        reason = decision.reason
    elif output_validation:
        category = output_validation.category
        action = "redacted"
        severity = output_validation.severity
        rule_ids = output_validation.rule_ids
        reason = output_validation.reason
    else:
        category = "provider_error"
        action = "failed"
        severity = "warning"
        rule_ids = ("GR-PROVIDER-001",)
        reason = "Falha na geracao ou persistencia da resposta." if provider_error else None

    try:
        await workspace.insert_ai_guardrail_event(
            guardrails.event_payload(
                actor=actor,
                chat=chat,
                chat_scope=chat_scope,
                context=context,
                stage=stage,
                category=category,
                action=action,
                severity=severity,
                rule_ids=rule_ids,
                reason=reason,
                content=content,
                message_id=message_id,
            )
        )
    except Exception:
        logger.exception(
            "Could not persist AI guardrail event",
            extra={"chat_scope": chat_scope, "chat_id": chat.get("id"), "stage": stage},
        )


async def _list_legacy_chats(
    patient_id: str | None,
    limit: int,
    offset: int,
    token: str,
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    profile = await workspace.get_authenticated_profile(token)
    safe_limit = min(max(limit, 1), 300)
    safe_offset = max(offset, 0)
    if profile["role"] == "nutritionist":
        sessions = await workspace.list_authorized_nutritionist_chats(token, patient_id)
    else:
        sessions = await workspace.list_authorized_patient_chats(token)
    return sessions[safe_offset : safe_offset + safe_limit]


def _normalize_legacy_payload(raw_payload: dict) -> SendChatMessageRequest:
    return SendChatMessageRequest(
        chat_scope=raw_payload.get("chat_scope") or raw_payload.get("chatScope"),
        content=(
            raw_payload.get("content")
            or raw_payload.get("message")
            or raw_payload.get("text")
            or ""
        ),
        patient_id=raw_payload.get("patient_id") or raw_payload.get("patientId"),
        reasoning_level=raw_payload.get("reasoning_level")
        or raw_payload.get("reasoningLevel")
        or "medium",
        session_id=(
            raw_payload.get("session_id")
            or raw_payload.get("sessionId")
            or raw_payload.get("conversation_id")
            or raw_payload.get("conversationId")
            or raw_payload.get("chat_id")
            or raw_payload.get("chatId")
        ),
    )


def _parse_legacy_limit_offset(value: str) -> tuple[int, int]:
    limit = 80
    offset = 0
    for index, part in enumerate(value.split("&")):
        if index == 0:
            part = f"limit={part}"
        key, _, raw = part.partition("=")
        try:
            parsed = int(raw)
        except ValueError:
            continue
        if key == "limit":
            limit = parsed
        if key == "offset":
            offset = parsed
    return limit, offset


def _event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _with_agent_actions(system_prompt: str, actions: list[dict]) -> str:
    if not actions:
        return (
            f"{system_prompt}\n\n"
            "Nenhuma tool operacional foi executada antes desta resposta. "
            "Nao diga que cadastrou, salvou, atualizou, marcou ou executou qualquer acao. "
            "Se o usuario pediu uma acao de cadastro/alteracao e nenhuma tool foi executada, "
            "explique objetivamente que a acao nao foi concluida e solicite os dados necessarios."
        )

    return (
        f"{system_prompt}\n\n"
        "Acoes operacionais avaliadas antes desta resposta:\n"
        f"{json.dumps(actions, ensure_ascii=False, default=str)}\n\n"
        "Ao responder, use apenas o resultado real acima. Informe sucesso somente quando "
        "success=true e status=executed. Para status failed/skipped, diga que a acao nao foi "
        "concluida e mostre o motivo em error/summary. Se houver result.pending_observation, "
        "pergunte se o usuario deseja adicionar essa observacao; a proxima resposta curta "
        "deve confirmar somente essa pending_action."
    )


def _answer_from_agent_actions(actions: list[dict]) -> str | None:
    if not actions:
        return None

    lines: list[str] = []
    for action in actions:
        status_value = action.get("status")
        result = action.get("result") or {}
        summary = (
            result.get("summary")
            or action.get("summary")
            or action.get("error")
            or "Ação avaliada."
        )
        if action.get("success") is True and status_value == "executed":
            lines.append(str(summary))
        elif status_value == "pending_confirmation":
            lines.append(str(summary))
        else:
            reason = action.get("error") or summary
            lines.append(f"Não foi possível concluir esta ação. Motivo: {reason}")

    return "\n".join(line.strip() for line in lines if line).strip() or None


def _looks_like_write_request(content: str) -> bool:
    normalized = _normalize_text(content)
    return any(
        term in normalized
        for term in (
            "adicionar",
            "adicione",
            "alterar",
            "altere",
            "atualizar",
            "atualize",
            "cadastrar",
            "cadastre",
            "cancelar",
            "cancele",
            "corrigir",
            "corrija",
            "criar",
            "crie",
            "deletar",
            "editar",
            "edite",
            "excluir",
            "exclua",
            "marcar",
            "marque",
            "mudar",
            "mude",
            "registrar",
            "registre",
            "remover",
            "remova",
            "salvar",
            "salve",
            "trocar",
            "troque",
        )
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"\s+", " ", ascii_value.lower()).split())


def _debug_context_payload(context: dict) -> dict:
    patient = context.get("patient") or {}
    profile = patient.get("profile") or context.get("profile") or {}
    workspace_summary = context.get("workspace_summary") or {}
    return {
        "patient": None
        if not patient
        else {
            "id": patient.get("id"),
            "full_name": profile.get("full_name"),
            "birth_date": patient.get("birth_date"),
            "gender": patient.get("gender"),
            "objective": patient.get("objective"),
        },
        "nutritionist_id": (context.get("nutritionist") or {}).get("id"),
        "workspace_summary": {
            "patients_count": workspace_summary.get("patients_count"),
            "active_patients_count": workspace_summary.get("active_patients_count"),
            "patients_index": workspace_summary.get("patients_index", [])[:20],
        },
        "counts": {
            "main_metrics": len(context.get("main_metrics", [])),
            "variable_metrics": len(context.get("variable_metrics", [])),
            "conditions": len(context.get("conditions", [])),
            "diets": len(context.get("diets", [])),
            "workouts": len(context.get("workouts", [])),
            "appointments": len(context.get("appointments", [])),
        },
    }


def _raise_session_error(exc: Exception) -> None:
    if settings.app_env == "development":
        print("Erro real em /chat/nutritionist/sessions:", repr(exc))

    if isinstance(exc, HTTPException) and exc.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    }:
        raise exc

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível iniciar a conversa.",
    ) from exc
