import logging
import sys
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles

from core.exception_handlers import register_exception_handlers
from routes import api_router
from service.ImageGeneration.gemini_image import generated_images_dir

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="Bearer",
    description="Enter your Bearer token",
    auto_error=False,
)
security_schemes = {
    "Bearer": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your JWT token",
    }
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Trend API started")
    yield
    logger.info("Trend API stopped")


app = FastAPI(
    title="Trend API",
    description="API for competitor analysis and Instagram trend discovery",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_init_oauth={"clientId": "swagger-ui"},
    swagger_ui_parameters={"persistAuthorization": True},
)

register_exception_handlers(app)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = security_schemes
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


app.include_router(api_router)

# Local/dev only. Vercel (and most serverless) has a read-only package FS,
# so never create/mount media dirs at import time there.
_media_dir = generated_images_dir(create=False)
if _media_dir is None:
    # Attempt /tmp for local-like writable mounts; skip if still unavailable.
    _media_dir = generated_images_dir(create=True)

if _media_dir is not None:
    try:
        app.mount(
            "/media/images",
            StaticFiles(directory=str(_media_dir)),
            name="generated_images",
        )
        logger.info("Mounted local media at /media/images -> %s", _media_dir)
    except Exception:
        logger.exception("Skipping /media/images mount")
else:
    logger.info(
        "Skipping /media/images mount (read-only FS). "
        "Use return_base64=true for production image responses."
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
