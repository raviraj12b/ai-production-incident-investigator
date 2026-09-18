"""Bounded, read-only telemetry queries. Backend query syntax stays inside adapters.

These functions are internal worker tools, not public API routes. They do not
write product rows or give a model direct access to observability backends.
"""

import base64
import binascii
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx


MAX_WINDOW = timedelta(hours=24)
MAX_ITEMS = 100
MAX_RESPONSE_BYTES = 2_000_000
SERVICE_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{0,79}\Z")
TRACE_RE = re.compile(r"(?:[a-fA-F0-9]{16}|[a-fA-F0-9]{32})\Z")


class TelemetryUnavailable(Exception):
    """A backend failed, timed out, or supplied an incompatible response."""


@dataclass(frozen=True)
class Query:
    service: str
    start: datetime
    end: datetime
    limit: int = 50

    def __post_init__(self):
        if not SERVICE_RE.fullmatch(self.service):
            raise ValueError("Invalid service name")
        if (self.start.tzinfo is None or self.start.utcoffset() is None
                or self.end.tzinfo is None or self.end.utcoffset() is None):
            raise ValueError("Query timestamps must contain timezones")
        if not timedelta(0) < self.end - self.start <= MAX_WINDOW:
            raise ValueError("Query window must be positive and at most 24 hours")
        if not 1 <= self.limit <= MAX_ITEMS:
            raise ValueError("Query limit must be between 1 and 100")


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _hex_id(value: str, byte_count: int) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid telemetry ID")
    if re.fullmatch(r"[0-9a-fA-F]{%s}\Z" % (byte_count * 2), value):
        return value.lower()
    if byte_count == 16 and TRACE_RE.fullmatch(value) and len(value) == 16:
        return value.lower().zfill(32)
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid telemetry ID") from exc
    if len(raw) != byte_count:
        raise ValueError("Invalid telemetry ID")
    return raw.hex()


def _endpoint(name: str, default: str) -> str:
    value = os.getenv(name, default).rstrip("/")
    parsed = httpx.URL(value)
    if parsed.scheme not in {"http", "https"} or not parsed.host or parsed.path != "/":
        raise ValueError(f"{name} must be an HTTP(S) origin without a path")
    return value


def _request(client: httpx.Client, origin: str, path: str, params: dict, *, stream_chunks: bool = False):
    try:
        with client.stream("GET", origin + path, params=params, timeout=5.0) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise TelemetryUnavailable("Telemetry response exceeds size limit")
        if stream_chunks:
            decoder = json.JSONDecoder()
            raw = bytes(body).decode("utf-8").strip()
            values = []
            while raw:
                value, offset = decoder.raw_decode(raw)
                if not isinstance(value, dict):
                    raise ValueError("Expected JSON object")
                values.append(value)
                raw = raw[offset:].strip()
            if not values:
                raise ValueError("Expected JSON object")
            return values
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")
        return data
    except (httpx.HTTPError, ValueError) as exc:
        raise TelemetryUnavailable("Telemetry backend is unavailable or returned invalid data") from exc


