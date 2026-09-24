# Phase 06 frontend status

The re-locked frontend source of truth is maintained in
`docs/phase-06-01-frontend-requirements.md`. Implementation changes must remain
within its product, evidence, API, authentication, and safety boundaries.

## Phase 06.1 — requirements re-locked

Frontend requirements were reconciled against project chats 00–04 and the verified Phase 05 HTTP contract. The browser is a thin evidence-presentation client and does not perform retrieval, correlation, confidence calculation, root-cause analysis, dependency inference, ground-truth lookup, or remediation.

## Phase 06.2 — scaffold and design foundation

Implemented:

- `frontend/` React and TypeScript application using Vite;
- strict TypeScript project configuration;
- React Router route structure for incident and investigation pages;
- TanStack Query provider with conservative defaults;
- Tailwind design foundation and responsive desktop/mobile shell;
- explicit unconnected API state with no fabricated incidents or conclusions;
- keyboard focus, skip navigation, semantic landmarks, 320 px minimum support, and reduced-motion behavior;
- ESLint, Prettier, Vitest, and Testing Library configuration;
- initial render, navigation, and deep-link tests;
- Vite development proxies for the FastAPI product routes.

Not implemented in this checkpoint:

- API schema generation or network client;
- incident forms or data reads;
- investigation polling;
- evidence/report/review data rendering;
- browser E2E tests;
- product authentication.

## Phase 06.2 verification

Executed successfully in the checkpoint workspace with Node `24.19.0` and npm `11.9.0`:

- `npm run format:check`
- `npm run lint`
- `npm run typecheck`
- `npm test` — 1 test file, 3 tests passed
- `npm run build` — Vite production build completed

The first test execution exposed missing DOM cleanup between Vitest cases. The shared test setup now performs cleanup after every test, and the complete verification set passed after that correction.

These checks verify the frontend foundation only. They do not establish backend integration, live browser data flows, or production deployment readiness.

## Phase 06.3 — API contract and test harness

Implemented:

- captured `frontend/src/api/openapi.json` from the running Phase 05 FastAPI app;
- generated and committed strict TypeScript declarations from that contract;
- added typed functions for every verified `/api/v1` incident, investigation,
  evidence, report, and review operation;
- required caller-supplied idempotency keys on incident and investigation
  creation functions;
- normalized product error envelopes, validation issues, request IDs,
  non-JSON failures, unreadable success payloads, and network failures;
- kept reviewer bearer credentials explicit and confined to review functions;
- added stable TanStack Query key factories without connecting pages early;
- added MSW server lifecycle, default handlers, and typed fixture builders;
- covered success, validation, conflict, unavailable, malformed-error, required
  idempotency-header, and review-auth boundaries in tests.

The captured OpenAPI document contains 11 paths and 14 schemas. It also confirms
the existing limitation that only review operations are authenticated; this
checkpoint does not add a login screen or imply product-wide authorization.

Backend source was not changed. In this environment the backend suite initially
encountered the host SOCKS proxy without its optional SOCKS transport. Rerunning
with proxy variables removed produced 40 passed and 1 skipped (41 collected),
which is the backend checkpoint used for this phase.

Phase 06.3 does not yet connect API functions to page components. Incident list
and intake integration remain Phase 06.4 work.

## Phase 06.3 verification

Executed successfully in the checkpoint workspace:

- live FastAPI OpenAPI capture — 11 paths and 14 schemas parsed;
- `npm run generate:api` — generated declarations and formatting completed;
- `npm run format:check`;
- `npm run lint`;
- `npm run typecheck`;
- `npm test` — 2 test files, 9 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities;
- backend regression suite with host proxy variables removed — 40 passed,
  1 skipped (41 collected).

These checks verify contract capture, generated types, client behavior, mocks,
and a production frontend compilation. They do not claim live page integration,
browser E2E behavior, or production authentication readiness.

## Phase 06.4 — incident workflows

Implemented:

- connected the incident list to `GET /api/v1/incidents` with a page size of 20;
- added Previous/Next offset pagination without inventing a total count;
- added severity and status filters that explicitly apply only to the loaded page;
- added loading, empty, page-filter-empty, network/error, and retry states;
- implemented manual incident intake using React Hook Form and Zod;
- validated required fields, length limits, timezone-local inputs, and an end time
  later than the start time before submission;
