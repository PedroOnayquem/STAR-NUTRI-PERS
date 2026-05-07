from fastapi import APIRouter, Depends, Header, HTTPException, status

from ...schemas.admin import CreateNutritionistRequest, CreateNutritionistResponse
from ...services.supabase_admin_service import SupabaseAdminService
from ...services.supabase_workspace_service import SupabaseWorkspaceService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    return authorization.split(" ", 1)[1].strip()


@router.post("/nutritionists", response_model=CreateNutritionistResponse)
async def create_nutritionist(
    payload: CreateNutritionistRequest,
    token: str = Depends(get_bearer_token),
) -> dict:
    service = SupabaseAdminService()
    await service.assert_admin(token)
    return await service.create_nutritionist(payload)


@router.get("/workspace")
async def get_admin_workspace(token: str = Depends(get_bearer_token)) -> dict:
    service = SupabaseWorkspaceService()
    return await service.get_admin_workspace(token)
