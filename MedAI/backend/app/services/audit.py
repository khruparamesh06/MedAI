from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record(db: Session, actor: User | None, action: str, entity_type: str,
           entity_id: int | None = None, **detail) -> None:
    """Add an audit event to the current transaction (committed together with the change)."""
    db.add(AuditEvent(actor_id=actor.id if actor else None, action=action,
                      entity_type=entity_type, entity_id=entity_id, detail=detail))
