# Phase 06.1 — Frontend requirements and implementation plan (re-locked)

## Status and evidence basis

This plan is reconciled against the decisions from project chats 00 through 04 and the reconstructed Phase 05 source checkpoint: the Phase 05 foundation plus updates 05.6 through 05.13.

- VERIFIED FROM SOURCE: API routes, request and response schemas, state values, validation rules, error envelope, pagination style, reviewer authentication boundary, and absence of CORS middleware.
- LOCKED PROJECT CONTEXT: problem framing and research from chat 00, PRD boundaries from chat 01, system boundaries from chat 02, data/API contracts from chat 03, and deterministic/AI responsibility boundaries from chat 04.
- OWNER-REPORTED: 41 backend tests pass and Alembic is at `phase05_0002 (head)`.
- NOT INDEPENDENTLY RE-RUN HERE: the available Python environment does not contain `pytest`.
- EXCLUDED: `relayflow_complete_spec.md` describes a different product and is not an authority for this project.

## Decision authority and reconciliation rule

Frontend behavior follows this order:

1. locked product intent and safety boundaries from chats 00–04;
2. the verified Phase 05 HTTP contract for behavior the browser can actually execute;
3. this Phase 06 plan for presentation and interaction details.

The frontend must not silently simulate an earlier design that Phase 05 did not implement. When an earlier contract and the verified backend differ, the UI follows the verified API and the difference is recorded as a backend/design gap.

### Reconciled decisions from chats 00–04

- The project is a flagship portfolio system intended to demonstrate a real incident-investigation problem, agentic AI judgment, evaluation, observability, and Python/full-stack engineering—not a generic CRUD dashboard.
- The MVP begins with an existing external alert or manually created incident. Automatic anomaly detection is not a Phase 06 frontend responsibility.
- Primary users are on-call engineers, SREs, backend engineers, and platform/DevOps engineers. Incident commanders or engineering leads are secondary review consumers.
- The Investigator is not a monitoring-platform replacement or raw telemetry warehouse.
- The browser is a thin client. Retrieval, normalization, correlation, counts, timelines, dependency/change relationships, confidence, and RCA reasoning belong to the backend pipeline.
- AI operates only on bounded, normalized evidence and may abstain. An inconclusive report with no hypotheses is a valid successful result.
- Product state and evaluation ground truth remain isolated. Simulator modes, injected causes, ground-truth labels, and evaluation hints must never be exposed to the frontend.
- Human review cannot rewrite an earlier report. Reinvestigation creates a linked new investigation instead of mutating historical evidence or conclusions.
- Excluded capabilities remain excluded: autonomous remediation, chatbot behavior, public arbitrary telemetry queries, vector search, LangGraph/multi-agent orchestration, Kubernetes-only assumptions, and speculative infrastructure.

The original PRD treated a polished dashboard as advanced scope after the investigation engine. Phase 06 is that deliberately deferred presentation phase; it must expose the completed backend workflow without expanding or redefining the engine MVP.

## Product goal

Build a responsive browser-based operations console that lets a user:

1. create and inspect incidents;
2. edit the limited fields supported by the API;
3. queue an AI-assisted investigation;
4. monitor durable investigation progress;
5. inspect evidence, hypotheses, citations, uncertainty, and missing evidence;
6. submit the protected human review decision in the local MVP.

The interface must separate observed evidence from model-generated hypotheses. It must never present a hypothesis as confirmed fact merely because its confidence label is `HIGH`.

The frontend does not detect incidents, query telemetry backends directly, perform root-cause analysis, calculate confidence, or take production-changing action.

## Frontend requirements

### Functional

- List incidents with offset pagination and a page size of 20.
- Create an incident with title, optional description, service, severity, timezone-aware start, and timezone-aware end.
- Validate required fields and enforce end time later than start time before submission.
- View a single incident and edit only title, description, and severity.
- List investigations for an incident.
- Queue an investigation with an optional focus.
- Reuse the same idempotency key for retries of the same create action; create a new key only for a new user intent.
- Poll queued and running investigations for authoritative state.
- Display job status, attempt count, timestamps, and safe error text.
- Display evidence ordered by observation time and grouped or filterable by `LOG`, `TRACE`, `METRIC`, and `CHANGE`.
- Display report summary and uncertainty prominently but distinctly.
- Display each hypothesis with its qualitative confidence, missing evidence, supporting evidence, and contradicting evidence.
- Resolve report evidence links against evidence records by ID. Missing references must be shown as unavailable, not silently discarded.
- Display investigation ancestry when `parent_id` is present so a reinvestigation is visibly linked without implying that the prior report changed.
- Present evidence chronologically as the available investigation timeline; do not calculate or invent causal ordering beyond backend-provided timestamps and links.
- Allow a locally configured reviewer to submit exactly one `ACCEPTED`, `REJECTED`, or `INCONCLUSIVE` decision with an optional comment.
- Treat a `409` during review as immutable-review conflict and re-fetch the existing review when credentials permit.
- Show clear loading, empty, unavailable, validation, conflict, and retry states.

