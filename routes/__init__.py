from fastapi import APIRouter

from routes.analyzecompany import router as analyzecompany_router
from routes.company_content import router as company_content_router
from routes.competitor import router as competitor_router
from routes.contentgeneration import router as contentgeneration_router
from routes.contentrecommendation import router as contentrecommendation_router
from routes.imagegeneration import router as imagegeneration_router
from routes.nichetrend import router as nichetrend_router
from routes.outreach import router as outreach_router
from routes.scriptgenerator import router as scriptgenerator_router
from routes.trend import router as trend_router

api_router = APIRouter()
api_router.include_router(analyzecompany_router)
api_router.include_router(competitor_router)
api_router.include_router(trend_router)
api_router.include_router(nichetrend_router)
api_router.include_router(outreach_router)
api_router.include_router(scriptgenerator_router)
api_router.include_router(contentgeneration_router)
api_router.include_router(contentrecommendation_router)
api_router.include_router(imagegeneration_router)
api_router.include_router(company_content_router)

__all__ = ["api_router"]
