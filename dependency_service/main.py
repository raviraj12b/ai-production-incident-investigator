from fastapi import FastAPI

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
def get_data():
    return {
        "status": "success",
        "data": {
            "item_id": 101,
            "availability": "in_stock"
        }
    }