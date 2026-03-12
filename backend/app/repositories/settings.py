from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings


class SettingsRepository:
    _schema_lock_key = 98421103

    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def ensure_schema(self) -> None:
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS automation_rule_profiles (
                profile_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                config JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_by_id UUID,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_triggered_at TIMESTAMPTZ,
                last_task_id UUID
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS automation_rule_profiles_updated_idx
            ON automation_rule_profiles (updated_at DESC)
            """,
        ]
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [self._schema_lock_key])
                try:
                    for statement in sql_statements:
                        cursor.execute(statement)
                finally:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [self._schema_lock_key])
            conn.commit()

    def list_profiles(self) -> list[dict[str, Any]]:
        self.ensure_schema()
        sql = """
        SELECT
            profile_key,
            title,
            description,
            enabled,
            config,
            updated_by_id::text AS updated_by_id,
            updated_at,
            last_triggered_at,
            last_task_id::text AS last_task_id
        FROM automation_rule_profiles
        ORDER BY profile_key ASC
        """
        return self._fetch_all(sql, [])

    def get_profile(self, *, profile_key: str) -> dict[str, Any] | None:
        self.ensure_schema()
        sql = """
        SELECT
            profile_key,
            title,
            description,
            enabled,
            config,
            updated_by_id::text AS updated_by_id,
            updated_at,
            last_triggered_at,
            last_task_id::text AS last_task_id
        FROM automation_rule_profiles
        WHERE profile_key = %s
        LIMIT 1
        """
        rows = self._fetch_all(sql, [profile_key])
        return rows[0] if rows else None

    def upsert_profile(
        self,
        *,
        profile_key: str,
        title: str,
        description: str,
        enabled: bool,
        config: dict[str, Any],
        updated_by_id: str,
    ) -> dict[str, Any]:
        self.ensure_schema()
        sql = """
        INSERT INTO automation_rule_profiles (
            profile_key,
            title,
            description,
            enabled,
            config,
            updated_by_id,
            updated_at,
            created_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s::jsonb,
            %s::uuid,
            NOW(),
            NOW()
        )
        ON CONFLICT (profile_key)
        DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            enabled = EXCLUDED.enabled,
            config = EXCLUDED.config,
            updated_by_id = EXCLUDED.updated_by_id,
            updated_at = NOW()
        RETURNING
            profile_key,
            title,
            description,
            enabled,
            config,
            updated_by_id::text AS updated_by_id,
            updated_at,
            last_triggered_at,
            last_task_id::text AS last_task_id
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(
                    sql,
                    [
                        profile_key,
                        title,
                        description,
                        enabled,
                        Jsonb(config),
                        updated_by_id,
                    ],
                )
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to upsert settings profile.")
        return dict(row)

    def mark_triggered(self, *, profile_key: str, task_id: str | None) -> None:
        self.ensure_schema()
        sql = """
        UPDATE automation_rule_profiles
        SET
            last_triggered_at = NOW(),
            last_task_id = %s::uuid
        WHERE profile_key = %s
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, [task_id, profile_key])
            conn.commit()

    def _fetch_all(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
