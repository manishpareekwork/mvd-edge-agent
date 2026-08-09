from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Optional


PENDING = "PENDING"
DELIVERED = "DELIVERED"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sanitize_error(error: Any, max_length: int = 500) -> str:
    message = str(error).replace("\n", " ").replace("\r", " ").strip()
    return message[:max_length]


@dataclass(frozen=True)
class QueuedEvent:
    id: int
    edge_event_id: str
    payload: dict[str, Any]
    created_at: str
    attempt_count: int
    last_attempt_at: Optional[str]
    delivered_at: Optional[str]
    status: str
    last_error: Optional[str]


class EventQueue:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.db_path))
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    def enqueue(self, payload: dict[str, Any]) -> None:
        edge_event_id = payload["edge_event_id"]
        payload_json = json.dumps(payload, sort_keys=True)

        with self._connection:
            self._connection.execute(
                """
                insert or ignore into event_queue (
                    edge_event_id,
                    payload_json,
                    created_at
                ) values (?, ?, ?)
                """,
                (edge_event_id, payload_json, utc_timestamp()),
            )

    def fetch_pending(self, limit: int) -> list[QueuedEvent]:
        rows = self._connection.execute(
            """
            select
                id,
                edge_event_id,
                payload_json,
                created_at,
                attempt_count,
                last_attempt_at,
                delivered_at,
                status,
                last_error
            from event_queue
            where status = ?
            order by created_at asc, id asc
            limit ?
            """,
            (PENDING, limit),
        ).fetchall()

        return [self._row_to_event(row) for row in rows]

    def mark_attempt(self, edge_event_id: str, error: Optional[Any] = None) -> None:
        with self._connection:
            self._connection.execute(
                """
                update event_queue
                set
                    attempt_count = attempt_count + 1,
                    last_attempt_at = ?,
                    last_error = ?
                where edge_event_id = ?
                """,
                (
                    utc_timestamp(),
                    sanitize_error(error) if error else None,
                    edge_event_id,
                ),
            )

    def update_payload(self, edge_event_id: str, payload: dict[str, Any]) -> None:
        with self._connection:
            self._connection.execute(
                """
                update event_queue
                set payload_json = ?
                where edge_event_id = ?
                """,
                (json.dumps(payload, sort_keys=True), edge_event_id),
            )

    def mark_delivered(self, edge_event_id: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                update event_queue
                set
                    status = ?,
                    delivered_at = ?,
                    last_error = null
                where edge_event_id = ?
                """,
                (DELIVERED, utc_timestamp(), edge_event_id),
            )

    def pending_count(self) -> int:
        row = self._connection.execute(
            """
            select count(*) as count
            from event_queue
            where status = ?
            """,
            (PENDING,),
        ).fetchone()

        return int(row["count"])

    def get(self, edge_event_id: str) -> Optional[QueuedEvent]:
        row = self._connection.execute(
            """
            select
                id,
                edge_event_id,
                payload_json,
                created_at,
                attempt_count,
                last_attempt_at,
                delivered_at,
                status,
                last_error
            from event_queue
            where edge_event_id = ?
            """,
            (edge_event_id,),
        ).fetchone()

        if not row:
            return None

        return self._row_to_event(row)

    def _initialize_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                create table if not exists event_queue (
                    id integer primary key autoincrement,
                    edge_event_id text not null unique,
                    payload_json text not null,
                    created_at text not null,
                    attempt_count integer not null default 0,
                    last_attempt_at text null,
                    delivered_at text null,
                    status text not null default 'PENDING',
                    last_error text null,
                    check (status in ('PENDING', 'DELIVERED'))
                )
                """
            )

    def _row_to_event(self, row: sqlite3.Row) -> QueuedEvent:
        return QueuedEvent(
            id=int(row["id"]),
            edge_event_id=row["edge_event_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            attempt_count=int(row["attempt_count"]),
            last_attempt_at=row["last_attempt_at"],
            delivered_at=row["delivered_at"],
            status=row["status"],
            last_error=row["last_error"],
        )
