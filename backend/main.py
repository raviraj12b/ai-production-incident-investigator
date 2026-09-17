from fastapi import FastAPI

import httpx

from fastapi import FastAPI, HTTPException, Request
from backend.dependency_client import fetch_dependency_data

from telemetry.logging_config import configure_logging
from telemetry.request_logging import add_request_logging


app = FastAPI(
    title="AI Production Incident Investigator - Demo Service",
    description="Production-like service used to generate and investigate incidents.",
    version="0.1.0",
)

configure_logging()

add_request_logging(
    app,
    service_name="incident-demo-api",
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