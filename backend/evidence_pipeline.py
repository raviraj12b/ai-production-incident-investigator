"""Bounded evidence capture from read-only telemetry; no report or worker loop.

Raw log bodies and arbitrary span attributes are never written to the product
database. A future worker owns claim/retry scheduling and report generation.
"""

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from backend.jobs import JobClaim, _effective_now, _owns_lease
from backend.models import (
    AuditEvent, Evidence, HypothesisEvidence, Incident, Investigation, InvestigationJob,
)
from backend.telemetry_gateway import Query, SERVICE_RE, TRACE_RE


MAX_PER_SIGNAL = 25
MAX_EVIDENCE = 100
SPAN_RE = re.compile(r"[0-9a-fA-F]{16}\Z")
KNOWN_EVENTS = frozenset({
    "request_completed", "request_failed", "dependency_call_started",
    "dependency_call_failed", "dependency_call_completed", "product_database_error", "log_event",
})
KNOWN_GAPS = frozenset({
    "NO_LOGS", "NO_REQUEST_RATE", "NO_TRACES", "CHANGE_FEED_NOT_CONFIGURED",
    "NO_LOG_TRACE_OVERLAP",
})
LOG_SUMMARY_RE = re.compile(
    "(?:" + "|".join(sorted(KNOWN_EVENTS)) + r")(?: \(HTTP [1-5][0-9]{2}\))?\Z"
)
METRIC_SUMMARY_RE = re.compile(r"(request_rate|error_rate)=[0-9]{1,10}\.[0-9]{4}/s\Z")
LOKI_REF_RE = re.compile(r"loki:[0-9]{1,20}:[0-9a-f]{24}\Z")
JAEGER_REF_RE = re.compile(r"jaeger:[0-9a-f]{32}:[0-9a-f]{16}\Z")


class EvidenceValidationError(ValueError):
    """Telemetry was malformed or the investigation cannot be safely queried."""


class Gateway(Protocol):
    def query_logs(self, query: Query) -> list[dict]: ...
    def query_metrics(self, query: Query, metric: str = "request_rate") -> list[dict]: ...
    def query_traces(self, query: Query) -> list[dict]: ...


@dataclass(frozen=True)
class EvidenceDraft:
    kind: str
    observed_at: datetime
    service: str
    summary: str
    source_backend: str
    source_ref: str
    trace_id: str | None = None


@dataclass(frozen=True)
class Correlation:
    trace_id: str
    log_count: int
    span_count: int


@dataclass(frozen=True)
class EvidenceBatch:
    records: tuple[EvidenceDraft, ...]
    gaps: tuple[str, ...]
    correlations: tuple[Correlation, ...]


