from fastapi import APIRouter, Depends

from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me/context")
async def get_my_context(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_patient_context_for_patient(token)
