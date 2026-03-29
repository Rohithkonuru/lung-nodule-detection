from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from pathlib import Path

from app.api.v1.routes import router as v1_router
from app.core.config import settings
from app.core.security import get_password_hash
from app.db import models
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.middleware.audit import AuditLogMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditLogMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": str(exc.detail), "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled server error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"message": "Internal server error"},
        )

    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()


def ensure_demo_user() -> None:
    db = SessionLocal()
    try:
        demo_email = "demo@example.com"
        demo_password = "demo123"
        demo_name = "Demo User"

        user = db.query(models.User).filter(models.User.email == demo_email).first()
        if user is None:
            user = models.User(
                name=demo_name,
                email=demo_email,
                password_hash=get_password_hash(demo_password),
                role="user",
            )
            db.add(user)
            db.commit()
            logger.info("Created demo user: %s", demo_email)
            return

        # Keep demo credentials predictable for local testing.
        user.password_hash = get_password_hash(demo_password)
        if not user.name:
            user.name = demo_name
        db.add(user)
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.APP_ENV.lower() != "production":
        ensure_demo_user()
    else:
        logger.info("Skipping demo user initialization in production mode.")
    if settings.SECRET_KEY.startswith("dev-only-"):
        logger.warning("Using development SECRET_KEY. Set SECRET_KEY in environment for production/pilot deployments.")
    if not Path(settings.MODEL_WEIGHTS_PATH).exists():
        logger.warning("MODEL_WEIGHTS_PATH does not exist: %s", settings.MODEL_WEIGHTS_PATH)
