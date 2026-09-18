import os
import logging

from fastapi import FastAPI

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_tracing_configured = False


def configure_tracing(
    app: FastAPI,
    service_name: str,
    instrument_httpx: bool = False,
):
    global _tracing_configured

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

    otlp_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "http://127.0.0.1:4318/v1/traces",
    )

    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)

    # The original debug Collector config has no logs pipeline. Enable logs
    # only when the queryable Collector configuration is running.
    if os.getenv("OTEL_LOGS_ENABLED", "false").lower() == "true":
        log_provider = LoggerProvider(resource=resource)
        log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(
            endpoint=os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://127.0.0.1:4318/v1/logs"),
        )))
        logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=log_provider))

    FastAPIInstrumentor.instrument_app(app)

    if instrument_httpx:
        HTTPXClientInstrumentor().instrument()

    _tracing_configured = True
