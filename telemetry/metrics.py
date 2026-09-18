"""Small Prometheus scrape surface with bounded HTTP label cardinality."""

import time

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST
from starlette.routing import Match


def add_metrics(app: FastAPI, service_name: str) -> None:
    registry = CollectorRegistry()
    requests = Counter("http_requests_total", "HTTP requests", (
        "service", "method", "route", "status_code",
    ), registry=registry)
    duration = Histogram("http_request_duration_seconds", "HTTP request duration", (
        "service", "method", "route",
    ), registry=registry)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def measure(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            if route is None:
                # HTTP middleware can finish without a route in its scope.
                # Resolve against registered templates instead of labeling a
                # request with its raw path (which may contain an ID).
                route = next((candidate for candidate in app.router.routes
                              if candidate.matches(request.scope)[0] == Match.FULL), None)
            # Route templates are bounded; never put raw paths or IDs in labels.
            label = getattr(route, "path", "unmatched")
            method = request.method if request.method in {"GET", "POST", "PATCH", "PUT", "DELETE"} else "OTHER"
            requests.labels(service_name, method, label, str(status)).inc()
            duration.labels(service_name, method, label).observe(time.perf_counter() - start)
