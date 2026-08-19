from fastapi import APIRouter, Depends

from ...schemas.auth import ChangeOwnPasswordRequest
from ...services.supabase_user_service import SupabaseUserService
from .admin import get_bearer_token


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/change-password")
async def change_own_password(
    payload: ChangeOwnPasswordRequest,
    token: str = Depends(get_bearer_token),
) -> dict[str, bool]:
    service = SupabaseUserService()
    await service.change_own_password(token, payload.password)
    return {"updated": True}
