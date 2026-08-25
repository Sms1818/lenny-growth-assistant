from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from app.core.logger import log_event


from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.health import router as health_router
from app.api.routes.messages import router as messages_router
from app.api.routes.sessions import router as sessions_router
from app.core.config import get_settings
from app.knowledge.embeddings import (
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

# Allow the Vite dev server origin only — required for browser API calls locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artifacts_router)
app.include_router(health_router)
app.include_router(messages_router)
app.include_router(sessions_router)


@app.exception_handler(EmbeddingServiceUnavailableError)
async def embedding_unavailable_handler(
    request: Request,
    exc: EmbeddingServiceUnavailableError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": {
                "code": "embedding_unavailable",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(EmbeddingServiceError)
async def embedding_service_error_handler(
    request: Request,
    exc: EmbeddingServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "detail": {
                "code": "embedding_failed",
                "message": str(exc),
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    log_event(
        "database_error",
        error_type=exc.__class__.__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": {"code": "database_unavailable", "message": "The database is temporarily unavailable."}}
    )
