"""Manual incident intake; no simulator state is exposed as product data."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models import AuditEvent, IdempotencyRecord, Incident
from backend.schemas import IncidentCreate, IncidentOut, IncidentUpdate


router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])
DbSession = Annotated[Session, Depends(get_session)]


def require_incident(session: Session, incident_id: str) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(
    body: IncidentCreate,
    response: Response,
    session: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    scope = "incident.create"
    payload_hash = hashlib.sha256(
        body.model_dump_json(exclude_none=True).encode("utf-8")
    ).hexdigest()

    def replay(existing: IdempotencyRecord) -> Incident:
        if existing.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was used with another payload")
        response.headers["Location"] = f"/api/v1/incidents/{existing.resource_id}"
        return require_incident(session, existing.resource_id)

    existing = session.get(IdempotencyRecord, idempotency_key)
    if existing:
        return replay(existing)
    # The initial lookup started a transaction. Flush all three rows together;
    # the unique key is the concurrency arbiter for simultaneous requests.
    incident = Incident(**body.model_dump())
    session.add(incident)
    session.flush()
    session.add(IdempotencyRecord(
        key=idempotency_key, scope=scope, payload_hash=payload_hash,
        resource_id=incident.id,
    ))
    session.add(AuditEvent(
        incident_id=incident.id, action="INCIDENT_CREATED", actor="api",
        detail={"service": incident.service},
    ))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(IdempotencyRecord, idempotency_key)
        if existing:
            return replay(existing)
        raise
    response.headers["Location"] = f"/api/v1/incidents/{incident.id}"
    return incident


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, session: DbSession):
    return require_incident(session, incident_id)


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return session.scalars(
        select(Incident).order_by(Incident.created_at.desc(), Incident.id.desc())
        .limit(limit).offset(offset)
    ).all()


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: str, body: IncidentUpdate, session: DbSession):
    changes = body.model_dump(exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Provide non-null incident fields to update")
    incident = require_incident(session, incident_id)
    if incident.status != "OPEN":
        raise HTTPException(status_code=409, detail="Closed incidents cannot be edited")
    for field, value in changes.items():
        setattr(incident, field, value)
    session.add(AuditEvent(
        incident_id=incident.id, action="INCIDENT_UPDATED", actor="api",
        detail={"fields": sorted(changes)},
    ))
    session.commit()
    return incident
