# Phase 05.10: standalone investigation worker

The API still only **queues** investigations. Run `python -m backend.worker`
as a separate process when the product database and the three queryable
telemetry backends are ready. `--once` takes at most one job; `--poll` watches
for more jobs every five seconds until Ctrl+C. Both use the existing
PostgreSQL lease and three-attempt retry limit. The worker requires a database
at revision `phase05_0002` and `GROQ_API_KEY` **before claiming a job**.
`GROQ_MODEL` is optional and defaults to `openai/gpt-oss-120b` served by Groq;
this model ID does not call the OpenAI API. It does not use a model embedded
in the FastAPI server.

The Groq adapter sends **only** saved, whitelisted evidence IDs, types, UTC
timestamps, services, summaries, validated trace IDs, and recorded gaps. Incident titles,
descriptions, raw log messages, request IDs, arbitrary span attributes, and
database credentials are excluded. The request has one input turn, no tools,
strict structured JSON output, and a size cap. A response is validated
again against the investigation's captured evidence before any report is
saved. Evidence references validate membership; they cannot verify that an
explanation is true. An empty successful capture produces an explicit
inconclusive report without a model call. Telemetry outages and model failures
schedule a retry rather than producing a made-up no-data report.

The adapter uses [Groq chat completions](https://console.groq.com/docs/api-reference)
and [Groq strict structured outputs](https://console.groq.com/docs/structured-outputs).
The default `openai/gpt-oss-20b` is listed for strict output and appears in
Groq's [free-plan rate limit table](https://console.groq.com/docs/rate-limits).
Rate limits depend on your own account; the worker calls Groq only when
explicitly started with a nonempty capture. Groq does not currently support
the OpenAI `store` request parameter, so it is deliberately absent here.

## Verify locally, in order

1. Run `python -m pytest -q` and `python -m alembic current`. Revision must
   remain `phase05_0002`. These tests use fake backends and HTTP mocks.
2. Follow `docs/phase-05-7-telemetry.md` to start and **verify** Loki,
   Prometheus, Jaeger, and the queryable Collector configuration. Generate
   recent `/inventory` traffic and check each gateway actually returns data.
3. In the worker's Git Bash terminal, set the same `DATABASE_URL` you use for
   the API, then read your Groq key without echoing:

   ```bash
   export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/incident_investigator'
   read -rsp 'Groq API key: ' GROQ_API_KEY; export GROQ_API_KEY; echo
   ```

   Replace database placeholders with your own values. Keep credentials out
   of Git. To override the default strict-output model, also set `GROQ_MODEL`
   to a currently supported Groq model ID.
4. Create a **new** incident with a recent, UTC-offset-aware window covering
   the traffic you generated, then POST a new investigation. Record the ID
   returned by the investigation POST. Target this job to avoid processing old
   queued investigations first:

   ```bash
   python -m backend.worker --once --investigation-id YOUR_INVESTIGATION_ID
   curl -i http://127.0.0.1:8000/api/v1/investigations/YOUR_INVESTIGATION_ID
   curl -i http://127.0.0.1:8000/api/v1/investigations/YOUR_INVESTIGATION_ID/evidence
   curl -i http://127.0.0.1:8000/api/v1/investigations/YOUR_INVESTIGATION_ID/report
   ```

   On success the worker prints `DONE`, the job is `DONE`, the investigation
   is `AWAITING_REVIEW`, and the report GET returns 200. `IDLE` means the
   target was not claimable; check its status. `HANDLED_FAILURE` means it was
   requeued or reached its attempt limit; GET investigation to see the safe
   error code and attempt count. `STALE` means the lease was lost. If all
   backends respond successfully with zero matches, the report is
   **inconclusive**, not an AI root-cause finding.

After one real targeted run works, start `python -m backend.worker --poll`
for local continuous processing. The worker is not automatically deployed or
started by the API. Each nonempty retry may call the configured model again,
so check your API account's usage controls before continuous polling.

## Verification limits

The nine worker tests exercise worker completion, data redaction before model
input, telemetry and model failure retries, zero-data behavior, targeted
claims, missing credentials, and the Groq chat request/response shape. They do not contact
Groq, prove the correctness of generated diagnoses, or verify concurrent
PostgreSQL workers. Do not interpret a citation as proof of root cause.
