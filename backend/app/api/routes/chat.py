import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...schemas.chat import CreateChatSessionRequest, SendChatMessageRequest
from ...services.ai_agent_service import AiAgentService
from ...services.chat_context_service import ChatContextService
from ...services.openai_service import OpenAIChatService
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions")
async def list_chat_sessions(
    patient_id: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    if patient_id:
        return await list_nutritionist_chat_sessions(patient_id, token)
    return await list_patient_chat_sessions(token)


@router.get("/nutritionist/sessions")
async def list_nutritionist_chat_sessions(
    patient_id: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    return await workspace.list_authorized_nutritionist_chats(token, patient_id)


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
    if payload.patient_id:
        return await create_nutritionist_chat_session(payload, token)
    return await create_patient_chat_session(payload, token)


@router.post("/nutritionist/sessions")
async def create_nutritionist_chat_session(
    payload: CreateChatSessionRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    workspace = SupabaseWorkspaceService()
    return await workspace.create_authorized_nutritionist_chat(
        token,
        payload.patient_id,
        payload.title,
    )


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
    if payload.patient_id:
        return await send_nutritionist_chat_message(payload, token)
    return await send_patient_chat_message(payload, token)


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
    system_prompt = context_service.build_system_prompt(
        context,
        payload.content,
        history,
        payload.reasoning_level,
        chat_scope,
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

            response_prompt = _with_agent_actions(system_prompt, agent_actions)
            async for delta in ai_service.stream_chat(
                system_prompt=response_prompt,
                history=history,
                reasoning_level=payload.reasoning_level,
                user_message=payload.content,
            ):
                answer += delta
                yield _event("delta", {"content": delta})

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
                },
            )
            yield _event("done", {"message": saved})
        except Exception as exc:
            yield _event("error", {"detail": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _with_agent_actions(system_prompt: str, actions: list[dict]) -> str:
    if not actions:
        return system_prompt

    return (
        f"{system_prompt}\n\n"
        "Acoes operacionais avaliadas antes desta resposta:\n"
        f"{json.dumps(actions, ensure_ascii=False, default=str)}\n\n"
        "Ao responder, informe de forma objetiva as acoes executadas, ignoradas, "
        "falhas ou pendentes de confirmacao. Nao prometa que uma acao foi feita se "
        "o status nao for executed."
    )
