# Phase 05 backend status

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

## Verification actually performed in this environment

- Python `compileall` passed for source, migration, and tests.
- Pydantic 2.13.5 accepted a valid aware time window and rejected naive and
  reversed windows.
- A structural source check found the same ten table names in the ORM and the
  initial migration.

Runtime tests, a migration against PostgreSQL, and an OpenTelemetry regression
check were **not run**. This environment lacks FastAPI, httpx, SQLAlchemy,
Alembic, psycopg, pytest, and a PostgreSQL server, and package installation
could not reach an index. The presence of test source does not establish that
these tests pass. Run `python -m pytest -q` and `python -m alembic upgrade head`
on the development machine, then verify `/ready`, `/health`, and `/inventory`.

## Remaining Phase 05 work

1. Verify this slice against a real PostgreSQL instance and fix any failures.
2. Add the investigation create/read/status API and a PostgreSQL-backed worker
   with an explicit lease and crash recovery policy.
3. Connect read-only logs/traces/metrics query adapters to an actual queryable
   telemetry backend. The existing debug exporter is insufficient.
4. Normalize and redact bounded evidence with provenance; implement the
   deterministic correlations and contradiction/missing-evidence logic.
5. Add the bounded single-investigator model adapter, report/review endpoints,
   and audit transitions. Keep AI tool access structured and read-only.
6. Complete integration, failure, and provenance acceptance tests before
   declaring Phase 05 complete. Authentication and an actual reviewer identity
   are still missing; the present audit actor is the channel label `api`.
