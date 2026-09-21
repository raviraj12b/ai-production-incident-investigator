# Phase 05 backend status (05.10 standalone worker)

## Baseline reconciled

The supplied ZIP is a source snapshot through Phase 1 Step 7C, without Git
history. It contains two FastAPI services, controlled dependency failures,
structured logs, request IDs, OTLP traces, and four existing endpoint tests.
The collector has only a `debug` exporter and cannot answer telemetry queries.
`requirements.txt` listed `httpx2`, while the source imports `httpx`; `httpx2`
was removed. The original `/`, `/health`, `/inventory`, dependency controls,
request logging, and tracing entry points were kept.

## Implemented in this snapshot

- Configuration for the dependency URL, request timeout, and PostgreSQL URL.
- Lazy database session creation and disposal on application shutdown; no
  schema creation on startup.
- Initial Alembic migration for incidents, investigations, jobs, evidence,
  hypotheses and evidence links, reports, reviews, audit events, and incident
  creation idempotency.
- `GET /ready` checks database connectivity and migration revision.
- `/api/v1/incidents` creation, retrieval, listing, and limited updates;
  timezone-aware UTC windows, transactional `Idempotency-Key`, audit rows,
  standard product API error envelopes, and a `Location` header.
- Isolated API tests for idempotency, audit, validation, and read/update paths.
- Migration `phase05_0002` adds investigation request idempotency without
  changing the existing incident idempotency table.
- `POST /api/v1/incidents/{id}/investigations` returns `202 Accepted` and
  atomically persists the investigation, job, request record, and audit event.
  GET endpoints expose status and attempts. A second active job is rejected.
- `backend/jobs.py` provides PostgreSQL `FOR UPDATE SKIP LOCKED` claims,
  expiring leases, fenced renewal, and up to three attempts.
- Phase 05.7 adds a bounded internal telemetry gateway for Loki logs,
  Prometheus request/error rate, and Jaeger trace search/detail, together with
  OTLP log export, a queryable Collector config, and `/metrics` on both services.
  See `docs/phase-05-7-telemetry.md` for setup and live checks.
- Phase 05.8 adds bounded, redacted evidence drafts, trace-ID correlation,
  explicit missing-signal gaps, and transactional persistence while a job
  claim remains valid. A read-only API lists saved evidence;
  see `docs/phase-05-8-evidence.md`.
- Phase 05.9 adds a provider-independent result contract, per-attempt evidence
  digest, validation of cited hypotheses, an atomic report/job completion path,
  and a read-only report API; see `docs/phase-05-9-analysis.md`.
- Phase 05.10 connects an explicitly started worker to the gateway, evidence
  capture, one bounded structured Groq model request, and validated completion.
  It also supports a targeted `--once` mode for safer local verification; see
  `docs/phase-05-10-worker.md`.

## Verification

- The project owner reported that the previous eight tests passed, migration
  `phase05_0001` ran, `/ready`, `/health`, and `/inventory` returned 200, and
  an incident POST replay returned the same ID on the development machine.
- This environment has no project Python dependencies, so it cannot run the
  tests or PostgreSQL migration. Run `python -m pip install -r requirements.txt`
  and `python -m pytest -q` on the development machine. The revision remains
  `phase05_0002` and `/ready` should return 200.
- The project owner reported 33 tests passing and migration `phase05_0002`
  with the initial 05.10 worker. The revised Groq adapter tests must be run
  on the development machine. Live connectivity to Loki, Prometheus, and
  Jaeger has not been independently verified here.

The SQLite test for lease transitions does not establish PostgreSQL concurrent
claim safety. Add a PostgreSQL integration test with two workers before
claiming that guarantee is verified.

## Remaining Phase 05 work

1. Run the new worker tests and verify the local Loki, Prometheus, and
   Jaeger gateway with generated traffic if it has not been checked already.
2. Add a PostgreSQL two-worker concurrency test to verify claim safety.
3. Verify one real worker run with live telemetry and a configured model.
   Comparable signals and change/deployment evidence are needed for meaningful
   contradiction analysis.
4. Add reviewer actions and audit transitions with an actual authenticated
   reviewer identity before treating approvals as authoritative.
5. Complete integration, failure, and provenance acceptance tests before
   declaring Phase 05 complete. Authentication and an actual reviewer identity
   are still missing; the present audit actor is the channel label `api`.
