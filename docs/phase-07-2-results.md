# Phase 07.2.4 provider run: measured results

This records what one published provider run measured and what it does not
show. Every number below is reproduced by `python evaluation/summarize_run.py
evaluation/runs/run-20261005T143726Z-c23f1609` on the published files, which
the unchanged production validator and the unchanged 07.1 scorer produced.
Nothing here is a causal-accuracy, root-cause or production-readiness claim.
Causal quality is `NOT_ASSESSED` and human review is pending.

## Run

| Field | Value |
| --- | --- |
| Run ID | `run-20261005T143726Z-c23f1609` |
| Started / finished (UTC) | 2026-10-05 14:37:26 / 14:37:34 |
| Provider, model | `groq` (`api.groq.com`), `openai/gpt-oss-20b` |
| Prompt fingerprint | `7a3154745b8aa283e5a56fc841fbe9e8aebb4949aa98cc129a3eeff91482a8e8` (covers system instructions and response schema only) |
| Repository at run time | commit `9e7d7f8eb842d1d39fc977a910f3ad6019232c77`, `dirty: false` |
| Corpus | version `07.1.0`, SHA-256 `6b0ee969c8919d8a4382fb7e4cbe63f51e16736ac9c85edc5d36475a7a031590` (frozen, unchanged) |
| Repeats | 3 per provider-called case |

Sampling parameters are not recorded in `run.json`, so nothing is claimed about
repeatability under other settings.

## Denominators

| Count | Value |
| --- | --- |
| Corpus cases | 3 |
| Provider-called cases | 2 (`isolated-server-error`, `mixed-status-and-trace`) |
| `NOT_CALLED` cases | 1 (`no-observations`: a fixed inconclusive result with no provider call; not a provider result and excluded from every provider count) |
| Planned provider calls | 6 |
| Outcomes | 6 `OK`, 0 `REFUSAL`, 0 `UNAVAILABLE`, 0 `OUTPUT_INVALID` |

There were no provider failures. Latency is the runner's per-attempt timing: n
= 6, min 1076.0 ms, median 1297.2 ms, max 1634.9 ms. It is provider wait as
measured by the runner, not a performance baseline.

## Production validator

Of the 6 `OK` attempts the unchanged production validator accepted 4 and
rejected 2. Both rejections carry the same reason, "The report must identify
all recorded evidence gaps":

| Attempt | Recorded gaps | What the saved output's `uncertainty` says |
| --- | --- | --- |
| `mixed-status-and-trace`, repeat 1 (2 hypotheses) | `CHANGE_FEED_NOT_CONFIGURED` | "Change feed not configured." |
| `isolated-server-error`, repeat 2 (1 hypothesis) | `NO_REQUEST_RATE`, `NO_TRACES`, `CHANGE_FEED_NOT_CONFIGURED` | Describes the missing request rate, trace data and change feed in prose |

The validator requires each gap code to appear verbatim in the report's
`uncertainty` text (`backend/analysis_pipeline.py`). In both rejected outputs
the gaps were described in words and the codes were absent. The accepted outputs
included the codes. This is a contract that stays as it is, so these are
reported as validator rejections, not as provider failures and not as an
instruction to loosen the rule. The validator checks structure and that cited
IDs belong to the evidence; it does not show that a citation supports the
explanation.

## Abstention (unchanged 07.1 scorer)

The corpus expects abstention for both provider-called cases. The model did not
abstain in any of the 6 attempts: 0 of 6 matched, and the decision was the same
across repeats for both cases (it never produced an empty `hypotheses` array).
The `no-observations` case is not counted, because it was not sent to the
provider.

This is a measured result for this model, prompt and sample. It does not
isolate a cause. The production validator also requires an abstaining report to
equal a fixed inconclusive text exactly; whether that rule, the prompt or the
model explains the result was not examined, and no conclusion is drawn.

## Review items

The review packet yields 4 items, and the count agrees with the attempt records
(`python evaluation/check_publishable.py` cross-checks them). Items are per
hypothesis and each accepted attempt had one hypothesis:

| Case | Repeat |
| --- | --- |
| `isolated-server-error` | 1 |
| `mixed-status-and-trace` | 2 |
| `isolated-server-error` | 3 |
| `mixed-status-and-trace` | 3 |

Excluded from review: 1 `NOT_CALLED`, 2 production-rejected, 0 provider
failures, 0 abstentions.

## What is not shown

- No human review has been recorded. `reviews/` does not exist for this run, no reviewer has labeled any item, and no review result is claimed. Publishing a review result needs two independent reviewers, with adjudication for any disagreement (rubric: `docs/phase-07-2-review-rubric.md`).
- Causal quality is `NOT_ASSESSED`. The corpus has only abstention-expected cases and no identifiable cause, so no accuracy figure exists or is implied.
- Three repeats of two cases is a small repeatability sample, not a statistical study, for one model and one prompt.
- Citation provenance (validator) is not semantic support (human rubric) and neither is causal truth.
- Publication eligibility (`check_publishable.py`) says the artifact met the policy. It does not say anything about the quality of the model's answers.
