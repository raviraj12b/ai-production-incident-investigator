import logging
import time

import httpx


SERVICE_NAME = "incident-demo-api"
DEPENDENCY_SERVICE_NAME = "dependency-service"

DEPENDENCY_BASE_URL = "http://127.0.0.1:8001"
DEPENDENCY_DATA_URL = f"{DEPENDENCY_BASE_URL}/data"

REQUEST_TIMEOUT_SECONDS = 2.0


logger = logging.getLogger(
    f"{SERVICE_NAME}.dependencies"
)


async def fetch_dependency_data(
    request_id: str,
):
    start_time = time.perf_counter()

    logger.info(
        "dependency_call_started",
        extra={
            "service": SERVICE_NAME,
            "event": "dependency_call_started",
            "request_id": request_id,
            "downstream_service": DEPENDENCY_SERVICE_NAME,
            "dependency_url": DEPENDENCY_DATA_URL,
        },
    )

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_SECONDS
        ) as client:

            response = await client.get(
                DEPENDENCY_DATA_URL,
                headers={
                    "X-Request-ID": request_id,
                },
            )

            response.raise_for_status()

    except httpx.TimeoutException as exc:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "dependency_call_failed",
            extra={
                "service": SERVICE_NAME,
                "event": "dependency_call_failed",
                "request_id": request_id,
                "downstream_service": DEPENDENCY_SERVICE_NAME,
                "dependency_url": DEPENDENCY_DATA_URL,
                "duration_ms": round(duration_ms, 2),
                "exception_type": type(exc).__name__,
                "error": str(exc),
            },
        )

        raise

    except httpx.HTTPStatusError as exc:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "dependency_call_failed",
            extra={
                "service": SERVICE_NAME,
                "event": "dependency_call_failed",
                "request_id": request_id,
                "downstream_service": DEPENDENCY_SERVICE_NAME,
                "dependency_url": DEPENDENCY_DATA_URL,
                "status_code": exc.response.status_code,
                "duration_ms": round(duration_ms, 2),
                "exception_type": type(exc).__name__,
                "error": str(exc),
            },
        )

        raise

    except httpx.RequestError as exc:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "dependency_call_failed",
            extra={
                "service": SERVICE_NAME,
                "event": "dependency_call_failed",
                "request_id": request_id,
                "downstream_service": DEPENDENCY_SERVICE_NAME,
                "dependency_url": DEPENDENCY_DATA_URL,
                "duration_ms": round(duration_ms, 2),
                "exception_type": type(exc).__name__,
                "error": str(exc),
            },
        )

        raise

    duration_ms = (
        time.perf_counter() - start_time
    ) * 1000

    logger.info(
        "dependency_call_completed",
        extra={
            "service": SERVICE_NAME,
            "event": "dependency_call_completed",
            "request_id": request_id,
            "downstream_service": DEPENDENCY_SERVICE_NAME,
            "dependency_url": DEPENDENCY_DATA_URL,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )

    return response.json()