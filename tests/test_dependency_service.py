import pytest

from fastapi.testclient import TestClient

from dependency_service.incident_state import (
    IncidentMode,
    set_incident_mode,
)
from dependency_service.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_incident_mode():
    set_incident_mode(IncidentMode.NORMAL)

    yield

    set_incident_mode(IncidentMode.NORMAL)


def test_dependency_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dependency-service"
    }

    assert "x-request-id" in response.headers


def test_dependency_data():
    response = client.get(
        "/data",
        headers={
            "X-Request-ID": "test-request-123"
        },
    )

    assert response.status_code == 200

    assert (
        response.headers["x-request-id"]
        == "test-request-123"
    )

    body = response.json()

    assert body["status"] == "success"
    assert body["data"]["item_id"] == 101
    assert body["data"]["availability"] == "in_stock"


def test_dependency_error_incident():
    control_response = client.post(
        "/control/mode/error"
    )

    assert control_response.status_code == 200
    assert control_response.json() == {
        "mode": "error"
    }

    response = client.get("/data")

    assert response.status_code == 500


def test_incident_mode_can_be_reset():
    client.post("/control/mode/error")

    reset_response = client.post(
        "/control/mode/normal"
    )

    assert reset_response.status_code == 200
    assert reset_response.json() == {
        "mode": "normal"
    }

    response = client.get("/data")

    assert response.status_code == 200