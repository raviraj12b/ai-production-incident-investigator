# Frontend

React and TypeScript operations console for the AI Production Incident Investigator.

## Current checkpoint

Phase 06.3 establishes the typed API boundary and test harness on top of the
Phase 06.2 foundation:

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

The API functions are not connected to pages yet, so the UI still does not
display backend data. Incident list and intake UI belong to Phase 06.4.

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
