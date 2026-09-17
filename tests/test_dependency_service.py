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


def test_dependency_data():
    response = client.get("/data")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "success"
    assert body["data"]["item_id"] == 101
    assert body["data"]["availability"] == "in_stock"