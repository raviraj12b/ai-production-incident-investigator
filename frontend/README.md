# Frontend

React and TypeScript operations console for the AI Production Incident Investigator.

## Current checkpoint

Phase 06.9 adds explicit browser and live-stack verification boundaries:

- Vite application and strict TypeScript configuration;
- React Router page structure;
- TanStack Query provider defaults;
- Tailwind-based design tokens and responsive application shell;
- accessibility baseline and reduced-motion support;
- Vitest and Testing Library render/navigation tests;
- local development proxies for `/api`, `/health`, and `/ready`;
- a captured FastAPI OpenAPI document and committed generated TypeScript types;
- typed endpoint functions, normalized API errors, and stable query keys;
- MSW handlers, typed fixture builders, and contract-boundary tests.
- API-backed incident list with offset pagination and page-local filters;
- manual incident intake with client and server validation;
- retry-safe idempotency keys that change only for a new submission intent;
- incident detail and edits limited to title, description, and severity;
- explicit loading, empty, unavailable, and conflict/error presentation;
- local-time display with timezone-visible labels and UTC API serialization.
- API-backed investigation history with offset pagination;
- optional-focus investigation creation with retry-safe idempotency;
- active-run and closed-incident safeguards backed by server conflict handling;
- authoritative investigation/job states, attempts, and lifecycle timestamps;
- polling only for queued/running states, paused in background tabs;
- immutable parent-investigation ancestry and safe worker-failure messages;
- a real `/ready` product/database readiness indicator in the application shell.
- one complete bounded evidence read of up to 100 backend-normalized records;
- chronological timeline and page-local LOG/TRACE/METRIC/CHANGE filters;
- copyable, non-navigable source references and trace identifiers;
- independently recoverable evidence and report requests;
- explicit pre-completion report-unavailable behavior;
- report summary, uncertainty, qualitative hypotheses, and missing evidence;
- SUPPORTS and CONTRADICTS citation resolution with unavailable-reference states;
- explicit evidence limitations including `CHANGE_FEED_NOT_CONFIGURED`;
- valid abstention rendering when a report contains zero hypotheses.
- one explicit `ACCEPTED`, `REJECTED`, or `INCONCLUSIVE` decision;
- an optional bounded comment and a separate confirmation step;
- reviewer credentials held only in React memory and sent only to review endpoints;
- authenticated retrieval of completed reviews;
- exact-request retry after `503` without losing the prepared decision;
- `409` reconciliation by retrieving and displaying the authoritative existing review;
- authoritative investigation refresh after review submission or retrieval.
- route-level recovery that hides internal error details;
- keyboard focus transfer into the mobile navigation and Escape-to-close behavior;
- main-content focus plus polite page announcements after client-side navigation;
- polite, busy loading announcements and announced field-validation errors;
- retry and recovery layouts that stack at narrow widths;
- an application-wide visible-focus fallback for interactive controls;
- higher-contrast secondary text, metadata, and placeholder tokens;
- retained reduced-motion behavior for transitions and animations.
- pinned Playwright Test and a reproducible Chromium configuration;
- a controlled desktop browser journey from incident intake through immutable review;
- a dedicated 320 CSS pixel project with overflow and keyboard-navigation checks;
- an opt-in real-stack workflow that is never enabled without `E2E_LIVE=1`;
- separate commands for browser installation, fixture tests, test discovery, and live verification;
- Vitest isolation so Playwright specifications are not collected as component tests.

The frontend does not calculate confidence, infer causality, create dependency
relationships, turn missing evidence into invented next-check actions, or alter
the generated report during review. The single local reviewer bearer credential
is not production authentication or a role system.

## API contract workflow

`src/api/openapi.json` was captured from a running FastAPI process. If the
backend contract intentionally changes, recapture that document and regenerate
the committed types:

```bash
npm run generate:api
```

The client uses same-origin `/api/v1` paths. Development proxying sends them to
`http://127.0.0.1:8000`. Production deployment must provide the same-origin
reverse proxy or a narrowly configured backend CORS policy.

Only review reads and writes accept a reviewer bearer token. There is no
product-wide browser authentication, and reviewer credentials must not be
compiled into the bundle, placed in URLs, logged, or persisted in browser
storage.

## Commands

```bash
npm install
npm run dev
npm run generate:api
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e:list
npm run test:e2e:install
npm run test:e2e
```

The development server proxies product API requests to `http://127.0.0.1:8000`.
The real-stack E2E prerequisites and credential-safe PowerShell commands are in
`../docs/phase-06-9-e2e.md`.