class TelemetryGateway:
    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client()
        self._owns_client = client is None
        self.loki = _endpoint("LOKI_URL", "http://127.0.0.1:3100")
        self.prometheus = _endpoint("PROMETHEUS_URL", "http://127.0.0.1:9090")
        self.jaeger = _endpoint("JAEGER_QUERY_URL", "http://127.0.0.1:16686")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self._owns_client:
            self.client.close()

    def query_logs(self, query: Query) -> list[dict]:
        data = _request(self.client, self.loki, "/loki/api/v1/query_range", {
            "query": "{service_name=" + json.dumps(query.service) + "}",
            "start": _utc(query.start), "end": _utc(query.end),
            "direction": "backward", "limit": query.limit,
        })
        if data.get("status") != "success" or data.get("data", {}).get("resultType") != "streams":
            raise TelemetryUnavailable("Unexpected Loki response")
        result = []
        try:
            for stream in data["data"]["result"]:
                if stream.get("stream", {}).get("service_name") != query.service:
                    continue
                for value in stream["values"]:
                    timestamp, line = value[:2]
                    metadata = value[2] if len(value) > 2 else {}
                    entry = json.loads(line) if line.startswith("{") else {"message": line}
                    if not isinstance(entry, dict):
                        entry = {"message": line}
                    result.append({
                        "timestamp_ns": str(timestamp), "service": query.service,
                        "message": str(entry.get("message", line))[:2000],
                        "level": entry.get("level", metadata.get("severity_text")),
                        "trace_id": entry.get("trace_id", metadata.get("trace_id")),
                        "request_id": entry.get("request_id", metadata.get("request_id")),
                        "source": "loki", "reference": str(timestamp),
                    })
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
            raise TelemetryUnavailable("Unexpected Loki response") from exc
        return sorted(result, key=lambda row: row["timestamp_ns"], reverse=True)[:query.limit]

    def query_metrics(self, query: Query, metric: str = "request_rate") -> list[dict]:
        if metric not in {"request_rate", "error_rate"}:
            raise ValueError("Unsupported metric")
        selector = "http_requests_total{service=" + json.dumps(query.service)
        if metric == "error_rate":
            selector += ',status_code=~"5.."'
        expr = "sum(rate(" + selector + "}[5m]))"
        step = max(15, int((query.end - query.start).total_seconds() / 100))
        data = _request(self.client, self.prometheus, "/api/v1/query_range", {
            "query": expr, "start": _utc(query.start), "end": _utc(query.end),
            "step": step, "limit": 1,
        })
        if data.get("status") != "success" or data.get("data", {}).get("resultType") != "matrix":
            raise TelemetryUnavailable("Unexpected Prometheus response")
        try:
            rows = [
                {"timestamp": timestamp, "value": float(value), "metric": metric,
                 "service": query.service, "source": "prometheus"}
                for series in data["data"]["result"][:1]
                for timestamp, value in series["values"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise TelemetryUnavailable("Unexpected Prometheus response") from exc
        return [row for row in rows if math.isfinite(row["value"])][:query.limit]

    def query_traces(self, query: Query) -> list[dict]:
        data = _request(self.client, self.jaeger, "/api/v3/traces", {
            "query.serviceName": query.service,
            "query.startTimeMin": _utc(query.start),
            "query.startTimeMax": _utc(query.end),
            "query.pagination.pageSize": query.limit,
        }, stream_chunks=True)
        # Jaeger's v3 HTTP response is OTLP TracesData. Do not forward arbitrary
        # span attributes or full raw traces to the consumer.
        result = []
        try:
            for chunk in data:
                payload = chunk.get("result", chunk)
                if not isinstance(payload, dict) or "resourceSpans" not in payload:
                    raise ValueError("Unexpected Jaeger response")
                for resource in payload.get("resourceSpans", []):
                    attrs = resource.get("resource", {}).get("attributes", [])
                    service = next((a["value"].get("stringValue", "") for a in attrs
                                    if a.get("key") == "service.name"), query.service)
                    for scope in resource.get("scopeSpans", []):
                        for span in scope.get("spans", []):
                            trace_id = _hex_id(span["traceId"], 16)
                            result.append({
                                "trace_id": trace_id,
                                "span_id": _hex_id(span["spanId"], 8),
                                "name": str(span.get("name", ""))[:200],
                                "start_time_unix_nano": span.get("startTimeUnixNano"),
                                "service": service, "source": "jaeger",
                            })
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise TelemetryUnavailable("Unexpected Jaeger response") from exc
        return result[:query.limit]

    def get_trace(self, trace_id: str) -> list[dict]:
        if not TRACE_RE.fullmatch(trace_id):
            raise ValueError("Invalid trace ID")
        canonical_id = trace_id.lower().zfill(32)
        data = _request(self.client, self.jaeger, "/api/v3/traces/" + trace_id.lower(), {})
        result = []
        try:
            for resource in data["result"]["resourceSpans"]:
                attrs = resource.get("resource", {}).get("attributes", [])
                service = next((a["value"].get("stringValue", "") for a in attrs
                                if a.get("key") == "service.name"), "")
                for scope in resource.get("scopeSpans", []):
                    for span in scope.get("spans", []):
                        if _hex_id(span["traceId"], 16) != canonical_id:
                            continue
                        result.append({
                            "trace_id": canonical_id, "span_id": _hex_id(span["spanId"], 8),
                            "parent_span_id": _hex_id(span["parentSpanId"], 8) if span.get("parentSpanId") else None,
                            "service": service, "name": str(span.get("name", ""))[:200],
                            "start_time_unix_nano": span.get("startTimeUnixNano"),
                            "end_time_unix_nano": span.get("endTimeUnixNano"),
                            "source": "jaeger",
                        })
                        if len(result) >= MAX_ITEMS:
                            return result
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise TelemetryUnavailable("Unexpected Jaeger response") from exc
        return result
