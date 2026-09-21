# Phase 05.9: validated analysis completion

`backend/analysis_pipeline.py` accepts a provider-independent `AnalysisDraft`.
Each proposed hypothesis must have a nonempty explanation, bounded confidence,
all of the capture's missing-signal gaps, and at least one supporting citation
to an evidence ID belonging to **that investigation**. A proposed contradiction
is recorded only as the analysis provider's declared relationship; this code
cannot establish semantic contradiction or causality. `HIGH` confidence is
blocked while any signal is missing. Missing core signals require `LOW`.

`inconclusive(gaps)` constructs the only accepted result without hypotheses.
Its fixed summary says that the root cause is undetermined and its uncertainty
names the gaps. It is valid even when a successful telemetry query returned no
evidence. Backend outages are still errors, not empty successful captures.

## Completion boundary

`complete_claim(factory, claim, draft)` locks the investigation job and checks
the worker ID, attempt, and live lease. It requires a capture audit for this
attempt whose count and digest match the current evidence rows. It then saves
the report, hypotheses, supporting or declared contradicting links, and audit
event in the same transaction as job `DONE` and investigation
`AWAITING_REVIEW`. Invalid results roll back; a stale claim returns `False`.

`GET /api/v1/investigations/{id}/report` returns a saved report with hypotheses
and cited evidence IDs, or 404 before a report exists. The original evidence
read endpoint can resolve those IDs. There is no public analysis write route,
worker loop, model integration, or reviewer decision route at this checkpoint.
An existing queued investigation still has no report and its report GET should
return 404. Report prose is a provider proposal; citation membership and
length are validated, **not the truth of its causal claims**. Do not use this
demo API with real sensitive incident data before authentication and an output
handling policy are implemented.

## Verify on the development machine

```bash
python -m pytest tests/test_analysis_pipeline.py -q
python -m pytest -q
python -m alembic current
```

The migration revision remains `phase05_0002`; no schema change is required.
The five new tests use SQLite to cover successful completion, the read API,
invalid links/confidence, no-data inconclusive completion, reclaimed attempts,
and modified evidence. These do not prove PostgreSQL two-worker claim safety
or live ingestion from Loki, Prometheus, and Jaeger. The separate Phase 05.7
guide covers live telemetry checks.