- serialized valid local date-time values as timezone-aware ISO UTC values for
  the API;
- reused one idempotency key for an unchanged failed submission and generated a
  new key when edited values formed a new intent;
- mapped structured backend validation issues to form fields while preserving a
  safe request-level error message;
- implemented incident detail loading and edits limited to title, description,
  and severity;
- displayed service, status, incident ID, severity, and the immutable incident
  time window without exposing unsupported controls;
- kept investigation history and start controls deferred to Phase 06.5.

No backend source, Python dependency, investigation workflow, evidence/report
workspace, reviewer credential handling, or product authentication was changed.

## Phase 06.4 verification

Executed successfully in the checkpoint workspace:

- `npm run format:check`;
- `npm run lint` with zero warnings;
- `npm run typecheck`;
- `npm test` — 3 test files, 15 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities.

The workflow tests cover API-backed rendering, empty results, heuristic
pagination, time-window validation, timezone-aware request serialization,
idempotency-key retry/new-intent behavior, server validation mapping, detail
loading, and supported-field updates. Browser E2E verification against the real
local API remains part of Phase 06.9 rather than being claimed here.

## Phase 06.5 — investigation lifecycle

Implemented:

- connected incident detail to paginated investigation history;
- displayed immutable run focus, status, queue time, and worker attempt count;
- added optional-focus investigation creation with the verified `202` contract;
- reused an idempotency key for unchanged network retries and generated a new
  key for changed submission intent;
- disabled creation when a loaded active run exists or the incident is closed;
- handled backend `409` conflicts by refreshing authoritative history rather
  than inventing a client-side run;
- connected investigation detail to durable investigation and job state;
- displayed queue, start, and finish timestamps plus the three-attempt budget;
- polled only `QUEUED` and `RUNNING` states at four-second intervals and used
  TanStack Query's background-tab pause behavior;
- stopped polling for `AWAITING_REVIEW`, `COMPLETED`, `FAILED`, and `CANCELLED`;
- displayed `parent_id` as immutable ancestry without offering unsupported
  reinvestigation controls or implying the parent report changed;
- mapped the verified worker failure codes to safe explanations while retaining
  the returned code for diagnosis;
- explicitly omitted retry/cancel controls because no such API exists;
- replaced the obsolete shell placeholder with a real `/ready` product/database
  readiness check.

No backend source, Python dependency, evidence/report rendering, review flow,
worker control, or product authentication was changed.

## Phase 06.5 verification

Executed successfully in the checkpoint workspace:

- `npm run format:check`;
- `npm run lint` with zero warnings;
- `npm run typecheck`;
- `npm test` — 4 test files, 20 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities.

The lifecycle tests cover active-run safeguards, investigation creation,
unchanged retry idempotency, `409` reconciliation, durable job status and
attempts, worker failure, parent ancestry, and active-versus-terminal polling.
Browser E2E verification against the real local API and worker remains Phase
06.9 work and is not claimed by this checkpoint.

## Phase 06.6 — evidence and report workspace

Implemented:

- fetched the backend's complete bounded set of up to 100 normalized evidence
  records for a known investigation;
- preserved backend chronological order and explicitly stated that observation
  order is not inferred causality;
- added page-local `LOG`, `TRACE`, `METRIC`, and `CHANGE` filters;
- displayed service, observation time, normalized summary, source backend,
  `source_ref`, and trace ID without treating identifiers as external links;
- made source references and trace IDs copyable without rendering raw secrets,
  headers, or API keys;
- fetched evidence and reports independently with separate loading, empty,
  unavailable, retry, and partial-data states;
- treated report `404` during an active run as analysis not yet available;
- keyed evidence/report reads by investigation status so the transition out of
  an active state performs a final authoritative fetch before polling stops;
- displayed report summary and uncertainty as visually distinct content;
- rendered `LOW`, `MEDIUM`, and `HIGH` confidence only, without percentages;
- resolved `SUPPORTS` and `CONTRADICTS` citations against the complete loaded
  evidence set and displayed missing references explicitly;
- kept missing evidence separate from citation relationships and did not relabel
  it as recommended action;
- surfaced known evidence gaps, including `CHANGE_FEED_NOT_CONFIGURED`, as
  limitations rather than inferred change events;
