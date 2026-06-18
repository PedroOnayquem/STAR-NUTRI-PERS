from fastapi import APIRouter, Depends, File, Form, UploadFile

from ...schemas.patients import CreatePatientRequest, CreatePatientResponse
from ...schemas.workspace import ActivatePatientRequest, UpdatePatientRequest
from ...services.bioimpedance_import_service import BioimpedanceImportService
from ...services.supabase_user_service import SupabaseUserService
from ...services.supabase_workspace_service import SupabaseWorkspaceService
from .admin import get_bearer_token

router = APIRouter(prefix="/nutritionists", tags=["nutritionists"])


@router.patch("/profile")
async def update_profile(
    professional_name: str | None = Form(None),
    clinic_name: str | None = Form(None),
    phone: str | None = Form(None),
    bio: str | None = Form(None),
    default_patient_trial_days: int | None = Form(None),
    remove_image: bool = Form(False),
    image: UploadFile | None = File(None),
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.update_nutritionist_profile(
        token,
        professional_name=professional_name,
        clinic_name=clinic_name,
        phone=phone,
        bio=bio,
        default_patient_trial_days=default_patient_trial_days,
        remove_image=remove_image,
        image=image,
    )


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


@router.post("/patients/{patient_id}/activate")
async def activate_patient(
    patient_id: str,
    payload: ActivatePatientRequest | None = None,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.activate_patient(token, patient_id, payload)


@router.delete("/patients/{patient_id}")
async def deactivate_patient(
    patient_id: str,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseWorkspaceService()
    return await service.deactivate_patient(token, patient_id)
