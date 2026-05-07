from fastapi import APIRouter

from ...core.config import settings

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "supabase_configured": bool(
            settings.supabase_url and settings.supabase_service_role_key
        ),
        "glm_configured": bool(settings.glm_api_key),
    }