### Evidence-focused presentation

- Evidence is visually primary; model conclusions remain visibly labeled as hypotheses.
- No invented confidence percentages. The API exposes only `LOW`, `MEDIUM`, and `HIGH`.
- Supporting and contradicting citations use different labels and icons, not color alone.
- Uncertainty and missing evidence cannot be hidden behind collapsed advanced sections by default.
- Empty hypotheses are a valid abstaining result and must be rendered as “no supported hypothesis,” not as a broken report.
- `CHANGE_FEED_NOT_CONFIGURED` and other missing-signal gaps are shown as evidence limitations, never filled with inferred changes.
- Service names and trace IDs may show observed cross-service correlation, but the client must not invent a dependency graph from incomplete records.
- `source_ref` and trace IDs are rendered as copyable identifiers. They are not treated as safe external URLs unless a future backend contract explicitly provides navigable URLs.
- Raw secrets, authorization headers, and API keys must never be rendered or logged by frontend code.

### Quality

- Responsive layouts at mobile, tablet, and desktop widths.
- Keyboard-accessible controls, visible focus states, semantic headings, labeled inputs, and status text that does not rely only on color.
- No horizontal page overflow at 320 CSS pixels.
- Route-level error boundaries and recoverable query errors.
- Stable date formatting with UTC source values and an explicit local/UTC indication.
- Reduced-motion support.

## Primary user workflows

### 1. Incident intake

`Incident list -> New incident -> Validate -> POST incident -> Incident detail`

The client generates one idempotency key when the user starts the submission. Network retry reuses that key. Editing form values after a completed or abandoned request creates a new intent and key.

### 2. Start and monitor an investigation

`Incident detail -> Optional focus -> Queue investigation -> Investigation workspace`

While state is `QUEUED` or `RUNNING`, the client polls the investigation endpoint. Polling stops for `AWAITING_REVIEW`, `COMPLETED`, `FAILED`, and `CANCELLED`. The backend remains the system of record.

### 3. Inspect evidence and analysis

`Investigation workspace -> Evidence -> Report -> Hypotheses -> Linked citations`

Evidence and report requests are independent. A report `404` before analysis completion means “not available yet,” not an application failure. Evidence may be partial and must display signal gaps honestly.

The evidence-to-conclusion chain is presented in this order: normalized evidence and provenance, observations available in the stored summaries, hypotheses and their evidence relations, report summary and uncertainty, then human disposition. The UI does not manufacture a separate observation or next-check object when the API has not provided one.

### 4. Human review

`Awaiting review -> Enter local reviewer credential -> Choose decision -> Confirm -> PUT review -> Re-fetch investigation and review`

The reviewer credential is local-development-only. It is held in memory for the current page session and is never placed in source, a Vite environment variable, URL, log, or persistent browser storage.

## Information architecture and routes

| Route | Purpose | Main API calls |
| --- | --- | --- |
| `/` | Redirect to incidents | None |
| `/incidents` | Operational landing page and incident list | `GET /api/v1/incidents` |
| `/incidents/new` | Incident intake form | `POST /api/v1/incidents` |
| `/incidents/:incidentId` | Incident details, supported edits, investigation history, start action | `GET/PATCH /api/v1/incidents/{id}`, `GET/POST .../investigations` |
| `/investigations/:investigationId` | Status, evidence, report, cited hypotheses, and review | investigation, evidence, report, and review endpoints |
| `*` | In-app not-found page | None |

There will be no fake login, audit page, incident-close control, worker control, cancellation control, manual retry control, or telemetry-backend browser in Phase 06 because the verified backend does not support those product workflows.

## Page structure

- Responsive application shell with product identity, Incidents navigation, backend readiness indicator, and compact mobile navigation.
- Incidents page: title, short operational summary, `New incident` action, severity/status filters applied to the loaded page only, incident cards/table, and pagination.
- New incident page: focused form with field guidance, timezone-visible date inputs, client validation, and server validation mapping.
- Incident detail: identity and status header, editable supported metadata, time window, investigation history, and investigation-start panel.
- Investigation workspace:
  - state and job strip;
  - immutable run metadata, time window, and optional parent investigation link;
  - report summary and uncertainty;
  - ranked hypotheses with qualitative confidence;
  - cited evidence drawer/list showing support or contradiction;
  - complete evidence timeline with kind filters;
  - missing evidence section;
  - review panel only when appropriate.

A service/dependency graph, raw trace waterfall, audit history, and explicit next-check checklist remain unavailable until supported by structured backend contracts. They must not be approximated in the browser from incomplete strings.

## Technology decision

