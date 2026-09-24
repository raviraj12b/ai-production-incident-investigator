# Phase 07.1: offline abstention baseline

`evaluation/corpus.json` is a small synthetic corpus that uses only the fields
the model adapter sends: evidence IDs, kind, time, service, constrained summary,
trace ID, and evidence gaps. The labels and rationales live in this evaluation
file, never in the product API, database, or frontend. All three cases require
abstention because they cannot establish a unique cause from available detail.
The empty case also documents the worker's no-model-call path.

Run the corpus check without a provider:

```bash
python evaluation/score_abstention.py
python -m unittest discover -s evaluation -p 'test_*.py' -v
```

The first command reports zero evaluated outputs. For a real evaluation later,
create a JSONL file with one entry per case:

```json
{"case_id":"no-observations","output":{"summary":"...","uncertainty":"...","hypotheses":[]}}
```

Then run `python evaluation/score_abstention.py --outputs path/to/outputs.jsonl`.
The scorer requires the exact corpus IDs once each and prints all case results.
It exits 0 when all expected abstention decisions match, 1 for an abstention
mismatch, and 2 for incomplete/malformed input. The JSONL example shows format,
not a model result. Do not put keys, real incident data, or evaluation labels in
the output file.

This scorer deliberately does **not** repeat production citation, confidence,
or lease validation. The `hypotheses` field must be an array; its contents are
not judged here. A passing run measures only the choice to abstain on these
synthetic cases. It does not prove that a proposed cause is correct, that a
citation supports the explanation, or that all provider responses satisfy the
production validator. Phase 07.2 will add a versioned provider run and a human
support/contradiction rubric before broader quality claims.
