from contextlib import asynccontextmanager

from fastapi import FastAPI, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, Session

DATABASE_URL = "postgresql+psycopg2://postgres:123@localhost:5432/postgres"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))

class TaskORM(Base):
    __tablename__ = "tasks"

    title: Mapped[str]
    completed: Mapped[bool] = mapped_column(default=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
)


class TaskSchema(BaseModel):
    id: str
    title: str
    completed: bool

class TaskCreateSchema(BaseModel):
    title: str

class TaskUpdateSchema(BaseModel):
    title: str | None = None
    completed: bool | None = None


def get_database():
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def task_orm_to_model(task_orm: TaskORM) -> TaskSchema:
    return TaskSchema(
        id=task_orm.id,
        title=task_orm.title,
        completed=task_orm.completed
    )

@app.get("/tasks")
def read_tasks(database: Session = Depends(get_database)) -> list[TaskSchema]:
    tasks_from_database = database.scalars(select(TaskORM)).all()
    return [task_orm_to_model(task) for task in tasks_from_database]

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreateSchema, database: Session = Depends(get_database)) -> TaskSchema:
    new_task = TaskORM(title=payload.title, completed=False)
    database.add(new_task)
    database.commit()
    database.refresh(new_task)
    return task_orm_to_model(new_task)

@app.patch("/tasks/{task_id}")
def update_task(task_id: str,payload: TaskUpdateSchema, database: Session = Depends(get_database)) -> TaskSchema:
    task_for_update = database.get(TaskORM, task_id)
    if payload.title:
        task_for_update.title = payload.title
    if payload.completed is not None:
        task_for_update.completed = payload.completed

    database.commit()
    return task_orm_to_model(task_for_update)

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, database: Session = Depends(get_database)):
    task_for_delete = database.get(TaskORM, task_id)
    database.delete(task_for_delete)
    database.commit()