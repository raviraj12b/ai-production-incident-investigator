# AI Production Incident Investigator

Development snapshot through **Phase 05.10 (standalone investigation worker)**.

This repository contains a small production-like FastAPI system used to generate and investigate controlled incidents. At this checkpoint it includes:

- Main FastAPI service (`incident-demo-api`)
- Downstream dependency service
- Health and inventory endpoints
- Structured JSON logging
- Request-ID propagation across services
- Outgoing dependency-call observability
- Controlled downstream incidents: latency and HTTP 500
- Real service-unavailable simulation by stopping the dependency process
- OpenTelemetry distributed tracing for FastAPI + HTTPX
- OTLP trace export to an OpenTelemetry Collector
- Trace/span correlation fields added to structured JSON logs
- PostgreSQL product schema and versioned Alembic migration
- Manual incident intake API with transactional idempotency and audit events
- Database readiness check; existing `/health` still checks the demo process
- `202 Accepted` investigation creation, idempotent retries, and status reads
- PostgreSQL-backed job claims with expiry, lease renewal, and bounded retries

The existing simulator is separate from the product schema. Jobs can be queued,
claimed, renewed, and failed by the worker primitives in `backend/jobs.py`.
The standalone worker is **never started by the FastAPI process**. A
queued job has not collected telemetry or produced a report until the worker
runs and its telemetry backends are reachable. The original
Collector `debug` exporter is **not a queryable telemetry store**.

Phase 05.7 adds bounded internal telemetry reads and a separate optional
Collector configuration for Loki logs and Jaeger traces. Both services expose
Prometheus metrics. For Windows setup and verification, see
[`docs/phase-05-7-telemetry.md`](docs/phase-05-7-telemetry.md). Evidence capture
can call these reads after claiming a job; no worker starts this automatically.

Phase 05.8 adds evidence normalization, conservative redaction, trace-ID
correlation, and lease-fenced persistence for a claimed job. The read-only
`GET /api/v1/investigations/{id}/evidence` endpoint returns stored summaries;
see [`docs/phase-05-8-evidence.md`](docs/phase-05-8-evidence.md).

Phase 05.9 validates cited analysis results and atomically saves a report,
hypotheses, evidence links, and the `AWAITING_REVIEW` transition for a valid
worker claim. `GET /api/v1/investigations/{id}/report` reads a saved result;
see [`docs/phase-05-9-analysis.md`](docs/phase-05-9-analysis.md).

Phase 05.10 connects a separate worker command to the evidence and report
pipeline. A Groq adapter accepts only normalized, bounded evidence. The
worker requires `GROQ_API_KEY` and uses `openai/gpt-oss-20b` on Groq by default;
see [`docs/phase-05-10-worker.md`](docs/phase-05-10-worker.md) before running it.

Phase 05.11 adds an opt-in PostgreSQL integration test for simultaneous job
claims. Set `TEST_DATABASE_URL` and follow
[`docs/phase-05-11-postgresql-concurrency.md`](docs/phase-05-11-postgresql-concurrency.md)
to verify the real `FOR UPDATE SKIP LOCKED` behavior; ordinary SQLite tests do
not establish that guarantee.

Phase 05.12 adds the protected human decision after report generation. A
configured reviewer can accept, reject, or mark a report inconclusive through
an idempotent review resource; see
[`docs/phase-05-12-review.md`](docs/phase-05-12-review.md). This authenticates
the review action only and is not product-wide API authentication.

Phase 05.13 adds final workflow-level backend acceptance tests for successful
cited analysis and review, telemetry failure, and invalid model provenance;
see [`docs/phase-05-13-acceptance.md`](docs/phase-05-13-acceptance.md). Passing
these tests completes the local Phase 05 backend checkpoint, not production
deployment hardening.

## Set up the product database

Install Python 3.11+ and PostgreSQL, create a database, then install packages:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Activate the virtual environment first if `python` does not point to it. Set
`DATABASE_URL` to a URL using the `postgresql+psycopg://` scheme, for example
`postgresql+psycopg://user:password@127.0.0.1:5432/incident_investigator`.
Do not commit credentials to the repository. Run the migration **before**
starting the product API:

In Windows PowerShell, set the variable for the current terminal with
`$env:DATABASE_URL = "postgresql+psycopg://user:password@127.0.0.1:5432/incident_investigator"`.

```bash
python -m alembic upgrade head
python -m uvicorn backend.main:app --port 8000
```

`GET /ready` returns 200 only when the database is reachable and at migration
`phase05_0002`. Without `DATABASE_URL`, the original demo routes still start;
product routes return 503 and `/ready` returns 503. Database tables are never
created automatically at startup.

Create an incident with `POST /api/v1/incidents` and an `Idempotency-Key` header:

```json
{"title":"Inventory errors","service":"incident-demo-api","severity":"HIGH","window_start":"2026-09-17T10:00:00Z","window_end":"2026-09-17T10:15:00Z"}
```

The response is 201 with an incident ID and `Location` header. Retrying with
the same key and payload returns the same incident. Reusing a key with another
payload returns 409. `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}` and
`PATCH /api/v1/incidents/{id}` are available; PATCH edits title, description,
or severity. Review completion does not automatically close the operational
incident. Non-review writes still use `actor="api"` as a channel label; the
review endpoint records the configured authenticated reviewer identity.

Create a job by posting `{}` or a `focus` to the nested endpoint, with a new
`Idempotency-Key` for each intended investigation:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/incidents/INCIDENT_ID/investigations \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: investigation-001' \
  -d '{"focus":"Inventory dependency errors"}'
curl -i http://127.0.0.1:8000/api/v1/investigations/INVESTIGATION_ID
```

Replace the IDs with values returned by the API. The POST returns 202 and a
`Location` header. A retry with the same key and body returns the same ID;
another key while an investigation is queued or running returns 409. The job
stays `QUEUED` until you start the standalone worker.

## Runtime ports

- Main API: `8000`
- Dependency service: `8001`
- OpenTelemetry Collector OTLP/HTTP: `4318`

## Run tests

```bash
python -m pytest -q
```

The project owner reported 33 tests passing with the initial Phase 05.10
worker. Run the updated Groq adapter tests as part of the full suite. There
is no new migration:
`python -m alembic current` should still report `phase05_0002` for `/ready`.

## Run OpenTelemetry Collector

Example with the standalone Windows collector binary:

```powershell
.\otelcol.exe --config "D:\ai-production-incident-investigator\telemetry\otel-collector-config.yaml"
```

## Run services with tracing enabled

Dependency service:

```bash
OTEL_ENABLED=true python -m uvicorn dependency_service.main:app --port 8001
```

Main API:

```bash
OTEL_ENABLED=true python -m uvicorn backend.main:app --port 8000
```

## Verify a distributed request

```bash
curl -H "X-Request-ID: correlation-test-001" http://127.0.0.1:8000/inventory
```

## Controlled incidents

Set dependency to HTTP 500 mode:

```bash
curl -X POST http://127.0.0.1:8001/control/mode/error
```

Set dependency to latency mode:

```bash
curl -X POST http://127.0.0.1:8001/control/mode/latency
```

Reset:

```bash
curl -X POST http://127.0.0.1:8001/control/mode/normal
```

To simulate dependency unavailability, stop the dependency service process while keeping the main API running.
