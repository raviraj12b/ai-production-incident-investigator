# Phase 05.13: backend acceptance workflows

This final Phase 05 slice adds three workflow-level tests in
`tests/test_acceptance.py`. They connect the HTTP API, durable job state,
worker, evidence capture, result validation, report reads, authenticated
review, and audit rows rather than testing those components in isolation.

## Acceptance coverage

1. **Successful cited workflow**
   - Creates an incident and queues an investigation through the API.
   - Runs one worker with normalized fake telemetry and a provider-independent
     analyzer.
   - Confirms raw sensitive input is not persisted or sent to the analyzer.
   - Confirms every report citation belongs to the saved investigation
     evidence and the capture digest still matches those rows.
   - Authenticates a reviewer, completes the investigation, verifies the audit
     actions, and confirms reviewing an analysis does not close the incident.
2. **Telemetry outage**
   - Confirms an unavailable backend schedules a retry and never calls the
     analyzer, stores evidence, creates a report, or allows a review.
3. **Invalid model citation**
   - Confirms a citation outside the investigation produces `RESULT_INVALID`,
     preserves the safe captured evidence for diagnosis/retry, and creates no
     report, evidence link, or review.

## Run locally

Keep the PostgreSQL integration variable enabled so the full suite also checks
real `FOR UPDATE SKIP LOCKED` behavior:

```bash
export TEST_DATABASE_URL="$DATABASE_URL"
python -m pytest -q tests/test_acceptance.py
python -m pytest -q
python -m alembic current
```

Expected after this slice:

```text
3 passed
41 passed
phase05_0002 (head)
```

No migration or runtime behavior changes are introduced by Phase 05.13.

## Claim boundary

A passing suite completes the Phase 05 **local backend implementation and
acceptance checkpoint** together with the previously recorded live telemetry,
Groq worker, reviewer, and PostgreSQL concurrency checks. It does not make the
application production-ready. Product-wide authentication, authorization,
secret management, TLS, deployment hardening, a configured change feed, and
external load/security testing remain outside this checkpoint. The acceptance
tests mock telemetry and the model; the earlier live validation covers actual
local Loki, Prometheus, Jaeger, Collector, and Groq connectivity.
