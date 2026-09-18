# Phase 05 backend status (05.7 telemetry gateway groundwork)

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
  expiring leases, fenced renewal, and up to three attempts. The worker
  processor and report completion path are not connected yet.
- Phase 05.7 adds a bounded internal telemetry gateway for Loki logs,
  Prometheus request/error rate, and Jaeger trace search/detail, together with
  OTLP log export, a queryable Collector config, and `/metrics` on both services.
  No worker invokes this gateway yet; see `docs/phase-05-7-telemetry.md`.

## Verification

- The project owner reported that the previous eight tests passed, migration
  `phase05_0001` ran, `/ready`, `/health`, and `/inventory` returned 200, and
  an incident POST replay returned the same ID on the development machine.
- This environment has no project Python dependencies, so it cannot run the
  tests or PostgreSQL migration. Run `python -m pip install -r requirements.txt`
  and `python -m pytest -q` on the development machine. The revision remains
  `phase05_0002` and `/ready` should return 200.
- The project owner reported ten tests passing and `/ready` returning 200
  after 05.6. The new gateway tests, backend connectivity, and binaries must
  still be checked on the development machine.

The SQLite test for lease transitions does not establish PostgreSQL concurrent
claim safety. Add a PostgreSQL integration test with two workers before
claiming that guarantee is verified.

## Remaining Phase 05 work

1. Run the new tests and connect the optional local Loki, Prometheus, and
   Jaeger backends; verify the gateway with generated traffic.
2. Add a PostgreSQL two-worker concurrency test to verify claim safety.
3. Normalize and redact bounded evidence with provenance; implement the
   deterministic correlations and contradiction/missing-evidence logic.
4. Connect the worker processor and report completion transition once evidence
   validation exists; retain lease fencing around all state changes.
5. Add the bounded single-investigator model adapter, report/review endpoints,
   and audit transitions. Keep AI tool access structured and read-only.
6. Complete integration, failure, and provenance acceptance tests before
   declaring Phase 05 complete. Authentication and an actual reviewer identity
   are still missing; the present audit actor is the channel label `api`.
