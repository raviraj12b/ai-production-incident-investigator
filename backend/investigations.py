"""Durable investigation requests; processing is a separate worker concern."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_session
from backend.models import (
    AuditEvent, Evidence, Incident, Investigation, InvestigationJob, InvestigationRequest,
)
from backend.schemas import EvidenceOut, InvestigationCreate, InvestigationOut, JobOut


router = APIRouter(tags=["investigations"])
DbSession = Annotated[Session, Depends(get_session)]


def investigation_out(session: Session, investigation: Investigation) -> InvestigationOut:
    job = session.get(InvestigationJob, investigation.id)
    if job is None:
        raise RuntimeError("Investigation is missing its job")
    return InvestigationOut(
        id=investigation.id, incident_id=investigation.incident_id,
        parent_id=investigation.parent_id, status=investigation.status,
        focus=investigation.focus, window_start=investigation.window_start,
        window_end=investigation.window_end, created_at=investigation.created_at,
        started_at=investigation.started_at, finished_at=investigation.finished_at,
        error=investigation.error,
        job=JobOut(status=job.status, attempts=job.attempts),
    )


@router.post(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationOut, status_code=202,
)
def create_investigation(
    incident_id: str,
    body: InvestigationCreate,
    response: Response,
    session: DbSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    # Serialize requests for the same incident, including concurrent retries.
    incident = session.scalar(
        select(Incident).where(Incident.id == incident_id).with_for_update()
    )
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    payload_hash = hashlib.sha256(body.model_dump_json().encode("utf-8")).hexdigest()
    existing = session.get(InvestigationRequest, (incident_id, idempotency_key))
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was used with another payload")
        response.headers["Location"] = f"/api/v1/investigations/{existing.investigation_id}"
        return investigation_out(session, session.get(Investigation, existing.investigation_id))

    if incident.status != "OPEN":
        raise HTTPException(status_code=409, detail="Closed incidents cannot be investigated")
    active_id = session.scalar(
        select(Investigation.id)
        .where(Investigation.incident_id == incident_id)
        .where(Investigation.status.in_(("QUEUED", "RUNNING")))
        .limit(1)
    )
    if active_id is not None:
        raise HTTPException(status_code=409, detail="An investigation is already active for this incident")

    investigation = Investigation(
        incident_id=incident_id, focus=body.focus,
        window_start=incident.window_start, window_end=incident.window_end,
    )
    session.add(investigation)
    session.flush()
    session.add(InvestigationJob(investigation_id=investigation.id))
    session.add(InvestigationRequest(
        incident_id=incident_id, key=idempotency_key,
        payload_hash=payload_hash, investigation_id=investigation.id,
    ))
    session.add(AuditEvent(
        incident_id=incident_id, investigation_id=investigation.id,
        action="INVESTIGATION_QUEUED", actor="api", detail={},
    ))
    session.commit()
    response.headers["Location"] = f"/api/v1/investigations/{investigation.id}"
    return investigation_out(session, investigation)


@router.get("/api/v1/investigations/{investigation_id}", response_model=InvestigationOut)
def get_investigation(investigation_id: str, session: DbSession):
    investigation = session.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation_out(session, investigation)


@router.get("/api/v1/investigations/{investigation_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    investigation_id: str, session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if session.get(Investigation, investigation_id) is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return session.scalars(
        select(Evidence)
        .where(Evidence.investigation_id == investigation_id)
        .order_by(Evidence.observed_at, Evidence.id)
        .limit(limit).offset(offset)
    ).all()


@router.get(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=list[InvestigationOut],
)
def list_investigations(
    incident_id: str,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    if session.get(Incident, incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    rows = session.scalars(
        select(Investigation)
        .where(Investigation.incident_id == incident_id)
        .order_by(Investigation.created_at.desc(), Investigation.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return [investigation_out(session, row) for row in rows]
