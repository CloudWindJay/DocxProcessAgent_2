"""
Small startup schema helpers for lightweight column bootstrapping.

This project does not use Alembic yet, so we add a narrow, explicit
bootstrap step for newly introduced user LLM settings columns.
"""
from __future__ import annotations

from sqlalchemy import inspect, text


def ensure_user_llm_settings_columns(engine) -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "llm_provider" not in existing:
        statements.append(
            "ALTER TABLE users ADD COLUMN llm_provider VARCHAR(50) NOT NULL DEFAULT 'qwen'"
        )
    if "llm_use_env_key" not in existing:
        statements.append(
            "ALTER TABLE users ADD COLUMN llm_use_env_key BOOLEAN NOT NULL DEFAULT TRUE"
        )
    if "llm_api_key" not in existing:
        statements.append(
            "ALTER TABLE users ADD COLUMN llm_api_key TEXT NULL"
        )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
