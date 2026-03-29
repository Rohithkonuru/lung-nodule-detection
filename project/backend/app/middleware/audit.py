import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import BackgroundTasks

from app.core.security import decode_token
from app.db.models import AuditLog
from app.db.session import SessionLocal


def log_audit_event_bg(user_id: int | None, action: str, entity: str, entity_id: int | None, meta_json: dict):
    """Background task to log audit events without blocking requests"""
    db = SessionLocal()
    try:
        audit = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            meta_json=meta_json,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        # Silently fail audit logging - don't let it cause request failures
        import logging
        logging.getLogger("audit").warning(f"Failed to audit log: {e}")
    finally:
        db.close()


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)

        # Skip audit logging for non-relevant endpoints
        if request.method == "OPTIONS" or request.url.path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return response

        # Skip audit logging for auth endpoints (they already log themselves)
        if request.url.path.startswith("/api/v1/auth/"):
            return response

        user_id: int | None = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            sub = decode_token(token)
            if sub and str(sub).isdigit():
                user_id = int(sub)

        # Log audit event in background (doesn't block response)
        # Note: We can't use BackgroundTasks here because middleware doesn't have access to it
        # Instead, we create a simple background operation
        import threading
        audit_thread = threading.Thread(
            target=log_audit_event_bg,
            args=(
                user_id,
                request.method,
                request.url.path,
                None,
                {
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client": request.client.host if request.client else None,
                },
            ),
            daemon=True,
        )
        audit_thread.start()

        return response
