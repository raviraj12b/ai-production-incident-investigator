from fastapi.testclient import TestClient

from dependency_service.main import app


client = TestClient(app)


def test_dependency_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "dependency-service"
    }

    # Verify middleware generated a request ID
    assert "x-request-id" in response.headers


def test_dependency_data():
    response = client.get(
        "/data",
        headers={
            "X-Request-ID": "test-request-123"
        },
    )

    assert response.status_code == 200

    # Verify the same incoming request ID is preserved
    assert response.headers["x-request-id"] == "test-request-123"

    body = response.json()

    assert body["status"] == "success"
    assert body["data"]["item_id"] == 101
    assert body["data"]["availability"] == "in_stock"