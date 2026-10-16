from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.base import Base


settings = get_settings()

if settings.database_url.startswith("sqlite:///"):
    database_path = Path(settings.database_url.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def initialize_database() -> None:
    """建立数据库连接并创建当前已注册的数据表。"""
    import app.models  # noqa: F401  确保声明式模型在 create_all 前完成注册

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        # Forward compatible SQLite upgrade for installations created before V2.0.
        if engine.dialect.name == "sqlite":
            def has_column(table: str, column: str) -> bool:
                return column in {row[1] for row in connection.exec_driver_sql(
                    f"PRAGMA table_info({table})").fetchall()}
            for table, column, definition in (
                ("users", "organization_id", "INTEGER"),
                ("users", "role", "VARCHAR(24) NOT NULL DEFAULT 'admin'"),
                ("greenhouses", "organization_id", "INTEGER"),
                ("ai_conversations", "owner_user_id", "INTEGER"),
                ("farm_tasks", "created_by_user_id", "INTEGER"),
                ("task_events", "operator_user_id", "INTEGER"),
                ("task_feedbacks", "operator_user_id", "INTEGER"),
                ("decision_recommendations", "reviewed_by_user_id", "INTEGER"),
                ("disease_recognition_records", "reviewed_by_user_id", "INTEGER"),
                ("warning_events", "last_operator_user_id", "INTEGER"),
                ("outcome_observations", "target_at", "DATETIME"),
                ("outcome_observations", "sample_delta_seconds", "INTEGER"),
            ):
                if not has_column(table, column):
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            # Give every existing account its own workspace. Existing shared data
            # stays in a quarantine organization until an administrator assigns it.
            for user_id, name, existing_org in connection.exec_driver_sql(
                "SELECT id, display_name, organization_id FROM users").fetchall():
                if existing_org is None:
                    result = connection.execute(text(
                        "INSERT INTO organizations (name, created_at) VALUES (:name, CURRENT_TIMESTAMP)"),
                        {"name": f"{name}的空间"})
                    connection.execute(text("UPDATE users SET organization_id=:org WHERE id=:id"),
                                       {"org": result.lastrowid, "id": user_id})
            unassigned = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM greenhouses WHERE organization_id IS NULL").scalar_one()
            if unassigned:
                users = connection.exec_driver_sql("SELECT organization_id FROM users").fetchall()
                if len(users) == 1:
                    org_id = users[0][0]
                else:
                    result = connection.execute(text(
                        "INSERT INTO organizations (name, created_at) VALUES ('历史数据待认领', CURRENT_TIMESTAMP)"))
                    org_id = result.lastrowid
                connection.execute(text("UPDATE greenhouses SET organization_id=:org WHERE organization_id IS NULL"),
                                   {"org": org_id})
        connection.execute(text("SELECT 1"))


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
