from fastapi import APIRouter, Depends, Query

from ...services.file_monitoring_service import FileMonitoringService
from .admin import get_bearer_token


router = APIRouter(prefix="/files", tags=["file-monitoring"])


@router.get("/monitoring")
async def get_file_monitoring(
    days: int = Query(default=30),
    limit: int = Query(default=60, ge=1, le=100),
    token: str = Depends(get_bearer_token),
) -> dict:
    return await FileMonitoringService().get_dashboard(token, days=days, limit=limit)
