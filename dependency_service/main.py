import asyncio

from fastapi import FastAPI, HTTPException

from dependency_service.incident_state import (
    IncidentMode,
    get_incident_mode,
    set_incident_mode,
)
from telemetry.logging_config import configure_logging
from telemetry.request_logging import add_request_logging


app = FastAPI(
    title="Dependency Service",
    description="Downstream service used for controlled incident simulation.",
    version="0.1.0",
)


configure_logging()

add_request_logging(
    app,
    service_name="dependency-service",
    excluded_path_prefixes=("/control/",),
)


@app.get("/")
def root():
    return {
        "service": "dependency-service",
        "message": "Dependency service is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "dependency-service"
    }


@app.get("/data")
async def get_data():
    incident_mode = get_incident_mode()

    if incident_mode == IncidentMode.LATENCY:
        await asyncio.sleep(3.0)

    elif incident_mode == IncidentMode.ERROR:
        raise HTTPException(
            status_code=500,
            detail="Injected dependency failure"
        )

    return {
        "status": "success",
        "data": {
            "item_id": 101,
            "availability": "in_stock"
        }
    }


@app.get("/control/mode")
def get_current_incident_mode():
    return {
        "mode": get_incident_mode().value
    }


@app.post("/control/mode/{mode}")
def change_incident_mode(mode: IncidentMode):
    set_incident_mode(mode)

    return {
        "mode": mode.value
    }