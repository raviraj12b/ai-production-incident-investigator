# Frontend

React and TypeScript operations console for the AI Production Incident Investigator.

## Current checkpoint

Phase 06.6 adds the evidence and report workspace to the investigation lifecycle:

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

The frontend does not calculate confidence, infer causality, create dependency
relationships, or turn missing evidence into invented next-check actions. Human
review belongs to Phase 06.7.

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
```

The development server proxies product API requests to `http://127.0.0.1:8000`.