- React + TypeScript + Vite for a typed client-side application with fast local development and a static production build.
- React Router for URL-addressable pages and nested layouts.
- TanStack Query for server-state caching, mutation invalidation, controlled polling, and retry behavior.
- React Hook Form + Zod for form state and client-side validation. Backend validation remains authoritative.
- Tailwind CSS with a small token layer for a consistent responsive design; no large component framework.
- Lucide React for accessible, consistent icons.
- Generated OpenAPI TypeScript types when the backend can be run, plus a small typed `fetch` client. Generated files are committed so ordinary frontend builds do not require a running backend.
- Vitest + React Testing Library for unit/component tests, MSW for network-level API mocks, and Playwright for critical browser workflows.
- No Redux: remote data belongs in TanStack Query and remaining UI state is local and small.

Exact dependency versions will be selected and locked during scaffolding after checking the active Node runtime and current package metadata.

## API integration boundaries

- Browser code calls relative `/api/v1/...` paths through a single API client.
- Browser code never calls Loki, Prometheus, Jaeger, the OpenTelemetry Collector, the dependency service, or simulator controls directly. All product evidence comes from the bounded Investigator API.
- Local Vite development proxies `/api` to `http://127.0.0.1:8000`, avoiding a backend CORS change for local development.
- Preferred deployment is same-origin frontend plus reverse-proxied API. A separate frontend origin requires an explicit backend CORS allowlist and is a deployment requirement, not a reason to enable permissive CORS.
- `GET /health` is process liveness; `GET /ready` is product/database readiness. The UI must not label `/health` alone as full system readiness.
- API errors under `/api/v1` use `{ error: { code, message, issues? } }`; parsing must still safely handle malformed or non-JSON failures.
- Lists use `limit` and `offset` but return no total count. The UI can provide Previous and Next, with Next available when a full page is returned; it cannot show a verified total.
- Active investigation polling is bounded and stops when the page is hidden or the state becomes terminal. No WebSocket or SSE contract exists.
- Report and evidence are fetched only for a known investigation. A pre-completion report `404` is represented as pending/unavailable.
- Reviewer authorization is attached only to review `GET` and `PUT` calls.
- `parent_id` is read-only ancestry metadata. The current API has no dedicated “request more evidence” or reinvestigation endpoint, so the UI cannot create linked follow-up runs automatically.

## Authentication and security limitations

- The product API is not authenticated except for review endpoints. This is a verified production blocker.
- There is no valid basis for a frontend login screen, user identity, role display, or route authorization.
- The single reviewer bearer key is not safe as public-web authentication. Any browser-based local review flow is a development convenience, not a production security design.
- The key must not be compiled into the frontend, stored in `VITE_*`, committed, logged, placed in URLs, or persisted in local storage.
- Until product-wide OAuth/OIDC or equivalent server-side sessions and authorization exist, the application must be restricted to local/trusted use and must not be publicly deployed as a secure product.

## Verified backend gaps and decisions

| Gap | Frontend impact | Phase 06 decision |
| --- | --- | --- |
| No CORS middleware | Direct calls from Vite origin to port 8000 would fail in browsers | Use Vite proxy locally; prefer same-origin reverse proxy in deployment. No backend change now. |
| No product-wide auth/authorization | Public users could access and mutate incidents | Do not invent login; clearly restrict to trusted/local use. Backend auth is required before public deployment. |
| Reviewer uses one configured bearer secret | Secret cannot become safe merely through UI | Memory-only credential input for local review; no build-time secret. |
| No global investigation endpoint | Landing page cannot cheaply show all investigations | Use incident-first navigation; avoid N+1 dashboard queries. |
| No audit-event endpoint | Audit trail cannot be displayed | Omit audit UI. |
| No structured observation model | The UI cannot distinguish a separately persisted observation layer from evidence summaries | Present evidence summaries as observations only in context; do not create synthetic observation records. |
| No explicit next-check field | Earlier design called for recommended next checks | Present `missing_evidence` as evidence still needed, but do not label it as backend-recommended actions. |
| No dependency graph contract | A complete service graph cannot be established from evidence strings | Show service and trace provenance; defer graph visualization. |
| No public evaluation contract | Ground truth is intentionally isolated | Never expose simulator state, injected causes, expected answers, or scoring controls. |
| No close/reopen endpoint | Incident status cannot be changed | Display status read-only. |
| No cancel/retry endpoint | Failed/running jobs cannot be controlled in UI | Display state and error only. |
| No WebSocket/SSE endpoint | No push updates | Bounded polling for active investigations. |
| No list totals or server filters | Exact counts and global filtering are unavailable | Page-local filters and heuristic Next navigation only. |
| Phase 03 used evidence relation `MISSING`; Phase 05 supports only `SUPPORTS`/`CONTRADICTS` | A third citation-relation badge would be false | Render missing evidence from `hypothesis.missing_evidence[]`, separate from citations. |
| Phase 03 used review `MORE_EVIDENCE_REQUESTED`; Phase 05 implements `INCONCLUSIVE` | The old decision cannot be submitted | Use `INCONCLUSIVE`; do not rename it in the request. A future linked reinvestigation workflow requires a new backend contract. |

