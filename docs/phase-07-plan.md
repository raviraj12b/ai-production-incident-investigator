# Phase 07 — Testing, Evaluation & Observability (locked plan)

## Evidence basis and claim limits

This plan audits the assembled Phase 06.3 full source snapshot with the later
Phase 06.4–06.9 and closeout updates applied in order. This workspace is not a
Git checkout. The owner reports 41 backend tests, 37 frontend tests, the
fixture and live Playwright workflows, and migration `phase05_0002 (head)` as
passed on their development machine. These results have not been rerun here:
this environment has no project Python dependencies, PostgreSQL, telemetry
backends, browser binary, or reviewer/model credentials. The backend suite
cannot start here because `pytest` is unavailable.

The existing tests cover incident validation/idempotency, lease and retry
fencing, PostgreSQL concurrent claims (opt-in), telemetry bounds and redaction,
capture digests, citation membership/limits, review authentication and
immutability, three workflow acceptance paths, frontend API and component
contracts, fixture browser journeys, and one opt-in real-stack browser path.
The real-stack path is a functional smoke test, not a representative quality,
load, or security assessment.

| Area | Verified in source | Phase 07 gap |
| --- | --- | --- |
| AI quality | Structured response, bounded redacted input, citations, gap and confidence rules; inconclusive result supported | No independent corpus, abstention rate, causal correctness labels, provider repeatability, or reviewer-calibrated quality measurement |
| Telemetry | Bounded Loki/Prometheus/Jaeger queries, request counters and duration, JSON logs, OTLP export | No worker-stage metrics, investigation latency/failure dashboards, alert thresholds, or tested collector outage and recovery procedure |
| Failure modes | Worker retries on telemetry/model outage, rejects invalid citation, fences stale claims | Limited service partial-outage, timeout, restart, exhaustion, data corruption, and browser/API interruption coverage |
| Performance | Fixed query/window/item/body caps and one live workflow | No measured latency, throughput, resource use, or concurrency budget under a stated local topology |
| Security | Redacted evidence, restricted model input, review-only bearer key, bounded queries and responses | No broad auth/authorization; no public-deployment security claim, credential handling review, dependency scan beyond the reported npm audit, or adversarial input assessment |
| Observability | Request IDs, traces, logs, HTTP `/metrics` | No documented operational questions answered by worker and pipeline signals; no verified alert rules or recovery drill |

The current model sees event names, status codes, rates, and generic trace
presence, not raw error descriptions, deployment changes, or dependency graph.
These observations can support hypotheses but rarely identify a unique cause.
Citation membership proves provenance, not semantic support or causal truth.
The evaluator must report those limits, and ground truth must remain outside
the product database, API, and frontend.

## Locked milestones and acceptance criteria

### 07.1 — Evaluation protocol and abstention baseline

- Keep a small, versioned synthetic corpus of normalized evidence matching the
  model-visible data shape. Include empty, single-signal, and conflicting or
  ambiguous multi-signal cases. Each case has an independently written
  expected-abstention label and rationale in evaluation-only files.
- Add an offline scorer for saved model outputs. Count every corpus case;
  reject duplicate, missing, or unknown IDs and malformed outputs instead of
  silently dropping them. Report per-case abstention and aggregate counts, with
  no percentage or model-quality claim when no provider run exists.
- Document how to obtain model outputs separately in 07.2 and why this baseline
  cannot establish root-cause accuracy. No model call or production data access
  is part of 07.1.
- Accept when the corpus/scorer are executable with local standard Python,
  targeted tests demonstrate both successful and failed scoring, and no
  ground-truth label appears in a product endpoint or frontend asset.

### 07.2 — Provider evaluation and human rubric

- Run the frozen 07.1 corpus against a declared provider/model/prompt version,
  with secrets kept out of artifacts. Save bounded, synthetic outputs and
  record runs, refusals, errors, abstention, citations, and latency separately.
- A human reviewer assesses whether each explanation is supported by its cited
  observations, whether contradictory evidence is acknowledged, and whether
  the result overstates causality. Two reviewers or an adjudication record are
  required before any causal-quality score is published. Do not create cause
  accuracy claims without labeled, identifiable cases and a documented rubric.
- Accept when the evaluation can be reproduced from corpus, version metadata,
  and saved outputs; publish denominators, failures, and disagreements.

### 07.3 — Failure and recovery matrix

- Cover one backend at a time unavailable/malformed/slow, model refusal/rate
  limit/timeout, lease expiration and attempt exhaustion, partial evidence,
  API interruption, and collector restart. Reuse existing test paths; add only
  missing scenarios. Assert durable status, safe error, retry budget, no false
  successful capture/report, and recovery where supported.
- Accept when each documented scenario has a repeatable test or a clearly
  identified manual drill with observed result; skipped infrastructure tests
  remain unverified.

### 07.4 — Performance baseline

- Use a named local topology, fixed synthetic workload, warmup, measured sample
  count, percentiles, error rate, and resource observations for API reads,
  intake, evidence capture, and end-to-end investigation. Separate model wait
  from local processing and never compare incomparable environments.
- Accept when results and hardware/config are recorded with reproducible
  commands, and any proposed budgets follow measurements rather than invented
  targets. Do not run load against public or shared systems.

### 07.5 — Security boundary review

- Review API exposure and authorization, reviewer key lifetime, logs/traces,
  model payload, prompt injection through telemetry, dependency findings, and
  input/resource caps. Add focused regression tests only for discovered gaps.
- Accept when findings are prioritized with evidence and mitigations; public
  deployment remains blocked until product-wide authentication/authorization,
  managed secrets and transport security are implemented and checked.

### 07.6 — Operational observability

- Define observable questions for queue age, attempts, capture outcome, model
  outcome, completion latency, and unavailable telemetry. Add bounded worker
  and pipeline signals only where they improve diagnosis without leaking
  evidence or creating unbounded metric labels. Document dashboards or queries
  and alert thresholds tied to the measured baseline.
- Accept when a local failure/recovery drill can be traced from request ID and
  investigation ID through the worker without logging secrets or raw evidence,
  and each documented signal is observed in the live topology.

### 07.7 — Regression and evidence closeout

- Rerun backend and frontend checks, PostgreSQL locking, fixture browser paths,
  opt-in live path, evaluation, drills, and selected performance/security gates
  in the owner environment. Record exact command, environment, pass/skip/fail,
  and limits. Preserve the Phase 05/06 contracts and `phase05_0002` unless a
  separately justified migration is required.
- Accept when the results and known blockers are documented without upgrading
  a simulated, skipped, owner-reported, or unavailable check into a local pass.

## Sequence and scope

Milestones proceed in order. The 07.1 scorer measures an intentionally narrow
property: whether an output abstains when the normalized observations are
insufficient to distinguish causes. It does not duplicate the production
validator's citation and confidence checks. Later provider and human review
are necessary before any claim about model judgment or causal accuracy.
