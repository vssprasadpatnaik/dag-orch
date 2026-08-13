"""Operational store (the canonical model + prediction history).

The plan calls for PostgreSQL; the POC uses SQLite so it runs with zero setup.
Schema mirrors implementation-plan sec.2.4 in spirit.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

_DB_PATH = os.path.join(os.path.dirname(__file__), "beacon_store.sqlite")
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def init(fresh: bool = True) -> None:
    global _conn
    if fresh and os.path.exists(_DB_PATH):
        os.remove(_DB_PATH)
    _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS function_definition (
            function_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            owner TEXT,
            sla_deadline_local TEXT NOT NULL,
            criticality INTEGER NOT NULL DEFAULT 2
        );
        CREATE TABLE IF NOT EXISTS function_run (
            function_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            business_date TEXT NOT NULL,
            state TEXT NOT NULL,
            PRIMARY KEY (function_id, run_id)
        );
        CREATE TABLE IF NOT EXISTS job_run (
            function_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (function_id, run_id, job_id)
        );
        CREATE TABLE IF NOT EXISTS prediction_snapshot (
            function_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            produced_at TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (function_id, run_id, produced_at)
        );
        """
    )
    _conn.commit()


def upsert_function(fid: str, name: str, owner: str, deadline_local: str, criticality: int) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO function_definition VALUES (?,?,?,?,?) "
            "ON CONFLICT(function_id) DO UPDATE SET display_name=excluded.display_name, "
            "owner=excluded.owner, sla_deadline_local=excluded.sla_deadline_local, "
            "criticality=excluded.criticality",
            (fid, name, owner, deadline_local, criticality),
        )
        _conn.commit()


def upsert_function_run(fid: str, run_id: str, business_date: str, state: str) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO function_run VALUES (?,?,?,?) "
            "ON CONFLICT(function_id, run_id) DO UPDATE SET state=excluded.state",
            (fid, run_id, business_date, state),
        )
        _conn.commit()


def upsert_job_run(fid: str, run_id: str, job_id: str, payload: Dict[str, Any]) -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO job_run VALUES (?,?,?,?) "
            "ON CONFLICT(function_id, run_id, job_id) DO UPDATE SET payload=excluded.payload",
            (fid, run_id, job_id, json.dumps(payload)),
        )
        _conn.commit()


def save_snapshot(fid: str, run_id: str, produced_at: str, payload: Dict[str, Any]) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO prediction_snapshot VALUES (?,?,?,?)",
            (fid, run_id, produced_at, json.dumps(payload)),
        )
        _conn.commit()


def get_functions() -> List[Dict[str, Any]]:
    with _lock:
        rows = _conn.execute("SELECT * FROM function_definition ORDER BY function_id").fetchall()
    return [dict(r) for r in rows]


def get_function(fid: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _conn.execute(
            "SELECT * FROM function_definition WHERE function_id=?", (fid,)
        ).fetchone()
    return dict(row) if row else None


def get_job_runs(fid: str, run_id: str) -> List[Dict[str, Any]]:
    with _lock:
        rows = _conn.execute(
            "SELECT payload FROM job_run WHERE function_id=? AND run_id=?", (fid, run_id)
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def latest_run_id(fid: str) -> Optional[str]:
    with _lock:
        row = _conn.execute(
            "SELECT run_id FROM function_run WHERE function_id=? ORDER BY business_date DESC LIMIT 1",
            (fid,),
        ).fetchone()
    return row["run_id"] if row else None


def latest_snapshot(fid: str, run_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _conn.execute(
            "SELECT payload FROM prediction_snapshot WHERE function_id=? AND run_id=? "
            "ORDER BY produced_at DESC LIMIT 1",
            (fid, run_id),
        ).fetchone()
    return json.loads(row["payload"]) if row else None
