from fastapi.testclient import TestClient

from api.main import app


def test_health_reports_status_and_model_state():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["model_loaded"], bool)


def test_swagger_docs_list_health_endpoint():
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200
        assert "/health" in client.get("/openapi.json").json()["paths"]
