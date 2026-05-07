import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...schemas.chat import CreateChatSessionRequest, SendChatMessageRequest
from ...services.chat_context_service import ChatContextService
from ...services.glm_service import GlmService
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions")
async def list_chat_sessions(
    patient_id: str | None = None,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    return await workspace.list_authorized_chat_sessions(token, patient_id)


@router.post("/sessions")
async def create_chat_session(
    payload: CreateChatSessionRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    workspace = SupabaseWorkspaceService()
    return await workspace.create_authorized_chat_session(
        token,
        payload.patient_id,
        payload.title,
    )


@router.get("/sessions/{session_id}/messages")
async def list_chat_messages(
    session_id: str,
    token: str = Depends(get_bearer_token),
) -> list[dict]:
    workspace = SupabaseWorkspaceService()
    return await workspace.get_authorized_chat_messages(token, session_id)


@router.post("/send")
async def send_chat_message(
    payload: SendChatMessageRequest,
    token: str = Depends(get_bearer_token),
) -> StreamingResponse:
    workspace = SupabaseWorkspaceService()
    context_service = ChatContextService(workspace)
    context, session, sender = await context_service.resolve_context(
        token,
        payload.patient_id,
        payload.session_id,
    )

    await workspace.insert_chat_message(
        session["id"],
        sender,
        payload.content,
        {"source": "star_nutri_app"},
    )

    history = context_service.build_history(context, session["id"])
    system_prompt = context_service.build_system_prompt(
        context,
        payload.content,
        history,
    )
    glm = GlmService()

    async def event_stream():
        answer = ""
        yield _event("session", {"session_id": session["id"]})

        try:
            async for delta in glm.stream_chat(
                system_prompt=system_prompt,
                history=history,
                user_message=payload.content,
            ):
                answer += delta
                yield _event("delta", {"content": delta})

            saved = await workspace.insert_chat_message(
                session["id"],
                "ai",
                answer.strip(),
                {"model": glm.model, "source": "glm"},
            )
            yield _event("done", {"message": saved})
        except Exception as exc:
            yield _event("error", {"detail": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
