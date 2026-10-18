"""Local SQLite order journal.

The broker does not expose a client-order-id, so a timeout leaves genuine
ambiguity: the order may or may not have been accepted.  The journal records
the intent *before* submission and the outcome afterwards, giving the operator
an audit trail and a safe place to reconcile duplicate-looking orders.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import DuplicateOrderError, ThsError
from .models import OrderIntent


class OrderJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _db(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    client_order_id TEXT PRIMARY KEY,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    account_id      TEXT NOT NULL,
                    symbol          TEXT NOT NULL,
                    side            TEXT NOT NULL,
                    quantity        INTEGER NOT NULL,
                    price           REAL NOT NULL,
                    amount_value    REAL NOT NULL,
                    status          TEXT NOT NULL,
                    broker_ref      TEXT,
                    message         TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_orders_created "
                "ON orders(created_at DESC)"
            )
            conn.commit()

    def begin(self, intent: OrderIntent) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            with self._db() as conn:
                conn.execute(
                    """
                    INSERT INTO orders
                    (client_order_id, created_at, updated_at, account_id,
                     symbol, side, quantity, price, amount_value, status,
                     broker_ref, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'intent', NULL, NULL)
                    """,
                    (intent.client_order_id, intent.created_at, now,
                     intent.account_id, intent.symbol, intent.side,
                     intent.quantity, intent.price, intent.amount_value),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateOrderError(
                f"client_order_id already exists: {intent.client_order_id}"
            ) from exc
        except sqlite3.Error as exc:
            raise ThsError(f"cannot write order journal: {exc}") from exc

    def mark(self, client_order_id: str, status: str, *,
             broker_ref: str | None = None, message: str | None = None) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            with self._db() as conn:
                cur = conn.execute(
                    """
                    UPDATE orders
                       SET status = ?, updated_at = ?,
                           broker_ref = COALESCE(?, broker_ref),
                           message = COALESCE(?, message)
                     WHERE client_order_id = ?
                    """,
                    (status, now, broker_ref, message, client_order_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    raise ThsError(
                        f"unknown client_order_id in journal: {client_order_id}")
        except sqlite3.Error as exc:
            raise ThsError(f"cannot update order journal: {exc}") from exc

    def get(self, client_order_id: str) -> dict[str, Any] | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE client_order_id = ?",
                (client_order_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def counts(self) -> dict[str, int]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"
            ).fetchall()
        return {str(r["status"]): int(r["n"]) for r in rows}