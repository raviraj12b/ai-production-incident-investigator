import json
import logging
import sys
from datetime import datetime, timezone
from opentelemetry import trace

STRUCTURED_FIELDS = (
    "service",
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "downstream_service",
    "dependency_url",
    "exception_type",
    "error",
)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add custom structured fields.
        for field in STRUCTURED_FIELDS:
            value = getattr(record, field, None)

            if value is not None:
                log_entry[field] = value

        # Correlate application logs with the active OpenTelemetry span.
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context()

        if span_context.is_valid:
            log_entry["trace_id"] = format(
                span_context.trace_id,
                "032x",
            )

            log_entry["span_id"] = format(
                span_context.span_id,
                "016x",
            )

        if record.exc_info:
            log_entry["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            log_entry,
            ensure_ascii=False,
        )

def configure_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)