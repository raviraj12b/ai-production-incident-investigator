import os

from fastapi import FastAPI

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)


_tracing_configured = False


def configure_tracing(
    app: FastAPI,
    service_name: str,
    instrument_httpx: bool = False,
):
    global _tracing_configured

    # Keep tracing disabled during normal tests unless explicitly enabled.
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return

    if _tracing_configured:
        return

    resource = Resource.create(
        {
            "service.name": service_name,
        }
    )

    provider = TracerProvider(
        resource=resource
    )

    provider.add_span_processor(
        BatchSpanProcessor(
            ConsoleSpanExporter()
        )
    )

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)

    if instrument_httpx:
        HTTPXClientInstrumentor().instrument()

    _tracing_configured = True