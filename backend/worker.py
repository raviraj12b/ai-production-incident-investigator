"""Standalone, single-investigation worker; no telemetry or model in the API process."""

import argparse
import logging
import time
import uuid
from datetime import timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.analysis_pipeline import AnalysisValidationError, complete_claim, inconclusive
from backend.database import session_factory
from backend.evidence_pipeline import EvidenceValidationError, collect_for_claim
from backend.jobs import claim_next_job, fail_claim, renew_lease
from backend.model_adapter import (
    Analyzer, EvidenceView, GroqAnalyzer, ModelOutputInvalid, ModelUnavailable,
)
from backend.models import Evidence
from backend.telemetry_gateway import TelemetryGateway, TelemetryUnavailable


logger = logging.getLogger("incident-investigator.worker")


def _failure(factory, claim, reason: str) -> str:
    return "HANDLED_FAILURE" if fail_claim(factory, claim, reason=reason) else "STALE"


def run_once(
    factory: sessionmaker[Session], gateway: TelemetryGateway,
    analyzer: Analyzer, worker_id: str, *, investigation_id: str | None = None,
) -> str:
    """Process one job or return IDLE; status reads give detailed job state."""
    claim = claim_next_job(factory, worker_id, investigation_id=investigation_id)
    if claim is None:
        return "IDLE"
    try:
        batch = collect_for_claim(factory, claim, gateway)
    except TelemetryUnavailable:
        return _failure(factory, claim, "TELEMETRY_UNAVAILABLE")
    except (EvidenceValidationError, ValueError):
        return _failure(factory, claim, "RESULT_INVALID")
    if batch is None or not renew_lease(factory, claim):
        return "STALE"

    # Read the committed, normalized snapshot. Do not forward the incident
    # title/description, raw logs, request IDs, or arbitrary trace attributes.
    with factory() as session:
        rows = session.scalars(select(Evidence).where(
            Evidence.investigation_id == claim.investigation_id,
        ).order_by(Evidence.observed_at, Evidence.id)).all()
        evidence = tuple(EvidenceView(
            id=row.id, kind=row.kind,
            observed_at=(row.observed_at if row.observed_at.tzinfo else
                         row.observed_at.replace(tzinfo=timezone.utc)),
            service=row.service, summary=row.summary, trace_id=row.trace_id,
        ) for row in rows)
    try:
        # No model call is needed when the successful capture has no evidence.
        draft = analyzer.analyze(evidence, batch.gaps) if evidence else inconclusive(batch.gaps)
        return "DONE" if complete_claim(factory, claim, draft) else "STALE"
    except ModelUnavailable:
        return _failure(factory, claim, "MODEL_UNAVAILABLE")
    except (ModelOutputInvalid, AnalysisValidationError):
        return _failure(factory, claim, "RESULT_INVALID")


def _check_database_revision(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    if revision != "phase05_0002":
        raise RuntimeError("Database migration must be phase05_0002 before running the worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process queued investigations")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Claim at most one job and exit")
    mode.add_argument("--poll", action="store_true", help="Poll until interrupted")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (1-60)")
    parser.add_argument("--investigation-id", type=uuid.UUID,
                        help="Process only this queued investigation (with --once)")
    args = parser.parse_args(argv)
    if not 1 <= args.interval <= 60:
        parser.error("--interval must be between 1 and 60")
    if args.investigation_id and not args.once:
        parser.error("--investigation-id requires --once")
    # Fail configuration before taking a lease. An API key is not read from the
    # database or printed by the worker.
    try:
        analyzer = GroqAnalyzer.from_environment()
    except ValueError as exc:
        parser.error(str(exc))
    try:
        factory = session_factory()
        _check_database_revision(factory)
        with analyzer, TelemetryGateway() as gateway:
            worker_id = str(uuid.uuid4())
            while True:
                outcome = run_once(factory, gateway, analyzer, worker_id,
                                   investigation_id=str(args.investigation_id) if args.investigation_id else None)
                logger.info("worker_cycle", extra={"outcome": outcome})
                if args.once or outcome != "IDLE":
                    print(outcome, flush=True)
                if args.once:
                    return 0 if outcome in {"DONE", "IDLE", "STALE"} else 1
                time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        if session_factory.cache_info().currsize:
            session_factory().kw["bind"].dispose()
            session_factory.cache_clear()


if __name__ == "__main__":
    raise SystemExit(main())
