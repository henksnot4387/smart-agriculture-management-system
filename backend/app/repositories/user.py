from __future__ import annotations

from typing import Any

import psycopg

from app.core.config import Settings


class UserRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def get_active_user(self, *, user_id: str) -> dict[str, Any] | None:
        sql = """
        SELECT id::text AS id, email, name, role::text AS role, is_active
        FROM users
        WHERE id = %s::uuid
        LIMIT 1
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, [user_id])
                return cursor.fetchone()
