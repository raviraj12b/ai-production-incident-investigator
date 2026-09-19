# Phase 05.7: queryable telemetry on Windows

This slice adds internal, read-only `query_logs`, `query_metrics`, `query_traces`,
and `get_trace` methods in `backend/telemetry_gateway.py`. They accept an
explicit service, timezone-aware window of at most 24 hours, and a limit of
1–100. The adapters construct Loki LogQL, Prometheus PromQL, and Jaeger v3
queries; callers cannot supply backend query text. HTTP reads have a five-second
timeout and a two-megabyte response cap. Returned records have source fields,
Evidence redaction and database persistence are described separately in
[`phase-05-8-evidence.md`](phase-05-8-evidence.md).

The two FastAPI processes expose `/metrics` for Prometheus scraping. With
`OTEL_ENABLED=true` and `OTEL_LOGS_ENABLED=true`, they also export Python logs
via OTLP/HTTP to the existing Collector. Structured JSON remains on stdout.
The new Collector config forwards OTLP logs to Loki and spans to Jaeger. These
services run as **separate Windows binaries; Docker is not needed**.

## Start the local backends

Download the Windows builds from the [Loki local install guide](https://grafana.com/docs/loki/latest/setup/install/local/),
[Prometheus downloads](https://prometheus.io/download/), and
[Jaeger downloads](https://www.jaegertracing.io/download/). Use the Loki local
config matching your binary release from its install guide. Run each command
in a separate PowerShell window, from the extracted binary's directory:

```powershell
# Loki directory
.\loki-windows-amd64.exe --config.file=.\loki-local-config.yaml

# Prometheus directory; replace REPO with the full repository directory
.\prometheus.exe --config.file="REPO\telemetry\prometheus.yml"

# Jaeger directory: avoid the existing Collector's port 4318
.\jaeger.exe --set=receivers.otlp.protocols.http.endpoint=127.0.0.1:4319

# Existing standalone Collector directory
.\otelcol.exe --config="REPO\telemetry\otel-collector-queryable.yaml"
```

Jaeger's default local store is **in memory**: traces disappear when Jaeger
restarts. The [Badger storage option](https://www.jaegertracing.io/docs/2.21/storage/badger/)
can be configured for persistence later. Loki and Prometheus use local storage
configured by their respective files. Keep ports 3100, 9090, 16686, and 4319
local to your development machine.

Start the dependency and API processes from the repository root (in Git Bash):

```bash
OTEL_ENABLED=true OTEL_LOGS_ENABLED=true python -m uvicorn dependency_service.main:app --port 8001
OTEL_ENABLED=true OTEL_LOGS_ENABLED=true python -m uvicorn backend.main:app --port 8000
```

The API still requires the existing `DATABASE_URL` when using product routes;
this slice does not add a migration. If you are only checking the old Collector
debug configuration, leave `OTEL_LOGS_ENABLED` unset.

## Verify

```bash
python -m pytest -q
curl -i http://127.0.0.1:8000/metrics
curl -i http://127.0.0.1:8001/metrics
curl -i http://127.0.0.1:3100/ready
curl -i http://127.0.0.1:9090/-/ready
curl -i http://127.0.0.1:8000/inventory
```

Give Prometheus two scrapes (about 30 seconds with the supplied config) after
generating traffic. Query the adapters from a Python REPL in the repository:

```python
from datetime import datetime, timedelta, timezone
from backend.telemetry_gateway import Query, TelemetryGateway
end = datetime.now(timezone.utc)
query = Query("incident-demo-api", end - timedelta(minutes=15), end, limit=10)
with TelemetryGateway() as gateway:
    logs = gateway.query_logs(query)
    metrics = gateway.query_metrics(query, "request_rate")
    traces = gateway.query_traces(query)
    print("logs", len(logs), "metrics", len(metrics), "spans", len(traces))
    if traces:
        print("trace ID", traces[0]["trace_id"])
        print("trace spans", len(gateway.get_trace(traces[0]["trace_id"])))
```

The search window must contain **new traffic** sent while the backends were
running. Search results can be empty without an error when there is no matching
traffic, no 5xx for `error_rate`, or Prometheus lacks two samples. `get_trace`
returns at most 100 spans; trace searches are capped by count and response
size. Backend outages raise `TelemetryUnavailable`, distinct from an empty
successful query. The queued investigation from 05.6 remains `QUEUED`; no
worker uses these tools until the evidence pipeline is built.

API references: [Loki range query](https://grafana.com/docs/loki/latest/reference/loki-http-api/),
[Loki OTLP ingestion](https://grafana.com/docs/loki/latest/send-data/otel/),
[Prometheus range query](https://prometheus.io/docs/prometheus/latest/querying/api/),
[Jaeger v3 query contract](https://github.com/jaegertracing/jaeger-idl/blob/main/swagger/api_v3/query_service.openapi.yaml).
