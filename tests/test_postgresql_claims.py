"""PostgreSQL-only verification for concurrent investigation job claims."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.jobs import claim_next_job
from backend.models import AuditEvent, Incident, Investigation, InvestigationJob


@pytest.fixture
def postgresql_factory():
    """Create all project tables in a disposable, uniquely named schema."""
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL locking tests")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg://")

    schema = f"test_claims_{uuid.uuid4().hex}"
    admin_engine = create_engine(url, pool_pre_ping=True)
    test_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema}"},
        )
        Base.metadata.create_all(test_engine)
        yield sessionmaker(bind=test_engine, expire_on_commit=False)
    finally:
        if test_engine is not None:
            test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_two_workers_cannot_claim_the_same_job(postgresql_factory):
    factory = postgresql_factory
    window_start = datetime.now(timezone.utc) - timedelta(minutes=15)
    window_end = window_start + timedelta(minutes=10)
    with factory.begin() as session:
        incident = Incident(
            title="Concurrent claim test",
            service="incident-demo-api",
            severity="LOW",
            window_start=window_start,
            window_end=window_end,
        )
        session.add(incident)
        session.flush()
        investigation = Investigation(
            incident_id=incident.id,
            window_start=window_start,
            window_end=window_end,
        )
        session.add(investigation)
        session.flush()
        investigation_id = investigation.id
        session.add(InvestigationJob(investigation_id=investigation_id))

    # Release both callers together. PostgreSQL row locking must allow exactly
    # one claim; the loser must skip the locked or newly RUNNING row.
    barrier = threading.Barrier(3)

    def compete(worker_id: str):
        barrier.wait(timeout=5)
        return claim_next_job(factory, worker_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(compete, "worker-a"),
                   executor.submit(compete, "worker-b")]
        barrier.wait(timeout=5)
        claims = [future.result(timeout=10) for future in futures]

    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0].investigation_id == investigation_id
    assert winners[0].attempt == 1

    with factory() as session:
        job = session.get(InvestigationJob, investigation_id)
        assert job.status == "RUNNING"
        assert job.attempts == 1
        assert job.worker_id == winners[0].worker_id
        starts = session.scalars(
            select(AuditEvent).where(
                AuditEvent.investigation_id == investigation_id,
                AuditEvent.action == "INVESTIGATION_STARTED",
            )
        ).all()
        assert len(starts) == 1
