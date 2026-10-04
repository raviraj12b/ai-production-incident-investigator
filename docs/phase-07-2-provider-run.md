# Phase 07.2: provider run and summary

`evaluation/run_provider.py` runs the frozen 07.1 corpus through the real
`GroqAnalyzer.analyze()` and saves what happened. It reuses the production
adapter and the production result validator (`analysis_pipeline._validate`,
the function `complete_claim` applies); it does not copy either. It makes no
quality or causal-accuracy claim. The 07.1 scorer and corpus are unchanged and
the scorer stays standard-library only.

## Running

Run from the repository root; the module imports the backend package.

```bash
export GROQ_API_KEY=...            # environment only; never written to a file
python -m evaluation.run_provider --repeats 3
```

`GROQ_MODEL` selects the model (default `openai/gpt-oss-20b`). The default
output root `evaluation/scratch/` is git-ignored. Without a key the command
exits 2 before writing anything. A run directory is never overwritten.

Tests use a mocked transport only: `python -m pytest tests/test_evaluation_provider_run.py`.
The summarizer's tests run with `python -m unittest discover -s evaluation -p "test_*.py"`.

**Status: no real provider run has been executed or committed yet.** Nothing in
this repository is a provider result until a run directory is published under
the policy below.

## Run directory

| File | Content |
| --- | --- |
| `run.json` | Written with `status: DECLARED` before the first provider call (repeat count, planned calls, corpus version and SHA-256, provider/model, prompt fingerprint, repo commit and dirty flag). Rewritten with `COMPLETE` and `finished_at` at the end. A run left at `DECLARED` was interrupted and is incomplete. |
| `runs.jsonl` | One record per attempt: `case_id`, `repeat`, `outcome`, `latency_ms`, `abstained`, `hypothesis_count`, `citation_count`, `validator`, `error`. |
| `outputs-r<N>.jsonl` | Provider results for repeat N in the format the 07.1 scorer reads. Only attempts with outcome `OK` appear, so a file can legitimately omit cases. |

Outcomes, recorded separately:

- `NOT_CALLED`: the case has no evidence, so the adapter and worker return the fixed inconclusive result without a provider call. Recorded once, never repeated, and not a provider result. With the current corpus the provider-called denominator is 2 of 3 cases (6 planned calls at 3 repeats).
- `OK`: a parsed result. `validator` holds what the production validator says (`accepted`, `reason`). A rejected result is still a provider output and is reported as such; it is not an error outcome.
- `UNAVAILABLE`: request failure. `http_status` (for example 429) and `timeout` are taken from the exception cause.
- `REFUSAL`: the provider returned an explicit refusal (`ModelRefusal`).
- `OUTPUT_INVALID`: incomplete, non-JSON, or wrong-shape output.

Error details are the adapter's fixed messages; raw provider text is not saved
for failures.

## What is and is not captured

- The prompt fingerprint is a SHA-256 of the system instructions and response
  schema. The adapter has no prompt version constant, and the fingerprint does
  not cover other request parameters. The adapter does not set temperature or
  a seed, so provider defaults apply and outputs may vary between repeats.
- The 3 repeats per provider-called case are a small repeatability sample, not
  a statistically significant study. The repeat count is declared in `run.json`
  before execution.
- When a provider returns no hypotheses, the adapter replaces its text with the
  fixed inconclusive result, so the saved abstention text is not the model's own.
- Citation validation here is provenance only: the production validator checks
  that cited IDs belong to the evidence and the structural and confidence
  rules. It does not show that a citation supports the explanation or that a
  cause is true. Those need the human rubric, and the current corpus (three
  cases, all expecting abstention) cannot support a causal-accuracy claim.

## Summarizing a run (07.2.2)

`evaluation/summarize_run.py` reads a saved run directory and prints a JSON
summary. It is standard library only, never calls a provider, and reuses the
07.1 scorer unchanged.

```bash
python evaluation/summarize_run.py evaluation/scratch/<run_id>
```

Exit 0 means a summary was produced; exit 2 means the run is malformed,
incomplete or inconsistent. It checks the accounting before reporting: status
`COMPLETE`, the corpus SHA-256 and version match, the plan matches the corpus,
every planned attempt has exactly one record, and each `outputs-r<N>.jsonl`
holds exactly the `OK` attempts of that repeat and agrees with its record.

The summary reports:

- **Denominators:** corpus cases, provider-called cases, `NOT_CALLED` cases,
  planned provider calls, and attempts by outcome.
- **Provider failures:** every `UNAVAILABLE`, `REFUSAL` and `OUTPUT_INVALID`
  attempt, with HTTP status, timeout flag and latency.
- **Validator:** accepted and rejected counts among `OK` attempts, with each
  rejection reason.
- **Abstention:** per repeat and per case, over `OK` attempts only, with the
  attempts that could not be scored listed. A case with fewer than two `OK`
  attempts is reported as `INSUFFICIENT_OK_ATTEMPTS`; otherwise its abstention
  decision across repeats is `CONSISTENT` or `INCONSISTENT`.
- **Latency:** min, median and max in milliseconds, with the sample size. This
  is provider wait as the runner measured it, not a performance baseline.
- **`causal_quality`:** always `NOT_ASSESSED` here. Any causal-quality figure
  needs labeled cases with an identifiable cause and the human rubric
  (07.2.3). There is no accuracy field.

`NOT_CALLED` cases are listed separately and excluded from every provider
count. The summarizer's tests build run directories by hand, and one test
checks that it accepts what the runner writes.

## Artifact-selection policy

- Scratch and debug runs stay in `evaluation/scratch/` and are never committed.
- At most one intentional real run is published, by copying its directory to
  `evaluation/runs/<run_id>/`, and only after all of these hold: `run.json`
  status is `COMPLETE`; `repo.dirty` is false (or explained); the corpus
  SHA-256 matches the committed corpus; the files contain only synthetic,
  bounded data; and a search of the directory finds no API key, `Bearer`, or
  `Authorization` text.
- Runs produced by tests (mocked transport) are never published.
- Failures, `NOT_CALLED` records, and validator rejections are published with the
  run; a run is not trimmed to its successes.
