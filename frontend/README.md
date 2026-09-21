# Frontend

React and TypeScript operations console for the AI Production Incident Investigator.

## Current checkpoint

Phase 06.2 establishes the frontend foundation only:

- Vite application and strict TypeScript configuration;
- React Router page structure;
- TanStack Query provider defaults;
- Tailwind-based design tokens and responsive application shell;
- accessibility baseline and reduced-motion support;
- Vitest and Testing Library render/navigation tests;
- local development proxies for `/api`, `/health`, and `/ready`.

It does not yet call the backend or display incident data. API types, the fetch client, error normalization, and mock handlers belong to Phase 06.3.

## Commands

```bash
npm install
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
```

The development server proxies product API requests to `http://127.0.0.1:8000`.
