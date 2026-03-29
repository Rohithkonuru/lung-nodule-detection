from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_audit_event(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta_json=metadata or {},
    )
    db.add(event)
    db.commit()
