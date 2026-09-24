# Phase 06.9 browser and live-integration verification

Phase 06.9 separates two different claims:

1. fixture-driven Playwright tests verify browser behavior against controlled
   HTTP contracts;
2. the opt-in live test verifies the real local PostgreSQL/API/telemetry/worker
   path.

Passing the fixture tests does not prove that the backend, telemetry services,
model adapter, or worker are operational.

## Install the browser test dependency

From `frontend/`:

```powershell
npm install
npm run test:e2e:install
```

The project pins `@playwright/test` to `1.63.0`. Browser binaries are installed
locally by Playwright and are not committed.

## Run controlled browser tests

```powershell
npm run test:e2e
```

This command starts Vite and runs:

- a desktop incident-intake-to-review workflow using controlled HTTP fixtures;
- a real 320 CSS pixel browser project that checks horizontal overflow and
  keyboard mobile-navigation behavior.

The live test is skipped unless `E2E_LIVE=1` is explicitly set. Fixture tests
must never be reported as real backend integration.

## Prepare the real local stack

Before running the live test, verify all of the following independently:

- PostgreSQL is reachable through `DATABASE_URL`;
- `python -m alembic current` reports `phase05_0002 (head)`;
- the dependency service is running on port `8001`;
- Loki, Jaeger, and the queryable Collector configuration are running;
- the FastAPI process is running on port `8000` with `REVIEWER_ID` and
  `REVIEWER_API_KEY` configured;
- `/ready` returns `200`;
- the standalone worker is running with the same database, a valid
  `GROQ_API_KEY`, and reachable telemetry backends;
- the frontend is not publicly exposed because product-wide authentication is
  still absent.

Use the existing Phase 05 telemetry, worker, and reviewer documentation for
the service-specific startup commands. The browser test does not start or
silently replace those services.

## Run the live workflow

In PowerShell, from `frontend/`, place the reviewer key only in the current
terminal process:

```powershell
$secureReviewerKey = Read-Host "Reviewer API key" -AsSecureString
$env:E2E_REVIEWER_API_KEY = [Net.NetworkCredential]::new('', $secureReviewerKey).Password
$env:E2E_LIVE = "1"
npm run test:e2e:live
Remove-Item Env:E2E_REVIEWER_API_KEY
Remove-Item Env:E2E_LIVE
```

The key is read by Playwright and typed into the memory-only credential field.
It must not be added to source, `.env`, command history, URLs, screenshots,
traces, or committed test artifacts. The live suite explicitly disables
Playwright screenshots, video, and tracing before the credential is entered.

The live test creates a real incident, queues a real investigation, waits up to
five minutes by default for `AWAITING_REVIEW`, and submits an immutable
`INCONCLUSIVE` review. Because the API has no supported delete endpoint, this
test leaves its auditable incident and review in the local database. Run it
against a development database only.

To allow a longer worker cycle, set a millisecond timeout before the command:

```powershell
$env:E2E_TIMEOUT_MS = "600000"
```

Remove that variable afterward if it was set.

## Required evidence before closing Phase 06.9

Record all of these results:

- frontend formatting, lint, typecheck, unit/component tests, build, and audit;
- fixture Playwright result, including the 320 px project;
- backend regression result;
- PostgreSQL concurrency test result with `TEST_DATABASE_URL` configured;
- `phase05_0002 (head)` from Alembic;
- live Playwright result against the running API and worker.

If any item was skipped or could not start, report it as unverified rather than
as a pass.