- rendered zero hypotheses as valid abstention: `No supported hypothesis`;
- retained evidence-first reading order ahead of model analysis.

No backend source, Python dependency, confidence calculation, RCA logic,
dependency inference, next-check generation, review flow, or product
authentication was added.

## Phase 06.6 verification

Executed successfully in the checkpoint workspace:

- `npm run format:check`;
- `npm run lint` with zero warnings;
- `npm run typecheck`;
- `npm test` — 5 test files, 26 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities.

The evidence tests cover evidence-first ordering, kind filtering, provenance,
supporting and contradicting labels, missing citation references, qualitative
confidence, explicit change-feed limitations, zero-hypothesis abstention,
active-run report `404`, and independent evidence/report failure behavior.
Browser E2E verification against the real local API and worker remains Phase
06.9 work and is not claimed here.

## Phase 06.7 — immutable human review

Implemented:

- added the human-review panel after the evidence and generated report so the
  operator sees the evidence trail before recording judgment;
- limited the review to one explicit `ACCEPTED`, `REJECTED`, or `INCONCLUSIVE`
  decision plus an optional comment of up to 5,000 characters;
- added a separate confirmation step that states the decision is immutable;
- held the reviewer credential only in React page memory, rendered it as a
  password field, and passed it only to the existing review GET/PUT functions;
- did not read reviewer credentials from source, environment variables, URLs,
  logs, local storage, or session storage;
- preserved the exact prepared decision, comment, and in-memory credential for
  safe retry after a `503` response;
- handled `401` without discarding the prepared decision so the credential can
  be corrected;
- handled `409` by automatically retrieving the authoritative existing review
  with the same credential and showing that no replacement occurred;
- required authentication before retrieving the review of a completed
  investigation;
- refreshed the active investigation query after successful review submission
  or retrieval so `COMPLETED` remains backend-authoritative;
- kept non-review API requests unauthenticated and made no claim of login,
  roles, product-wide authorization, or production credential security;
- made an existing local-date intake assertion timezone-independent so the
  suite verifies the intended local-input-to-UTC serialization on any host.

No backend source, Python dependency, report content, evidence relationship,
incident status, worker behavior, or product-wide authentication was changed.

## Phase 06.7 verification

Executed successfully in the checkpoint workspace:

- `npm run format:check`;
- `npm run lint` with zero warnings;
- `npm run typecheck`;
- `npm test` — 6 test files, 32 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities.

The new review tests cover successful completion, review-only bearer headers,
`401`, automatic `409` reconciliation, `503` exact retry, completed-review
retrieval, and credential non-persistence across storage, URL, and component
remount boundaries. Browser E2E verification against the real local API and
worker remains Phase 06.9 work and is not claimed here.

## Phase 06.8 — responsive and accessibility hardening

Implemented:

- added a route-level error boundary with safe generic messaging, incident-list
  recovery, and explicit page reload without exposing internal error details;
- moved keyboard focus to main content after client-side route navigation and
  added a polite page-change announcement plus synchronized document title;
- moved focus into the mobile navigation when opened, supported Escape to
  close it, and restored focus to the menu button;
- added a global visible-focus fallback for links, buttons, inputs, textareas,
  and selects while preserving component-specific focus treatments;
- marked loading panels as polite busy live regions and readiness changes as a
  polite status;
- made query/report error recovery stack vertically with full-width buttons on
  narrow screens before returning to horizontal layout at larger breakpoints;
- announced client-validation messages and terminal investigation failures;
- replaced low-contrast slate secondary text, metadata, and placeholder tokens
  with the WCAG AA-capable slate-400 token on the application's dark surfaces;
- retained the existing reduced-motion media query and accessible textual
  labels alongside every color-coded status, confidence, evidence kind, and
  evidence relationship;
- statically reviewed fixed/minimum widths, grid columns, long identifiers, and
  wrapping behavior for the 320 CSS pixel boundary.

No backend source, API contract, product behavior, evidence logic, report
content, reviewer authentication boundary, or dependency was changed.

## Phase 06.8 verification

Executed successfully in the checkpoint workspace:

