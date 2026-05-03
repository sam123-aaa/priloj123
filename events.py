import json
from datetime import datetime

from sqlalchemy.orm import Session

from orm_models import DomainEvent


def publish_domain_event(
    session: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id,
    payload: dict,
):
    event = DomainEvent(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=json.loads(json.dumps(payload, ensure_ascii=False, default=str)),
        status="pending",
        created_at=datetime.utcnow(),
    )
    session.add(event)
    session.flush()
    return event
