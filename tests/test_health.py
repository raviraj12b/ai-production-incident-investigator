from fastapi.testclient import TestClient

from backend.main import app

import backend.main as main_module

client = TestClient(app)


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "incident-demo-api"
    }

def test_inventory(monkeypatch):

    async def fake_fetch_dependency_data():
        return {
            "status": "success",
            "data": {
                "item_id": 101,
                "availability": "in_stock"
            }
        }

    monkeypatch.setattr(
        main_module,
        "fetch_dependency_data",
        fake_fetch_dependency_data
    )

    response = client.get("/inventory")

    assert response.status_code == 200

    assert response.json() == {
        "status": "success",
        "source": "dependency-service",
        "dependency": {
            "status": "success",
            "data": {
                "item_id": 101,
                "availability": "in_stock"
            }
        }
    }