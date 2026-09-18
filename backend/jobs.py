"""PostgreSQL job claims with lease fencing and bounded crash recovery.

This module does not run an investigation. The processor and completion path
are connected only after evidence collection and report validation exist.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from backend.models import AuditEvent, Investigation, InvestigationJob


MAX_ATTEMPTS = 3
LEASE_SECONDS = 300
RETRY_DELAY_SECONDS = 30


@dataclass(frozen=True)
class JobClaim:
    investigation_id: str
    worker_id: str
    attempt: int


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _effective_now(now: datetime | None) -> datetime:
    value = now or utc_now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return value


def _valid_worker(worker_id: str) -> None:
    if not worker_id or len(worker_id) > 100:
        raise ValueError("worker_id must contain 1 to 100 characters")


def _owns_lease(job: InvestigationJob, claim: JobClaim, now: datetime) -> bool:
    lease_until = job.lease_until
    # SQLite test databases return naive datetimes; PostgreSQL stores UTC-aware values.
    if lease_until is not None and lease_until.tzinfo is None:
        lease_until = lease_until.replace(tzinfo=timezone.utc)
    return (
        job.status == "RUNNING" and job.worker_id == claim.worker_id
        and job.attempts == claim.attempt
        and lease_until is not None and lease_until > now
    )


def claim_next_job(
    factory: sessionmaker[Session], worker_id: str, *, now: datetime | None = None,
) -> JobClaim | None:
    """Atomically claim an available job or reclaim a crashed worker's lease."""
    _valid_worker(worker_id)
    now = _effective_now(now)

    while True:
        with factory.begin() as session:
            job = session.scalar(
                select(InvestigationJob)
                .where(or_(
                    and_(InvestigationJob.status == "QUEUED", InvestigationJob.available_at <= now),
                    and_(InvestigationJob.status == "RUNNING", or_(
                        InvestigationJob.lease_until <= now,
                        InvestigationJob.lease_until.is_(None),
                    )),
                ))
                .order_by(InvestigationJob.available_at, InvestigationJob.investigation_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None

            investigation = session.get(Investigation, job.investigation_id)
            if investigation is None:
                raise RuntimeError("Job is missing its investigation")
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "FAILED"
                job.worker_id = None
                job.lease_until = None
                investigation.status = "FAILED"
                investigation.finished_at = now
                investigation.error = "ATTEMPTS_EXHAUSTED"
                session.add(AuditEvent(
                    incident_id=investigation.incident_id,
                    investigation_id=investigation.id,
                    action="INVESTIGATION_FAILED", actor="worker",
                    detail={"reason": "ATTEMPTS_EXHAUSTED"},
                ))
                continue

            was_running = job.status == "RUNNING"
            job.status = "RUNNING"
            job.attempts += 1
            job.worker_id = worker_id
            job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            investigation.status = "RUNNING"
            investigation.started_at = now
            investigation.error = None
            session.add(AuditEvent(
                incident_id=investigation.incident_id,
                investigation_id=investigation.id,
                action="INVESTIGATION_RECLAIMED" if was_running else "INVESTIGATION_STARTED",
                actor="worker", detail={"attempt": job.attempts},
            ))
            return JobClaim(investigation.id, worker_id, job.attempts)


def renew_lease(
    factory: sessionmaker[Session], claim: JobClaim, *, now: datetime | None = None,
) -> bool:
    """Return False when another worker has reclaimed the job or the lease expired."""
    now = _effective_now(now)
    with factory.begin() as session:
        job = session.scalar(
            select(InvestigationJob)
            .where(InvestigationJob.investigation_id == claim.investigation_id)
            .with_for_update()
        )
        if job is None or not _owns_lease(job, claim, now):
            return False
        job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        return True


def fail_claim(
    factory: sessionmaker[Session], claim: JobClaim, *,
    reason: str = "PROCESSOR_ERROR", now: datetime | None = None,
) -> bool:
    """Retry within the attempt budget; a stale claim cannot change state."""
    if reason not in {"PROCESSOR_ERROR", "TELEMETRY_UNAVAILABLE", "RESULT_INVALID"}:
        raise ValueError("Unsupported public failure reason")
    now = _effective_now(now)
    with factory.begin() as session:
        job = session.scalar(
            select(InvestigationJob)
            .where(InvestigationJob.investigation_id == claim.investigation_id)
            .with_for_update()
        )
        if job is None or not _owns_lease(job, claim, now):
            return False
        investigation = session.get(Investigation, claim.investigation_id)
        job.worker_id = None
        job.lease_until = None
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "FAILED"
            investigation.status = "FAILED"
            investigation.finished_at = now
            action = "INVESTIGATION_FAILED"
        else:
            job.status = "QUEUED"
            job.available_at = now + timedelta(seconds=RETRY_DELAY_SECONDS)
            investigation.status = "QUEUED"
            action = "INVESTIGATION_RETRY_SCHEDULED"
        investigation.error = reason
        session.add(AuditEvent(
            incident_id=investigation.incident_id,
            investigation_id=investigation.id, action=action,
            actor="worker", detail={"reason": reason, "attempt": job.attempts},
        ))
        return True
