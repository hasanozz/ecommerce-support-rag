from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import close_database, initialize_database
from .database import SessionLocal
from .routers import (
    auth_router,
    conversation_router,
    feedback_router,
    rag_router,
    ticket_router,
)


settings = get_settings()
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Secrets file loaded successfully.")
    logger.info("Gemini default model configured: %s", settings.gemini_model)
    logger.info(
        "Gemini runtime/dev model configured: %s", settings.gemini_model_dev
    )
    if settings.auto_create_tables:
        await initialize_database()
    yield
    await close_database()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_frontend_cache_in_development(request: Request, call_next):
    response = await call_next(request)
    if settings.app_env.casefold() == "development" and (
        request.url.path == "/" or request.url.path.startswith("/assets/")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.include_router(rag_router, prefix=settings.api_prefix)
app.include_router(auth_router)
app.include_router(conversation_router)
app.include_router(feedback_router)
app.include_router(ticket_router)


@app.get("/health")
async def health():
    from sqlalchemy import text

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.app_name, "database": "ok"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "service": settings.app_name,
                "database": "unavailable",
            },
        )


if settings.frontend_path.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=settings.frontend_path),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    async def frontend() -> FileResponse:
        return FileResponse(settings.frontend_path / "index.html")
