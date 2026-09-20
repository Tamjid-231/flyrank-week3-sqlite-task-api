from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator


app = FastAPI(
    title="Task API",
    version="1.0.0",
    description="A beginner-friendly in-memory CRUD API for managing tasks.",
)


class Task(BaseModel):
    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str):
        if not value.strip():
            raise ValueError("title must not be empty")
        return value.strip()


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    done: StrictBool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str | None):
        if value is not None and not value.strip():
            raise ValueError("title must not be empty")
        return value.strip() if value is not None else value


tasks = [
    {"id": 1, "title": "Read the assignment", "done": True},
    {"id": 2, "title": "Build the CRUD API", "done": False},
    {"id": 3, "title": "Test it in Swagger UI", "done": False},
]


def find_task(task_id: int):
    return next((task for task in tasks if task["id"] == task_id), None)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]
    message = first_error.get("msg", "Invalid request body")
    return JSONResponse(status_code=400, content={"error": message})


@app.get("/", summary="Describe the API", tags=["System"])
def api_information():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Check server health", tags=["System"])
def health_check():
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], summary="List all tasks", tags=["Tasks"])
def list_tasks():
    return tasks


@app.get("/tasks/{task_id}", response_model=Task, summary="Get one task", tags=["Tasks"])
def get_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"},
        )
    return task


@app.post(
    "/tasks",
    response_model=Task,
    status_code=201,
    summary="Create a task",
    tags=["Tasks"],
)
def create_task(task_data: TaskCreate):
    next_id = max((task["id"] for task in tasks), default=0) + 1
    new_task = {"id": next_id, "title": task_data.title, "done": False}
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}", response_model=Task, summary="Update a task", tags=["Tasks"])
def update_task(task_id: int, task_data: TaskUpdate):
    task = find_task(task_id)
    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"},
        )

    changes = task_data.model_dump(exclude_none=True)
    if not changes:
        return JSONResponse(
            status_code=400,
            content={"error": "Provide title and/or done"},
        )

    task.update(changes)
    return task


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task", tags=["Tasks"])
def delete_task(task_id: int):
    task = find_task(task_id)
    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"},
        )

    tasks.remove(task)
    return None


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            responses = operation.get("responses", {})
            responses.pop("422", None)
            if method in {"post", "put"}:
                responses.setdefault("400", {"description": "Invalid request body"})
            if "{task_id}" in path:
                responses.setdefault("404", {"description": "Task not found"})

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
