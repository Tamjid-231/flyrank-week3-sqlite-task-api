import pytest
from fastapi.testclient import TestClient

from app.main import app, tasks


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_tasks():
    tasks[:] = [
        {"id": 1, "title": "Read the assignment", "done": True},
        {"id": 2, "title": "Build the CRUD API", "done": False},
        {"id": 3, "title": "Test it in Swagger UI", "done": False},
    ]


def test_root_and_health():
    assert client.get("/").json() == {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }
    assert client.get("/health").json() == {"status": "ok"}


def test_list_and_get_task():
    response = client.get("/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert client.get("/tasks/1").json()["id"] == 1


def test_unknown_task_returns_json_404():
    response = client.get("/tasks/99")
    assert response.status_code == 404
    assert response.json() == {"error": "Task 99 not found"}


def test_create_task_returns_201_and_saves_it():
    response = client.post("/tasks", json={"title": "Buy milk"})
    assert response.status_code == 201
    assert response.json() == {"id": 4, "title": "Buy milk", "done": False}
    assert len(client.get("/tasks").json()) == 4


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_create_rejects_missing_or_empty_title(body):
    response = client.post("/tasks", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_update_title_and_done():
    response = client.put("/tasks/2", json={"title": "Finish API", "done": True})
    assert response.status_code == 200
    assert response.json() == {"id": 2, "title": "Finish API", "done": True}


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"done": "yes"}])
def test_update_rejects_invalid_body(body):
    response = client.put("/tasks/2", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_update_unknown_task_returns_404():
    response = client.put("/tasks/99", json={"done": True})
    assert response.status_code == 404
    assert response.json() == {"error": "Task 99 not found"}


def test_delete_returns_empty_204():
    response = client.delete("/tasks/3")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/tasks/3").status_code == 404


def test_delete_unknown_task_returns_404():
    response = client.delete("/tasks/99")
    assert response.status_code == 404
    assert response.json() == {"error": "Task 99 not found"}


def test_openapi_documents_assignment_status_codes():
    schema = client.get("/openapi.json").json()
    assert "400" in schema["paths"]["/tasks"]["post"]["responses"]
    assert "422" not in schema["paths"]["/tasks"]["post"]["responses"]
    assert "404" in schema["paths"]["/tasks/{task_id}"]["get"]["responses"]
