from fastapi import APIRouter, Depends

from ...schemas.patients import CreatePatientRequest, CreatePatientResponse
from ...schemas.workspace import UpdatePatientRequest
from ...services.supabase_user_service import SupabaseUserService
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/nutritionists", tags=["nutritionists"])


@router.post("/patients", response_model=CreatePatientResponse)
async def create_patient(
    payload: CreatePatientRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseUserService()
    nutritionist = await service.assert_nutritionist(token)
    return await service.create_patient(payload, nutritionist_id=nutritionist["id"])


@router.get("/workspace")
async def get_workspace(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_nutritionist_workspace(token)


@router.get("/patients/{patient_id}/context")
async def get_patient_context(
    patient_id: str,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_patient_context_for_nutritionist(token, patient_id)


@router.patch("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    payload: UpdatePatientRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.update_patient(token, patient_id, payload)


@router.delete("/patients/{patient_id}")
async def deactivate_patient(
    patient_id: str,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.deactivate_patient(token, patient_id)
