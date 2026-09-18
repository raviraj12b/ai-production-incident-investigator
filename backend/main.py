import httpx
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from backend.database import session_factory
from backend.dependency_client import fetch_dependency_data
from backend.incidents import router as incidents_router
from telemetry.logging_config import configure_logging
from telemetry.request_logging import add_request_logging
from telemetry.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if session_factory.cache_info().currsize:
        session_factory().kw["bind"].dispose()
        session_factory.cache_clear()


app = FastAPI(
    title="AI Production Incident Investigator - Demo Service",
    description="Production-like service used to generate and investigate incidents.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(incidents_router)
logger = logging.getLogger("incident-demo-api.product")


@app.exception_handler(HTTPException)
async def api_http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/v1/"):
        codes = {404: "NOT_FOUND", 409: "CONFLICT", 422: "VALIDATION_ERROR", 503: "SERVICE_UNAVAILABLE"}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": codes.get(exc.status_code, "HTTP_ERROR"), "message": str(exc.detail)}},
            headers=exc.headers,
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def api_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/v1/"):
        issues = [{"location": list(error["loc"]), "message": error["msg"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "issues": issues}})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(SQLAlchemyError)
async def api_database_error(request: Request, exc: SQLAlchemyError):
    logger.error("product_database_error", extra={"exception_type": type(exc).__name__})
    status = 503 if isinstance(exc, OperationalError) else 500
    return JSONResponse(
        status_code=status,
        content={"error": {"code": "DATABASE_UNAVAILABLE" if status == 503 else "INTERNAL_ERROR", "message": "Product database error"}},
    )


configure_logging()

add_request_logging(
    app,
    service_name="incident-demo-api",
)

configure_tracing(
    app,
    service_name="incident-demo-api",
    instrument_httpx=True,
)


@app.get("/")
def root():
    return {
        "service": "incident-demo-api",
        "message": "AI Production Incident Investigator demo service"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "incident-demo-api"
    }


@app.get("/ready")
def readiness():
    try:
        engine = session_factory().kw["bind"]
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        if version != "phase05_0001":
            raise RuntimeError("Database migration is not at the expected revision")
    except (RuntimeError, SQLAlchemyError) as exc:
        raise HTTPException(status_code=503, detail="Product database is not ready") from exc
    return {"status": "ready"}


@app.get("/inventory")
async def get_inventory(request: Request):
    try:
        dependency_response = await fetch_dependency_data(
            request.state.request_id
        )

        return {
            "status": "success",
            "source": "dependency-service",
            "dependency": dependency_response
        }

    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise HTTPException(
            status_code=503,
            detail="Dependency service unavailable"
        )

    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=504,
            detail="Dependency service timed out"
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Dependency service timed out"
        )

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Dependency service returned "
                f"HTTP {exc.response.status_code}"
            )
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Dependency service unavailable"
        )
