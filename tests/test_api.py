import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


client = TestClient(app)


def test_database_is_created_with_three_seed_tasks(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database, raising=False)

    main.initialize_database()

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert count == 3


def test_repeated_initialization_does_not_duplicate_seeds(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database, raising=False)

    main.initialize_database()
    main.initialize_database()
    main.initialize_database()

    with sqlite3.connect(database) as connection:
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    assert count == 3


def test_root_and_health():
    assert client.get("/").json() == {
        "name": "Task API",
        "version": "2.0",
        "endpoints": ["/tasks"],
    }
    assert client.get("/health").json() == {"status": "ok"}


def test_list_and_get_task_read_live_database(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE tasks SET title = ? WHERE id = ?",
            ("Changed directly in SQLite", 1),
        )

    response = client.get("/tasks")

    assert response.status_code == 200
    assert len(response.json()) == 3
    assert response.json()[0] == {
        "id": 1,
        "title": "Changed directly in SQLite",
        "done": True,
    }
    assert client.get("/tasks/1").json() == response.json()[0]


def test_unknown_task_returns_json_404():
    response = client.get("/tasks/99")
    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_create_task_returns_201_and_saves_it(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()

    response = client.post("/tasks", json={"title": "Buy milk"})

    assert response.status_code == 201
    assert response.json() == {"id": 4, "title": "Buy milk", "done": False}
    assert len(client.get("/tasks").json()) == 4


def test_create_uses_parameterized_sql_for_title(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()
    title = "Robert'); DROP TABLE tasks;--"

    response = client.post("/tasks", json={"title": title})

    assert response.status_code == 201
    assert response.json()["title"] == title
    tasks_response = client.get("/tasks")
    assert tasks_response.status_code == 200
    assert len(tasks_response.json()) == 4


def test_created_task_survives_a_fresh_database_connection(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()

    created = client.post("/tasks", json={"title": "Persistent task"}).json()

    with sqlite3.connect(database) as connection:
        saved = connection.execute(
            "SELECT title, done FROM tasks WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert saved == ("Persistent task", 0)


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"title": "   "}])
def test_create_rejects_missing_or_empty_title(body):
    response = client.post("/tasks", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_update_title_and_done_persists_in_database(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()

    response = client.put("/tasks/2", json={"title": "Finish API", "done": True})

    assert response.status_code == 200
    assert response.json() == {"id": 2, "title": "Finish API", "done": True}
    assert client.get("/tasks/2").json() == response.json()
    with sqlite3.connect(database) as connection:
        saved = connection.execute(
            "SELECT title, done FROM tasks WHERE id = ?", (2,)
        ).fetchone()
    assert saved == ("Finish API", 1)


@pytest.mark.parametrize("body", [{}, {"title": ""}, {"done": "yes"}])
def test_update_rejects_invalid_body(body):
    response = client.put("/tasks/2", json=body)
    assert response.status_code == 400
    assert "error" in response.json()


def test_update_unknown_task_returns_404():
    response = client.put("/tasks/99", json={"done": True})
    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_delete_returns_empty_204_and_removes_database_row(tmp_path, monkeypatch):
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(main, "DB_PATH", database)
    main.initialize_database()

    response = client.delete("/tasks/3")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/tasks/3").status_code == 404


def test_delete_unknown_task_returns_404():
    response = client.delete("/tasks/99")
    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_openapi_documents_assignment_status_codes():
    schema = client.get("/openapi.json").json()
    assert "400" in schema["paths"]["/tasks"]["post"]["responses"]
    assert "422" not in schema["paths"]["/tasks"]["post"]["responses"]
    assert "404" in schema["paths"]["/tasks/{task_id}"]["get"]["responses"]
