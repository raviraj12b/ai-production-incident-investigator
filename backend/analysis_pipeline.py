"""Validate cited analysis and finish a leased investigation atomically.

An analysis provider can propose a result, but it cannot write database rows or
query telemetry. A later worker will call this boundary after evidence capture.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.evidence_pipeline import KNOWN_GAPS, evidence_digest
from backend.jobs import JobClaim, _effective_now, _owns_lease
from backend.models import (
    AuditEvent, Evidence, Hypothesis, HypothesisEvidence, Investigation,
    InvestigationJob, Report,
)


INCONCLUSIVE_SUMMARY = "Root cause undetermined from available evidence."
MAX_HYPOTHESES = 3
MAX_LINKS = 12


class AnalysisValidationError(ValueError):
    """An analysis is malformed, uncited, or inconsistent with captured evidence."""


@dataclass(frozen=True)
class EvidenceLinkDraft:
    evidence_id: str
    relation: str


@dataclass(frozen=True)
class HypothesisDraft:
    explanation: str
    confidence: str
    missing_evidence: tuple[str, ...]
    links: tuple[EvidenceLinkDraft, ...]


@dataclass(frozen=True)
class AnalysisDraft:
    summary: str
    uncertainty: str
    hypotheses: tuple[HypothesisDraft, ...]


def inconclusive(gaps: tuple[str, ...]) -> AnalysisDraft:
    """A safe result when no supported hypothesis can be made."""
    if any(not isinstance(gap, str) or gap not in KNOWN_GAPS for gap in gaps):
        raise AnalysisValidationError("Unknown evidence gap")
    suffix = ", ".join(sorted(set(gaps))) if gaps else "No supported hypothesis"
    return AnalysisDraft(INCONCLUSIVE_SUMMARY, f"Evidence limits: {suffix}.", ())


def _bounded_text(value: object, max_length: int) -> bool:
    return (isinstance(value, str) and value == value.strip()
            and 1 <= len(value) <= max_length
            and all(char.isprintable() for char in value))


def _validate(
    draft: AnalysisDraft, evidence: dict[str, Evidence], gaps: tuple[str, ...],
) -> None:
    if not isinstance(draft, AnalysisDraft):
        raise AnalysisValidationError("Expected an analysis draft")
    if not _bounded_text(draft.summary, 1000) or not _bounded_text(draft.uncertainty, 1000):
        raise AnalysisValidationError("Invalid report text")
    if not isinstance(draft.hypotheses, tuple) or len(draft.hypotheses) > MAX_HYPOTHESES:
        raise AnalysisValidationError("Too many hypotheses")
    if not draft.hypotheses:
        if draft != inconclusive(gaps):
            raise AnalysisValidationError("Inconclusive reports must use the fixed evidence summary")
        return
    if not evidence:
        raise AnalysisValidationError("Hypotheses require captured evidence")
    if any(gap not in draft.uncertainty for gap in gaps):
        raise AnalysisValidationError("The report must identify all recorded evidence gaps")

    total_links = 0
    for hypothesis in draft.hypotheses:
        if not isinstance(hypothesis, HypothesisDraft):
            raise AnalysisValidationError("Invalid hypothesis")
        if not _bounded_text(hypothesis.explanation, 2000):
            raise AnalysisValidationError("Invalid hypothesis explanation")
        if not isinstance(hypothesis.confidence, str) or hypothesis.confidence not in {"LOW", "MEDIUM", "HIGH"}:
            raise AnalysisValidationError("Invalid confidence")
        # Missing signals are not positive evidence. Never allow HIGH with a
        # missing signal, and require LOW when a core signal is absent.
        if (hypothesis.confidence == "HIGH" and gaps
                or hypothesis.confidence != "LOW"
                and set(gaps) & {"NO_LOGS", "NO_REQUEST_RATE", "NO_TRACES", "NO_LOG_TRACE_OVERLAP"}):
            raise AnalysisValidationError("Confidence exceeds available evidence")
        missing = hypothesis.missing_evidence
        if (not isinstance(missing, tuple) or any(not isinstance(gap, str) for gap in missing)
                or len(missing) != len(set(missing))
                or set(missing) != set(gaps)):
            raise AnalysisValidationError("Hypothesis must disclose recorded gaps")
        links = hypothesis.links
        if not isinstance(links, tuple) or not 1 <= len(links) <= MAX_LINKS:
            raise AnalysisValidationError("Hypothesis must cite bounded evidence")
        if any(not isinstance(link, EvidenceLinkDraft) for link in links):
            raise AnalysisValidationError("Invalid evidence link")
        if any(not isinstance(link.evidence_id, str) or not isinstance(link.relation, str)
               for link in links):
            raise AnalysisValidationError("Invalid evidence link")
        if len({link.evidence_id for link in links}) != len(links):
            raise AnalysisValidationError("Duplicate evidence reference")
        if not any(link.relation == "SUPPORTS" for link in links):
            raise AnalysisValidationError("Hypothesis requires supporting evidence")
        for link in links:
            if link.relation not in {"SUPPORTS", "CONTRADICTS"} or link.evidence_id not in evidence:
                raise AnalysisValidationError("Evidence reference is outside this investigation")
        total_links += len(links)
    if total_links > MAX_LINKS:
        raise AnalysisValidationError("Too many evidence links")


def complete_claim(
    factory: sessionmaker[Session], claim: JobClaim, draft: AnalysisDraft,
    *, now: datetime | None = None,
) -> bool:
    """Return False for a stale lease; invalid results roll back without finishing."""
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
        if investigation is None or investigation.status != "RUNNING":
            return False
        # A capture for this attempt is required even if it contained zero rows.
        current_capture = session.scalar(select(AuditEvent).where(
            AuditEvent.investigation_id == claim.investigation_id,
            AuditEvent.action == "EVIDENCE_CAPTURED",
        ).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(1))
        if current_capture is None or current_capture.detail.get("attempt") != claim.attempt:
            raise AnalysisValidationError("Capture evidence for this attempt before analysis")
        gaps = tuple(current_capture.detail.get("gaps", ()))
        if (any(not isinstance(gap, str) or gap not in KNOWN_GAPS for gap in gaps)
                or len(gaps) != len(set(gaps))):
            raise AnalysisValidationError("Invalid captured evidence gaps")
        rows = session.scalars(select(Evidence).where(
            Evidence.investigation_id == claim.investigation_id,
        )).all()
        evidence = {row.id: row for row in rows}
        if (len(evidence) != current_capture.detail.get("record_count")
                or evidence_digest(rows) != current_capture.detail.get("evidence_digest")):
            raise AnalysisValidationError("Captured evidence changed since the claim")
        _validate(draft, evidence, gaps)

        report = Report(
            investigation_id=investigation.id,
            summary=draft.summary, uncertainty=draft.uncertainty,
        )
        session.add(report)
        for proposed in draft.hypotheses:
            hypothesis = Hypothesis(
                investigation_id=investigation.id,
                explanation=proposed.explanation,
                confidence=proposed.confidence,
                missing_evidence=list(proposed.missing_evidence),
            )
            session.add(hypothesis)
            session.flush()
            session.add_all(HypothesisEvidence(
                hypothesis_id=hypothesis.id, evidence_id=link.evidence_id,
                relation=link.relation,
            ) for link in proposed.links)
        investigation.status = "AWAITING_REVIEW"
        investigation.finished_at = now
        investigation.error = None
        job.status = "DONE"
        job.worker_id = None
        job.lease_until = None
        session.add(AuditEvent(
            incident_id=investigation.incident_id,
            investigation_id=investigation.id,
            action="INVESTIGATION_AWAITING_REVIEW", actor="worker",
            detail={"attempt": claim.attempt, "hypothesis_count": len(draft.hypotheses),
                    "evidence_count": len(evidence), "gaps": list(gaps)},
        ))
        return True
