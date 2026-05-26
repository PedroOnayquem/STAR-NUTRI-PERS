from fastapi import APIRouter, Depends

from ...schemas.workspace import UpdateMyPatientProfileRequest
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("/me/context")
async def get_my_context(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_patient_context_for_patient(token)


@router.patch("/me/profile")
async def update_my_profile(
    payload: UpdateMyPatientProfileRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.update_my_patient_profile(token, payload)
