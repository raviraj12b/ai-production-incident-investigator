# Phase 05.8: bounded evidence capture

`backend/evidence_pipeline.py` collects at most 25 records per signal from the
Phase 05.7 telemetry gateway: Loki logs, Prometheus request and error rates,
and Jaeger spans. It sorts and deduplicates records and returns a maximum of
100 normalized records for an explicit service and investigation window.

Evidence summaries use known event names, HTTP status codes, rate samples,
and fixed trace descriptions. Raw log messages, request IDs, arbitrary span
names, URL parameters, and telemetry attributes are **not persisted**. The
`evidence` table stores the signal type, UTC observation time, service, safe
summary, source backend, source reference, and optional trace ID. Log source
references include a timestamp and short hash, so they do not copy log text.
Redaction is a whitelist and can lose details; it is intentionally conservative.

The batch also reports deterministic correlations when both a log and a span
have the same trace ID. `NO_LOGS`, `NO_REQUEST_RATE`, `NO_TRACES`, and
`NO_LOG_TRACE_OVERLAP` are **gaps**, not proof that no error occurred. A change
feed has not been added; `CHANGE_FEED_NOT_CONFIGURED` is explicit in every
batch. Search limits and trace sampling can create missing matches. This slice
does not assert causal relationships or contradictions from incomplete signals.

## Transaction boundary

`collect_for_claim(factory, claim, gateway)` uses an existing, valid RUNNING
job claim. It reads the incident service and window, queries telemetry without
holding a database lock across HTTP requests, and then saves rows in one
transaction. `save_evidence` locks the job row, checks the worker ID, attempt,
and unexpired lease, and replaces this investigation's previous unlinked
evidence only after validating the entire new batch. A stale worker returns
`None`/`False` and cannot overwrite rows. An empty retry cannot erase earlier
evidence. Backend failures propagate without a partial commit; the later worker
will decide when to call `fail_claim`.

The product endpoint `GET /api/v1/investigations/{id}/evidence` reads saved
summaries and provenance in pages (`limit` 1–100, `offset` ≥ 0). A new queued
investigation returns `[]` because **no worker process is connected**. This
endpoint does not trigger a collection or complete an investigation.

## Verify on the development machine

```bash
python -m pytest tests/test_evidence_pipeline.py -q
python -m pytest -q
python -m alembic current
```

The migration revision remains `phase05_0002`; no schema change is needed.
The tests use a temporary isolated database and a fake telemetry gateway to
verify redaction, matching trace IDs, GET results, audit counts, and stale
claims. They do **not** verify concurrent claims in PostgreSQL or live Loki,
Prometheus, and Jaeger ingestion. Use the separate Phase 05.7 Windows guide
for live backend checks. Avoid manually claiming a real queued job merely to
test this module: a claim changes its status to RUNNING until processing or
lease expiry, and this slice has no worker completion path.

Phase 05.9 extends the capture audit with a digest of the normalized evidence
set. A retry that reads identical rows records a capture for its own attempt
without replacing those rows. Analysis completion checks this digest and the
attempt number before saving a report.
