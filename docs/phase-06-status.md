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
