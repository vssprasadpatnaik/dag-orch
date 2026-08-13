"""Graph module - builds the dependency graph and the cascade delta.

Cascade rule (architecture sec.5.2): if a head job starts at T+delta, downstream
critical-path jobs shift by delta unless parallel slack absorbs it.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import timeutil


def build_graph(jobs: List[Dict[str, Any]], deps: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = [{"id": j["jobId"], "role": j.get("role"), "state": j["state"]} for j in jobs]
    edges = []
    for d in deps:
        detail = d.get("detail", {})
        if "fromJob" in detail and "toJob" in detail:
            edges.append({"from": detail["fromJob"], "to": detail["toJob"], "type": d["type"]})
    return {"nodes": nodes, "edges": edges}


def cascade_delta_minutes(jobs: List[Dict[str, Any]]) -> float:
    """Largest observed start slippage among jobs (actualStart - scheduledStart)."""
    worst = 0.0
    for j in jobs:
        sched = j.get("scheduledStart")
        actual = j.get("actualStart")
        if sched and actual:
            delta = timeutil.minutes_between(sched, actual)
            if delta > worst:
                worst = delta
    return round(worst, 1)
