from fastapi import APIRouter

from routes.competitor import router as competitor_router

api_router = APIRouter()
api_router.include_router(competitor_router)

__all__ = ["api_router"]