def _window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    # SQLite test DB loses timezone metadata; PostgreSQL stores aware timestamps.
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _timestamp_ns(raw: object, query: Query, *, enforce_window: bool = True) -> datetime:
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise EvidenceValidationError("Invalid telemetry nanosecond timestamp")
    try:
        nanoseconds = int(raw)
        if str(raw) != str(nanoseconds) or nanoseconds < 0:
            raise ValueError("Invalid timestamp")
        observed = datetime.fromtimestamp(nanoseconds // 1_000_000_000, timezone.utc)
        observed += timedelta(microseconds=(nanoseconds % 1_000_000_000) // 1000)
    except (ValueError, OverflowError, OSError) as exc:
        raise EvidenceValidationError("Invalid telemetry nanosecond timestamp") from exc
    if enforce_window and not query.start <= observed <= query.end:
        raise EvidenceValidationError("Telemetry record outside investigation window")
    return observed


def _metric_timestamp(raw: object, query: Query) -> datetime:
    if isinstance(raw, bool) or not isinstance(raw, (float, int)) or not math.isfinite(raw):
        raise EvidenceValidationError("Invalid metric timestamp")
    try:
        observed = datetime.fromtimestamp(raw, timezone.utc)
    except (ValueError, OverflowError, OSError) as exc:
        raise EvidenceValidationError("Invalid metric timestamp") from exc
    if not query.start <= observed <= query.end:
        raise EvidenceValidationError("Metric outside investigation window")
    return observed


def _trace_id(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not TRACE_RE.fullmatch(raw):
        raise EvidenceValidationError("Invalid telemetry trace ID")
    return raw.lower().zfill(32)


def _service(raw: object) -> str:
    if not isinstance(raw, str) or not SERVICE_RE.fullmatch(raw):
        raise EvidenceValidationError("Invalid telemetry service")
    return raw


def _hash_ref(*values: object) -> str:
    # Only the digest is persisted; log bodies/request IDs may contain secrets.
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()[:24]


def evidence_digest(records) -> str:
    """Compare saved normalized rows to the exact set captured by an attempt."""
    normalized = []
    for row in records:
        observed = row.observed_at
        if observed.tzinfo is None:  # SQLite test database drops timezone metadata.
            observed = observed.replace(tzinfo=timezone.utc)
        normalized.append((
            row.kind, observed.astimezone(timezone.utc).isoformat(), row.service,
            row.summary, row.source_backend, row.source_ref, row.trace_id,
        ))
    payload = json.dumps(sorted(normalized, key=lambda row: json.dumps(row)), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _log(row: dict, query: Query) -> EvidenceDraft:
    if row.get("source") != "loki" or row.get("service") != query.service:
        raise EvidenceValidationError("Unexpected log source")
    observed = _timestamp_ns(row.get("timestamp_ns"), query)
    trace_id = _trace_id(row.get("trace_id"))
    event = row.get("event") or row.get("message")
    event = event if isinstance(event, str) and event in KNOWN_EVENTS else "log_event"
    status = row.get("status_code")
    if isinstance(status, bool) or (status is not None and (not str(status).isdigit() or not 100 <= int(status) <= 599)):
        status = None
    summary = event + (f" (HTTP {int(status)})" if status is not None else "")
    source_ref = "loki:" + str(row["timestamp_ns"]) + ":" + _hash_ref(
        query.service, row["timestamp_ns"], row.get("message"), row.get("request_id"), trace_id,
    )
    return EvidenceDraft("LOG", observed, query.service, summary, "loki", source_ref, trace_id)


def _metric(row: dict, query: Query, metric: str) -> EvidenceDraft:
    if row.get("source") != "prometheus" or row.get("service") != query.service or row.get("metric") != metric:
        raise EvidenceValidationError("Unexpected metric source")
    observed = _metric_timestamp(row.get("timestamp"), query)
    value = row.get("value")
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value < 1_000_000_000):
        raise EvidenceValidationError("Invalid metric sample")
    summary = f"{metric}={value:.4f}/s"
    source_ref = f"prometheus:{metric}:{observed.isoformat()}"
    return EvidenceDraft("METRIC", observed, query.service, summary, "prometheus", source_ref)


def _span(row: dict, query: Query) -> EvidenceDraft | None:
    if row.get("source") != "jaeger":
        raise EvidenceValidationError("Unexpected trace source")
    observed = _timestamp_ns(row.get("start_time_unix_nano"), query, enforce_window=False)
    # Jaeger returns every span from a matched trace, including spans outside
    # the searched interval. Keep only spans in the investigation window.
    if not query.start <= observed <= query.end:
        return None
    service = _service(row.get("service"))
    trace_id = _trace_id(row.get("trace_id"))
    span_id = row.get("span_id")
    if trace_id is None or not isinstance(span_id, str) or not SPAN_RE.fullmatch(span_id):
        raise EvidenceValidationError("Invalid trace span")
    # Span names can embed URLs/IDs and other user data; persist only safe kind.
    summary = "Trace span observed"
    return EvidenceDraft(
        "TRACE", observed, service, summary, "jaeger",
        f"jaeger:{trace_id}:{span_id.lower()}", trace_id,
    )


def collect_evidence(gateway: Gateway, service: str, start: datetime, end: datetime) -> EvidenceBatch:
    """Collect an investigation window without writing a product row."""
    start, end = _window(start, end)
    query = Query(service, start, end, limit=MAX_PER_SIGNAL)
    try:
        logs = gateway.query_logs(query)
        rates = gateway.query_metrics(query, "request_rate")
        errors = gateway.query_metrics(query, "error_rate")
        spans = gateway.query_traces(query)
        if any(not isinstance(rows, list) or len(rows) > MAX_PER_SIGNAL
               for rows in (logs, rates, errors, spans)):
            raise EvidenceValidationError("Telemetry response exceeds item cap")
        records = ([_log(row, query) for row in logs]
                   + [_metric(row, query, "request_rate") for row in rates]
                   + [_metric(row, query, "error_rate") for row in errors]
                   + [record for row in spans if (record := _span(row, query)) is not None])
    except (ValueError, TypeError, KeyError) as exc:
        raise EvidenceValidationError("Invalid telemetry for evidence capture") from exc

    if len(records) > MAX_EVIDENCE:
        raise EvidenceValidationError("Evidence exceeds item cap")
    # Stable order and IDs make an interrupted capture safe to retry.
    unique = {}
    for record in records:
        key = (record.kind, record.service, record.source_ref)
        if key in unique and unique[key] != record:
            raise EvidenceValidationError("Conflicting telemetry for the same source")
        unique[key] = record
    records = sorted(unique.values(), key=lambda r: (r.observed_at, r.kind, r.source_ref))
    gaps = []
    if not logs:
        gaps.append("NO_LOGS")
    if not rates:
        gaps.append("NO_REQUEST_RATE")
    if not any(r.kind == "TRACE" for r in records):
        gaps.append("NO_TRACES")
    gaps.append("CHANGE_FEED_NOT_CONFIGURED")
    log_ids = {r.trace_id for r in records if r.kind == "LOG" and r.trace_id}
    trace_ids = {r.trace_id for r in records if r.kind == "TRACE"}
    shared = sorted(log_ids & trace_ids)
    if log_ids and trace_ids and not shared:
        gaps.append("NO_LOG_TRACE_OVERLAP")
    correlations = tuple(Correlation(
        trace_id=trace_id,
        log_count=sum(r.kind == "LOG" and r.trace_id == trace_id for r in records),
        span_count=sum(r.kind == "TRACE" and r.trace_id == trace_id for r in records),
    ) for trace_id in shared)
    return EvidenceBatch(tuple(records), tuple(gaps), correlations)


def save_evidence(
    factory: sessionmaker[Session], claim: JobClaim, batch: EvidenceBatch, *,
    now: datetime | None = None,
) -> bool:
    """Replace one attempt's evidence atomically while its lease is valid."""
    now = _effective_now(now)
    if len(batch.records) > MAX_EVIDENCE or any(gap not in KNOWN_GAPS for gap in batch.gaps):
        raise EvidenceValidationError("Evidence exceeds item cap")
    with factory.begin() as session:
        job = session.scalar(select(InvestigationJob)
                             .where(InvestigationJob.investigation_id == claim.investigation_id)
                             .with_for_update())
        if job is None or not _owns_lease(job, claim, now):
            return False
        investigation = session.get(Investigation, claim.investigation_id)
        if investigation is None or investigation.status != "RUNNING":
            return False
        window_start, window_end = _window(investigation.window_start, investigation.window_end)
        for record in batch.records:
            if (record.kind not in {"LOG", "TRACE", "METRIC"}
                    or record.source_backend != {"LOG": "loki", "TRACE": "jaeger", "METRIC": "prometheus"}.get(record.kind)
                    or not isinstance(record.observed_at, datetime)
                    or record.observed_at.tzinfo is None
                    or record.observed_at.utcoffset() is None
                    or not isinstance(record.service, str) or not SERVICE_RE.fullmatch(record.service)
                    or not isinstance(record.summary, str) or len(record.summary) > 1000
                    or not isinstance(record.source_ref, str) or len(record.source_ref) > 500
                    or not window_start <= record.observed_at <= window_end
                    or (record.trace_id is not None and not re.fullmatch(r"[0-9a-f]{32}", record.trace_id))):
                raise EvidenceValidationError("Invalid evidence record")
            if record.kind == "LOG" and not (LOG_SUMMARY_RE.fullmatch(record.summary)
                                               and LOKI_REF_RE.fullmatch(record.source_ref)):
                raise EvidenceValidationError("Invalid log evidence")
            if record.kind == "TRACE" and not (record.summary == "Trace span observed"
                                                 and JAEGER_REF_RE.fullmatch(record.source_ref)
                                                 and record.trace_id == record.source_ref.split(":")[1]):
                raise EvidenceValidationError("Invalid trace evidence")
            if record.kind == "METRIC":
                match = METRIC_SUMMARY_RE.fullmatch(record.summary)
                if (match is None or record.trace_id is not None
                        or record.source_ref != f"prometheus:{match.group(1)}:{record.observed_at.isoformat()}"):
                    raise EvidenceValidationError("Invalid metric evidence")
        existing = session.scalars(select(Evidence)
                                   .where(Evidence.investigation_id == claim.investigation_id)).all()
        if existing and not batch.records:
            raise EvidenceValidationError("Refusing to replace evidence with an empty capture")

        def signature(row):
            observed = row.observed_at
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            return (row.kind, observed.astimezone(timezone.utc), row.service,
                    row.summary, row.source_backend, row.source_ref, row.trace_id)

        if existing and Counter(map(signature, existing)) == Counter(map(signature, batch.records)):
            # A reclaimed job must record that its *new* attempt checked this
            # capture; completion is fenced to the current attempt's audit.
            prior = session.scalar(select(AuditEvent).where(
                AuditEvent.investigation_id == claim.investigation_id,
                AuditEvent.action == "EVIDENCE_CAPTURED",
            ).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1))
            digest = evidence_digest(batch.records)
            if (prior is None or prior.detail.get("attempt") != claim.attempt
                    or prior.detail.get("evidence_digest") != digest):
                session.add(AuditEvent(
                    incident_id=investigation.incident_id,
                    investigation_id=investigation.id,
                    action="EVIDENCE_CAPTURED", actor="worker",
                    detail={"attempt": claim.attempt, "record_count": len(batch.records),
                            "correlation_count": len(batch.correlations), "gaps": list(batch.gaps),
                            "evidence_digest": digest},
                ))
            return True
        linked = session.scalar(select(HypothesisEvidence.evidence_id)
                                .join(Evidence, Evidence.id == HypothesisEvidence.evidence_id)
                                .where(Evidence.investigation_id == claim.investigation_id).limit(1))
        if linked is not None:
            raise EvidenceValidationError("Cannot replace evidence linked to a hypothesis")
        session.execute(delete(Evidence).where(Evidence.investigation_id == claim.investigation_id))
        session.add_all(Evidence(
            investigation_id=claim.investigation_id, kind=r.kind,
            observed_at=r.observed_at, service=r.service, summary=r.summary,
            source_backend=r.source_backend, source_ref=r.source_ref,
            trace_id=r.trace_id,
        ) for r in batch.records)
        session.add(AuditEvent(
            incident_id=investigation.incident_id,
            investigation_id=investigation.id,
            action="EVIDENCE_CAPTURED", actor="worker",
            detail={"attempt": claim.attempt, "record_count": len(batch.records),
                    "correlation_count": len(batch.correlations), "gaps": list(batch.gaps),
                    "evidence_digest": evidence_digest(batch.records)},
        ))
        return True


def collect_for_claim(
    factory: sessionmaker[Session], claim: JobClaim, gateway: Gateway,
) -> EvidenceBatch | None:
    """Read without locking across HTTP calls; recheck lease before committing."""
    with factory() as session:
        job = session.get(InvestigationJob, claim.investigation_id)
        if job is None or not _owns_lease(job, claim, _effective_now(None)):
            return None
        investigation = session.get(Investigation, claim.investigation_id)
        incident = session.get(Incident, investigation.incident_id) if investigation else None
        if incident is None or investigation.status != "RUNNING":
            return None
        service = incident.service
        start, end = investigation.window_start, investigation.window_end
    batch = collect_evidence(gateway, service, start, end)
    return batch if save_evidence(factory, claim, batch) else None
