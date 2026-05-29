from fastapi import APIRouter, Depends, File, UploadFile

from ...schemas.patients import CreatePatientRequest, CreatePatientResponse
from ...schemas.workspace import UpdatePatientRequest
from ...services.bioimpedance_import_service import BioimpedanceImportService
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


@router.post("/patients/import-bioimpedance-pdf")
async def import_bioimpedance_pdf(
    file: UploadFile = File(...),
    token: str = Depends(get_bearer_token),
) -> dict:
    service = BioimpedanceImportService()
    return await service.process_report(token, file)


@router.post("/patients/import-bioimpedance-report")
async def import_bioimpedance_report(
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    token: str = Depends(get_bearer_token),
) -> dict:
    service = BioimpedanceImportService()
    selected_files = files or ([file] if file else [])
    return await service.process_reports(token, selected_files)


@router.get("/imports/{import_id}/signed-url")
async def get_import_signed_url(
    import_id: str,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = BioimpedanceImportService()
    return await service.create_signed_url(token, import_id)


@router.get("/imports/{import_id}/files/signed-urls")
async def get_import_file_signed_urls(
    import_id: str,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = BioimpedanceImportService()
    return await service.create_file_signed_urls(token, import_id)


@router.get("/workspace")
async def get_workspace(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_nutritionist_workspace(token)


@router.get("/dashboard")
async def get_dashboard(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_nutritionist_dashboard(token)


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
