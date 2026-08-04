from fastapi import APIRouter

from routes.competitor import router as competitor_router
from routes.nichetrend import router as nichetrend_router
from routes.trend import router as trend_router

api_router = APIRouter()
api_router.include_router(competitor_router)
api_router.include_router(trend_router)
api_router.include_router(nichetrend_router)

__all__ = ["api_router"]
