from fastapi import APIRouter

from .admin import router as admin_router
from .chat import router as chat_router
from .health import router as health_router
from .nutritionists import router as nutritionists_router
from .patients import router as patients_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(chat_router)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(nutritionists_router)
api_router.include_router(patients_router)