None of these gaps requires an immediate backend edit to build and verify the local frontend vertical slice. Product-wide authentication is mandatory before public deployment. Audit retrieval, structured observations/next checks, dependency topology, and explicit linked reinvestigation remain product gaps rather than Phase 06 browser inventions.

## Visual direction

- Modern operations-console aesthetic: restrained slate/neutral surfaces, high-contrast typography, one cool accent, and semantic severity/status colors.
- Desktop uses a compact left navigation and broad evidence workspace; mobile uses a top bar and stacked sections.
- Dense technical data remains readable through progressive disclosure, not tiny type.
- Cards are used for summaries and hypotheses; evidence uses a timeline/list optimized for scanning.
- Confidence, status, evidence kind, and relationship labels always include text.
- The main reading order prioritizes operational questions: what was observed, where it came from, what the system hypothesizes, what contradicts it, what is missing, and what the reviewer decided.
- Avoid decorative charts until the API provides meaningful time-series values and the chart answers a real operational question.

## Implementation plan

### 06.2 — Scaffold and design foundation

- Confirm Node/npm versions.
- Create `frontend/` with React, TypeScript, and Vite.
- Add strict TypeScript, linting, formatting, test runner, base CSS/tokens, app shell, routes, and responsive navigation.
- Add an initial render test and run lint, typecheck, tests, and production build.

### 06.3 — API contract and test harness

- Capture the FastAPI OpenAPI document from a running backend and generate TypeScript types.
- Build the fetch client, error normalization, query-key factory, MSW handlers, and fixture builders.
- Add contract-oriented tests for success, validation, conflict, unavailable, and malformed error responses.

### 06.4 — Incident workflows

- Implement list, pagination, new incident form, detail page, and supported edits.
- Verify idempotency-key reuse on retry and replacement for new intent.
- Test timezone and validation behavior.

### 06.5 — Investigation lifecycle

- Implement investigation history, create action, detail status, job attempts, bounded polling, and terminal states.
- Display linked ancestry from `parent_id` without offering unsupported reinvestigation controls.
- Test conflict and worker-failure states.

### 06.6 — Evidence and report workspace

- Implement evidence filters/timeline, report summary, uncertainty, hypotheses, missing evidence, and citation resolution.
- Test supporting, contradicting, missing-reference, empty-hypothesis abstention, missing change feed, incomplete-evidence, and report-not-yet-available states.
- Verify that no RCA logic, confidence calculation, dependency inference, or next-check generation exists in frontend code.

### 06.7 — Review boundary

- Implement the local-only credential prompt and immutable review flow.
- Test 401, 409, 503, exact retry, completed review, and credential non-persistence.

### 06.8 — Responsive and accessibility hardening

- Verify keyboard navigation, focus, labels, contrast, narrow screens, loading announcements, reduced motion, and error recovery.

### 06.9 — Real integration and E2E verification

- Run frontend checks.
- Run backend and database at `phase05_0002`.
- Verify browser flows against the real local API and worker.
- Add Playwright coverage for incident creation through evidence/report/review using controlled fixtures or a reproducible seeded workflow.

### 06.10 — Documentation and checkpoint

- Document verified setup, environment boundaries, screenshots, test commands, and known security limitations.
- Produce a consolidated Phase 06 checkpoint only after lint, typecheck, unit/component tests, production build, and agreed E2E checks pass.

## Phase 06 acceptance criteria

1. A user can create, list, view, and edit the supported fields of an incident.
2. A user can queue an investigation and observe every supported state without manual refresh.
3. Evidence, report uncertainty, hypotheses, missing evidence, and citation relationships are distinguishable and traceable by ID.
4. The UI never invents telemetry, probabilities, causes, totals, audit history, or unsupported actions.
5. The UI performs no RCA, evidence correlation, confidence calculation, dependency inference, or ground-truth lookup.
6. Empty hypotheses and missing change evidence render as legitimate abstention/evidence-limit states.
7. Linked investigations preserve visible ancestry without modifying earlier reports or reviews.
8. The local reviewer flow handles authenticated success and 401/409/503 failures without persisting the key.
9. The layout is usable at 320 px and common desktop widths with keyboard-only navigation.
10. API errors are presented safely and do not expose secrets.
11. Lint, TypeScript checks, component tests, and production build pass.
12. Critical flows are executed against the real local backend before being called working.
13. Public deployment remains blocked until product-wide backend authentication/authorization is implemented and deployment topology is secured.
