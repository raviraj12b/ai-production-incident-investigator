# Phase 07.2.3: human review rubric

This rubric covers what a person judges about a provider explanation, and when
the results may be published. It defines labels, not numeric scores. It
measures semantic support, contradiction handling and causal calibration. It
does not measure whether a cause is true.

## Why this exists

Three questions are kept apart on purpose:

| Question | Answered by |
| --- | --- |
| Which evidence was cited? | Provenance: the production validator, recorded in each run |
| Does that evidence support the explanation? | This rubric |
| Was it the real root cause? | Not assessed. The 07.1 corpus has no case with an identifiable cause |

## What is reviewed

One review item is one hypothesis in a provider attempt that is all of:

- outcome `OK`;
- not an abstention (it has at least one hypothesis);
- accepted by the production validator.

Everything else is excluded and counted separately in the review summary:
abstentions have no explanation to judge, provider failures have no output, and
an output the production validator rejects (for example one citing evidence
outside the case) is not what a reader would be shown and may cite items that
cannot be checked. Items are per hypothesis, so repeats of the same case are
separate items; the denominators say so.

## What the reviewer sees and does not see

`python evaluation/review_run.py packet <run_dir>` prints, per item: the
output's summary, uncertainty, explanation and confidence, the cited evidence
with relations, and the full evidence and gaps the model was given for that
case. It never prints the corpus labels (`expected_abstain`, `rationale`) and
never prints which other reviewers said what. Judge the explanation against the
evidence supplied to the model, not against what you think happened and not on
whether you like the explanation.

## Labels

Each item gets exactly one label per dimension and a short note.

### `evidence_support`: does the explanation follow from the cited observations?

- `SUPPORTED`: every factual statement in the explanation follows from the cited observations, and the explanation states nothing the evidence does not show.
- `PARTIAL`: some statements follow from the cited observations; others go beyond them, or the cited observations cover only part of the explanation.
- `UNSUPPORTED`: the cited observations do not support the explanation, or the explanation rests on things not in the evidence.

### `contradiction_handling`: are conflicting observations acknowledged?

Look at all the evidence the model was given, not only the cited items.

- `NOT_APPLICABLE`: no supplied observation conflicts with or weakens the explanation.
- `ACKNOWLEDGED`: at least one such observation exists and the output (explanation, summary or uncertainty) takes it into account.
- `IGNORED`: at least one such observation exists and the output does not account for it.

Example from the synthetic corpus: a case that holds both a successful and a
failed request on the same trace conflicts with any explanation that treats the
failure as general. An output that mentions the success is `ACKNOWLEDGED`; one
that does not is `IGNORED`.

### `causal_calibration`: does the wording match the evidence?

- `CALIBRATED`: the output frames its claim as a hypothesis or possibility, its confidence is consistent with the evidence, and it does not present the cause as established.
- `OVERSTATED`: the output presents a cause as established or certain, or uses causal language ("caused by", "root cause is") or a confidence that the evidence cannot carry.

### Notes

One or two sentences saying why, at most 500 characters. Notes are published
with the run: no secrets, no personal data, no real telemetry.

## Process

1. Reviewers work independently. The tooling cannot verify independence, so it is a procedure: do not read another reviewer's file before submitting yours.
2. Create your file with `python evaluation/review_run.py template <run_dir> --reviewer <id>`. The template has null labels and is rejected until every label is filled in.
3. Reviewer IDs are pseudonyms matching `[a-z0-9][a-z0-9_-]{0,31}`. The ID is the file name: `reviews/<id>.jsonl`.
4. If two reviewers differ on any label of an item, an adjudication record is written for that item in `reviews/adjudication.jsonl`. It gives the final label for all three dimensions and a reason. Adjudication is only accepted for an item that has a disagreement.
5. Run `python evaluation/review_run.py summarize <run_dir>`.

## Publication gate

A causal-quality result may be published only when the summary reports
`PUBLISHABLE`, which needs all of:

- at least one review item;
- every item reviewed by at least two different reviewers;
- every item with a disagreement adjudicated.

A single reviewer is never enough. Until the gate holds, the summary reports
coverage, agreement and disagreements but withholds label counts. If a run has
no reviewable items (for example every provider output abstained), the status is
`NOT_APPLICABLE` and there is no review result to publish.

Even when `PUBLISHABLE`, the result describes the labels above for the items
that were reviewed. Calling it root-cause accuracy would need cases with an
identifiable cause; the current corpus has none. The denominators (items,
exclusions, reviewers, disagreements) are always published with any result.

## Reviewing the published run (pending)

Status for `evaluation/runs/run-20261005T143726Z-c23f1609/`: **no review has
been recorded.** There is no `reviews/` directory, no reviewer has labeled any
item, and the causal-quality status is `NOT_PUBLISHABLE`. Nothing in this
repository is a human-reviewed result until the steps below are done by two real
reviewers.

The published directory is evidence and is not edited while reviews are in
progress. `template` writes into the run directory, so each reviewer works on a
private copy:

1. Each reviewer copies the published run directory to their own scratch location (for example `evaluation/scratch/review-<id>/`, which is git-ignored) and does not read anyone else's copy or file.
2. In that copy: `python evaluation/review_run.py packet <copy>` shows what to judge, and `python evaluation/review_run.py template <copy> --reviewer <id>` creates `reviews/<id>.jsonl`. The reviewer fills in every label and a short note, following the rubric above, then sends back only that one file.
3. Only after both files exist are they added to `reviews/` in a working copy of the run. Any item where the two differ gets an adjudication record in `reviews/adjudication.jsonl`.
4. Run `python evaluation/review_run.py summarize <run_dir>`. Only a `PUBLISHABLE` status allows label counts to be reported.
5. Run `python evaluation/check_publishable.py <run_dir>` on the result. It rejects invalid or unfilled review files, so a template that nobody filled in cannot be published by accident.
6. Add the review files to the published run directory and update `docs/phase-07-2-results.md` in a separate commit. Publish the denominators, the reviewer count and every disagreement, including ones that were adjudicated.

Limits that remain even then. The tooling cannot verify independence or that the
two reviewer IDs belong to two different people, so both are procedural
requirements and one person using two IDs is a violation. A reviewed result
describes the labels above for these items only. It is not root-cause accuracy,
because the corpus has no case with an identifiable cause, and it covers four
items from one model and one prompt.
