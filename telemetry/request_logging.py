import logging
import time
import uuid

from fastapi import FastAPI, Request


def add_request_logging(
    app: FastAPI,
    service_name: str,
):
    logger = logging.getLogger(
        f"{service_name}.requests"
    )

    @app.middleware("http")
    async def request_logging_middleware(
        request: Request,
        call_next,
    ):
        request_id = (
            request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

        request.state.request_id = request_id

        start_time = time.perf_counter()

        try:
            response = await call_next(request)

        except Exception:
            duration_ms = (
                time.perf_counter() - start_time
            ) * 1000

            logger.exception(
                "request_failed",
                extra={
                    "service": service_name,
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            raise

        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            extra={
                "service": service_name,
                "event": "request_completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return response