- `npm run format:check`;
- `npm run lint` with zero warnings;
- `npm run typecheck`;
- `npm test` — 7 test files, 37 tests passed;
- `npm run build` — Vite production build completed;
- `npm audit --audit-level=high` — 0 vulnerabilities.

The new hardening tests cover mobile-menu focus and Escape recovery, SPA route
focus and announcements, loading semantics, narrow retry controls, safe route
error recovery, WCAG contrast-ratio calculations for the hardened tokens, and
the reduced-motion rule. A static source scan found no unwrapped fixed-width
content exceeding the 320 px content boundary.

A live 320 px browser render was not independently completed in this workspace:
the available remote browser blocks loopback URLs and no local Chromium binary
is installed. That limitation is not treated as a successful visual test. The
real-browser viewport checks and full backend/worker flows remain explicit
Phase 06.9 work.

## Phase 06.9 — real integration and E2E verification

Implemented:

- pinned `@playwright/test` `1.63.0` and added desktop Chromium plus 320 CSS
  pixel Chromium projects;
- added a controlled HTTP-fixture browser journey covering incident creation,
  idempotency headers, investigation creation, evidence, report, citations,
  missing evidence, review-only authorization, immutable review, and the
  authoritative `COMPLETED` refresh;
- added a 320 px browser test for horizontal overflow, mobile-menu focus,
  Escape recovery, review confirmation, and narrow-screen usability;
- added an opt-in live test that creates a real incident, queues a real worker
  investigation, waits for `AWAITING_REVIEW`, and completes authenticated human
  review against the actual local stack;
- gated the live test behind `E2E_LIVE=1` and required the reviewer credential
  at runtime rather than source, URLs, persistent storage, or committed files;
- disabled screenshots, video, and tracing for the live credential-bearing
  suite so failure artifacts do not retain the reviewer key;
- isolated Vitest discovery to `src/**/*.test.{ts,tsx}` so component and browser
  test runners do not collect one another's suites;
- documented browser installation, real-stack prerequisites, PowerShell secret
  handling, persistent test-data impact, and the evidence required to close the
  milestone.

The initial browser harness did not change backend behavior. Owner-run live
verification later exposed a mismatch between the model instructions and the
existing aggregate limit of twelve evidence links. The model contract was
corrected to state that limit explicitly, while the downstream validation,
database migration, API contract, evidence rules, report rules, and
authentication boundary remained unchanged.

## Phase 06.9 verification status

Verified in the checkpoint workspace:

- `npm run format:check` passed;
- `npm run lint` passed with zero warnings;
- `npm run typecheck` passed;
- `npm test` passed — 7 files and 37 tests;
- `npm run build` passed;
- `npm audit --audit-level=high` reported 0 vulnerabilities;
- `npm run test:e2e:list` compiled and discovered 3 tests in 3 files across the
  desktop and 320 px projects;
- backend regression suite passed — 40 passed and 1 PostgreSQL test skipped.

Environment limits in the checkpoint workspace:

- fixture Playwright execution and the real 320 px render did not start because
  the Chromium download returned invalid empty archives and no browser
  executable was installed;
- the live browser workflow did not run because PostgreSQL, telemetry services,
  the worker, and reviewer/model credentials are not available here;
- the PostgreSQL concurrency test remained skipped because
  `TEST_DATABASE_URL` was not configured;
- `alembic current` against a real database was not run.

The failed Playwright launch in the checkpoint workspace was an
environment/tooling failure before test execution, not a product result.

Owner-reported local verification subsequently completed the remaining gates:

- Playwright Chromium installed successfully;
- the controlled desktop and 320 CSS pixel browser projects passed — 2 passed
  and the opt-in live test skipped as expected;
- the first live attempts captured the same 78 validated evidence records but
  exposed the aggregate citation-budget mismatch rather than weakening the
  validator;
- after correcting the model instructions, the real PostgreSQL/API/telemetry/
  worker/reviewer Playwright workflow passed — 1 passed in 1.3 minutes — and
  the worker reached `DONE` through its bounded retry behavior;
- the backend regression suite passed — 41 passed with 1 warning — including
  the configured PostgreSQL concurrency test;
- `python -m alembic current` reported `phase05_0002 (head)`;
- frontend audit reported 0 vulnerabilities.

Phase 06.9 is closed on this local-development evidence. This does not claim
public-deployment readiness; product-wide authentication remains absent.
