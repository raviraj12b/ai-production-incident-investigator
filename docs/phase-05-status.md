# Phase 05 backend status (05.6 queue groundwork)

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

## Verification

- The project owner reported that the previous eight tests passed, migration
  `phase05_0001` ran, `/ready`, `/health`, and `/inventory` returned 200, and
  an incident POST replay returned the same ID on the development machine.
- This environment cannot run the new API/worker tests or the PostgreSQL
  migration. Run `python -m pytest -q`, then `python -m alembic upgrade head`
  and `python -m alembic current` on the development machine. The revision
  must be `phase05_0002` for `/ready` to return 200.

The SQLite test for lease transitions does not establish PostgreSQL concurrent
claim safety. Add a PostgreSQL integration test with two workers before
claiming that guarantee is verified.

## Remaining Phase 05 work

1. Run the new tests and migration against the development PostgreSQL instance;
   verify 202/replay/409/status responses.
2. Connect read-only logs/traces/metrics query adapters to an actual queryable
   telemetry backend. The existing debug exporter is insufficient.
3. Normalize and redact bounded evidence with provenance; implement the
   deterministic correlations and contradiction/missing-evidence logic.
4. Connect the worker processor and report completion transition once evidence
   validation exists; retain lease fencing around all state changes.
5. Add the bounded single-investigator model adapter, report/review endpoints,
   and audit transitions. Keep AI tool access structured and read-only.
6. Complete integration, failure, and provenance acceptance tests before
   declaring Phase 05 complete. Authentication and an actual reviewer identity
   are still missing; the present audit actor is the channel label `api`.
