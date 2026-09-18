"""Check bounded query construction against the documented HTTP response shapes."""

import base64
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from backend.telemetry_gateway import Query, TelemetryGateway, TelemetryUnavailable
from dependency_service.main import app as dependency_app


START = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
TRACE = "a" * 32
SPAN = "b" * 16


def _query(**kwargs):
    return Query("incident-demo-api", START, START + timedelta(minutes=15), **kwargs)


def test_query_rejects_unbounded_or_unsafe_inputs():
    with pytest.raises(ValueError):
        Query('demo"} | delete', START, START + timedelta(minutes=1))
    with pytest.raises(ValueError):
        Query("demo", START.replace(tzinfo=None), START + timedelta(minutes=1))
    with pytest.raises(ValueError):
        Query("demo", START, START + timedelta(days=2))
    with pytest.raises(ValueError):
        _query(limit=101)
    with TelemetryGateway(client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200)))) as gateway:
        with pytest.raises(ValueError):
            gateway.query_metrics(_query(), metric='up{job="secret"}')
        with pytest.raises(ValueError):
            gateway.get_trace("../../etc/passwd")


def test_logs_query_uses_service_filter_and_keeps_provenance():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/loki/api/v1/query_range"
        assert request.url.params["query"] == '{service_name="incident-demo-api"}'
        assert request.url.params["limit"] == "2"
        return httpx.Response(200, json={"status": "success", "data": {
            "resultType": "streams", "result": [{"stream": {"service_name": "incident-demo-api"},
                "values": [["1770000000000000000", "request_completed", {
                    "trace_id": TRACE, "request_id": "req-1", "severity_text": "INFO"}]]}]
        }})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with TelemetryGateway(client=client) as gateway:
            result = gateway.query_logs(_query(limit=2))
    assert result[0]["trace_id"] == TRACE
    assert result[0]["request_id"] == "req-1"
    assert result[0]["source"] == "loki"


def test_metrics_query_is_allowlisted_and_numeric():
    def handler(request):
        assert request.url.path == "/api/v1/query_range"
        assert request.url.params["query"] == 'sum(rate(http_requests_total{service="incident-demo-api",status_code=~"5.."}[5m]))'
        return httpx.Response(200, json={"status": "success", "data": {
            "resultType": "matrix", "result": [{"values": [[1770000000, "0.25"]]}]
        }})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with TelemetryGateway(client=client) as gateway:
            result = gateway.query_metrics(_query(), "error_rate")
    assert result == [{"timestamp": 1770000000, "value": 0.25, "metric": "error_rate",
                       "service": "incident-demo-api", "source": "prometheus"}]


def test_trace_lookup_normalizes_otlp_base64_ids_and_discards_attributes():
    def handler(request):
        assert request.url.path == "/api/v3/traces/" + TRACE
        return httpx.Response(200, json={"result": {"resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "dependency-service"}}]},
            "scopeSpans": [{"spans": [{"traceId": base64.b64encode(bytes.fromhex(TRACE)).decode(),
                                      "spanId": base64.b64encode(bytes.fromhex(SPAN)).decode(),
                                      "name": "GET /data", "attributes": [{"key": "secret", "value": {"stringValue": "hidden"}}]}]}]
        }]}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with TelemetryGateway(client=client) as gateway:
            result = gateway.get_trace(TRACE)
    assert result[0]["service"] == "dependency-service"
    assert result[0]["span_id"] == SPAN
    assert "attributes" not in result[0]


def test_trace_search_and_backend_failure():
    def handler(request):
        if request.url.path == "/api/v3/traces":
            assert request.url.params["query.serviceName"] == "incident-demo-api"
            assert request.url.params["query.pagination.pageSize"] == "50"
            return httpx.Response(200, json={"resourceSpans": [{"scopeSpans": [{"spans": [
                {"traceId": TRACE, "spanId": SPAN, "name": "GET /inventory"}
            ]}]}]})
        return httpx.Response(503)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with TelemetryGateway(client=client) as gateway:
            assert gateway.query_traces(_query())[0]["trace_id"] == TRACE
            with pytest.raises(TelemetryUnavailable):
                gateway.query_logs(_query())


def test_dependency_metrics_are_scrapable_without_raw_path_labels():
    with TestClient(dependency_app) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/control/mode/normal").status_code == 200
        body = client.get("/metrics").text
    samples = [sample for family in text_string_to_metric_families(body)
               for sample in family.samples if sample.name == "http_requests_total"]
    assert any(sample.labels == {
        "service": "dependency-service", "method": "GET",
        "route": "/health", "status_code": "200",
    } for sample in samples), body
    assert any(sample.labels == {
        "service": "dependency-service", "method": "POST",
        "route": "/control/mode/{mode}", "status_code": "200",
    } for sample in samples), body
