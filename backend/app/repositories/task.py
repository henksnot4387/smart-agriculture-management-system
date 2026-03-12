from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import Settings


class TaskRepository:
    def __init__(self, settings: Settings):
        self._database_url = settings.psycopg_database_url

    def create_ai_task(
        self,
        *,
        title: str,
        description: str,
        priority: str,
        created_by_id: str,
        due_at: datetime | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        sql = """
        INSERT INTO tasks (
            id,
            title,
            description,
            status,
            priority,
            source,
            metadata,
            created_by_id,
            due_at,
            created_at,
            updated_at
        )
        VALUES (
            %(id)s::uuid,
            %(title)s,
            %(description)s,
            'PENDING'::"TaskStatus",
            %(priority)s::"TaskPriority",
            'AI'::"TaskSource",
            %(metadata)s,
            %(created_by_id)s::uuid,
            %(due_at)s,
            NOW(),
            NOW()
        )
        RETURNING id::text, title, description, status::text, priority::text, created_at, metadata
        """
        payload = {
            "id": str(uuid4()),
            "title": title,
            "description": description,
            "priority": priority,
            "metadata": Jsonb(metadata),
            "created_by_id": created_by_id,
            "due_at": due_at,
        }
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, payload)
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to create AI task.")
        return row

    def create_system_task(
        self,
        *,
        title: str,
        description: str,
        priority: str,
        source: str,
        created_by_id: str,
        due_at: datetime | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        sql = """
        INSERT INTO tasks (
            id,
            title,
            description,
            status,
            priority,
            source,
            metadata,
            created_by_id,
            due_at,
            created_at,
            updated_at
        )
        VALUES (
            %(id)s::uuid,
            %(title)s,
            %(description)s,
            'PENDING'::"TaskStatus",
            %(priority)s::"TaskPriority",
            %(source)s::"TaskSource",
            %(metadata)s,
            %(created_by_id)s::uuid,
            %(due_at)s,
            NOW(),
            NOW()
        )
        RETURNING id::text, title, description, status::text, priority::text, source::text, created_at, metadata
        """
        payload = {
            "id": str(uuid4()),
            "title": title,
            "description": description,
            "priority": priority,
            "source": source,
            "metadata": Jsonb(metadata),
            "created_by_id": created_by_id,
            "due_at": due_at,
        }
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, payload)
                row = cursor.fetchone()
            conn.commit()
        if not row:
            raise RuntimeError("Failed to create system task.")
        return row

    def list_ai_tasks(self, *, limit: int, status: str | None) -> tuple[int, list[dict[str, Any]]]:
        params: list[Any] = []
        where_clauses = [
            "source = 'AI'::\"TaskSource\"",
        ]
        if status:
            where_clauses.append("status = %s::\"TaskStatus\"")
            params.append(status)
        where_sql = " AND ".join(where_clauses)

        count_sql = f"""
        SELECT COUNT(*)::int AS total
        FROM tasks
        WHERE {where_sql}
        """

        list_sql = f"""
        SELECT
            id,
            title,
            description,
            status,
            priority,
            metadata,
            created_at
        FROM tasks
        WHERE {where_sql}
        ORDER BY created_at DESC
        LIMIT %s
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(count_sql, params)
                count_row = cursor.fetchone()
                cursor.execute(list_sql, [*params, limit])
                items = list(cursor.fetchall())
        total = int((count_row or {}).get("total") or 0)
        return total, items

    def list_tasks(
        self,
        *,
        limit: int,
        status: str | None,
        source: str | None,
        assigned_to: str,
        user_id: str,
        worker_scope: bool,
    ) -> tuple[int, list[dict[str, Any]]]:
        params: list[Any] = []
        where_clauses: list[str] = []

        if status:
            where_clauses.append("t.status = %s::\"TaskStatus\"")
            params.append(status)
        if source:
            where_clauses.append("t.source = %s::\"TaskSource\"")
            params.append(source)

        if assigned_to == "me":
            where_clauses.append("t.assignee_id = %s::uuid")
            params.append(user_id)
        elif assigned_to == "unassigned":
            where_clauses.append("t.assignee_id IS NULL")

        if worker_scope:
            where_clauses.append(
                "(t.assignee_id = %s::uuid OR (t.assignee_id IS NULL AND t.status = 'APPROVED'::\"TaskStatus\"))"
            )
            params.append(user_id)

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        count_sql = f"""
        SELECT COUNT(*)::int AS total
        FROM tasks t
        WHERE {where_sql}
        """
        list_sql = f"""
        {self._task_select_base_sql()}
        WHERE {where_sql}
        ORDER BY t.created_at DESC
        LIMIT %s
        """

        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(count_sql, params)
                count_row = cursor.fetchone()
                cursor.execute(list_sql, [*params, limit])
                items = list(cursor.fetchall())
        return int((count_row or {}).get("total") or 0), items

    def get_task_by_id(self, *, task_id: str) -> dict[str, Any] | None:
        sql = f"""
        {self._task_select_base_sql()}
        WHERE t.id = %s::uuid
        LIMIT 1
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, [task_id])
                return cursor.fetchone()

    def list_worker_assignees(self) -> list[dict[str, Any]]:
        sql = """
        SELECT id::text AS id, email, name, role::text AS role
        FROM users
        WHERE role = 'WORKER'::"UserRole" AND is_active = TRUE
        ORDER BY email ASC
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql)
                return list(cursor.fetchall())

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

    def get_first_management_user_id(self) -> str | None:
        sql = """
        SELECT id::text AS id
        FROM users
        WHERE is_active = TRUE
          AND role IN ('SUPER_ADMIN'::"UserRole", 'ADMIN'::"UserRole", 'EXPERT'::"UserRole")
        ORDER BY
          CASE role
            WHEN 'SUPER_ADMIN'::"UserRole" THEN 0
            WHEN 'ADMIN'::"UserRole" THEN 1
            ELSE 2
          END,
          created_at ASC
        LIMIT 1
        """
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
        return str(row["id"]) if row and row.get("id") else None

    def approve_task(
        self,
        *,
        task_id: str,
        approved_by_id: str,
        assignee_id: str | None,
    ) -> dict[str, Any] | None:
        sql = f"""
        WITH updated AS (
            UPDATE tasks t
            SET
                status = 'APPROVED'::"TaskStatus",
                approved_by_id = %s::uuid,
                approved_at = NOW(),
                assignee_id = %s::uuid,
                updated_at = NOW()
            WHERE
                t.id = %s::uuid
                AND t.status = 'PENDING'::"TaskStatus"
            RETURNING t.*
        )
        {self._task_select_base_sql(from_table='updated t')}
        LIMIT 1
        """
        return self._fetch_one(sql, [approved_by_id, assignee_id, task_id])

    def claim_task(
        self,
        *,
        task_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        sql = f"""
        WITH updated AS (
            UPDATE tasks t
            SET
                assignee_id = %s::uuid,
                updated_at = NOW()
            WHERE
                t.id = %s::uuid
                AND t.status = 'APPROVED'::"TaskStatus"
                AND t.assignee_id IS NULL
            RETURNING t.*
        )
        {self._task_select_base_sql(from_table='updated t')}
        LIMIT 1
        """
        return self._fetch_one(sql, [user_id, task_id])

    def start_task(
        self,
        *,
        task_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        sql = f"""
        WITH updated AS (
            UPDATE tasks t
            SET
                status = 'IN_PROGRESS'::"TaskStatus",
                started_at = COALESCE(t.started_at, NOW()),
                updated_at = NOW()
            WHERE
                t.id = %s::uuid
                AND t.status = 'APPROVED'::"TaskStatus"
                AND t.assignee_id = %s::uuid
            RETURNING t.*
        )
        {self._task_select_base_sql(from_table='updated t')}
        LIMIT 1
        """
        return self._fetch_one(sql, [task_id, user_id])

    def complete_task(
        self,
        *,
        task_id: str,
        user_id: str,
        execution_report: dict[str, Any],
    ) -> dict[str, Any] | None:
        sql = f"""
        WITH updated AS (
            UPDATE tasks t
            SET
                status = 'COMPLETED'::"TaskStatus",
                completed_at = COALESCE(t.completed_at, NOW()),
                metadata = jsonb_set(
                    COALESCE(t.metadata, '{{}}'::jsonb),
                    '{{executionReport}}',
                    %s::jsonb,
                    TRUE
                ),
                updated_at = NOW()
            WHERE
                t.id = %s::uuid
                AND t.status = 'IN_PROGRESS'::"TaskStatus"
                AND t.assignee_id = %s::uuid
            RETURNING t.*
        )
        {self._task_select_base_sql(from_table='updated t')}
        LIMIT 1
        """
        return self._fetch_one(sql, [Jsonb(execution_report), task_id, user_id])

    def _task_select_base_sql(self, *, from_table: str = "tasks t") -> str:
        return f"""
        SELECT
            t.id::text AS id,
            t.title,
            t.description,
            t.status::text AS status,
            t.priority::text AS priority,
            t.source::text AS source,
            t.metadata,
            t.created_at,
            t.updated_at,
            t.approved_at,
            t.started_at,
            t.completed_at,
            t.due_at,
            t.created_by_id::text AS created_by_id,
            creator.email AS created_by_email,
            t.assignee_id::text AS assignee_id,
            assignee.email AS assignee_email,
            t.approved_by_id::text AS approved_by_id,
            approver.email AS approved_by_email
        FROM {from_table}
        LEFT JOIN users creator ON creator.id = t.created_by_id
        LEFT JOIN users assignee ON assignee.id = t.assignee_id
        LEFT JOIN users approver ON approver.id = t.approved_by_id
        """

    def _fetch_one(self, sql: str, params: list[Any]) -> dict[str, Any] | None:
        with psycopg.connect(self._database_url) as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()
            conn.commit()
        return row
