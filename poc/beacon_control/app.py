"""beacon-control service - the ONLY writer.

Holds the Control SPI ports. Validates -> (simulate) -> execute via a write
adapter -> audit. Two capabilities in this POC:

  * Fast Lane  -> ComputeControl.reassign/release (Databricks adapter)
  * Actions    -> OrchestrationControl.execute      (MWAA adapter)

It never predicts; it asks beacon-core to re-evaluate after a write so the loop
closes (observe -> ... -> act -> show).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List

import config
from common import httpkit

_lock = threading.Lock()
_AUDIT: List[Dict[str, Any]] = []
_ASSIGNMENTS: Dict[str, Dict[str, Any]] = {}


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _audit(entry: Dict[str, Any]) -> None:
    entry["at"] = _now()
    with _lock:
        _AUDIT.append(entry)


def fast_lane_assign(query, body):
    """POST /fast-lane/assignments  {function_id, run_id, approved_by}."""
    fid = body["function_id"]
    run_id = body["run_id"]
    approver = body.get("approved_by", "unknown-sre")

    # 1. Validate against the core's eligibility decision (no self-granted writes).
    elig = httpkit.get_json(
        config.CORE() + "/mf-sla/v1/fast-lane/eligibility?function_id={0}&run_id={1}".format(fid, run_id))
    if not elig.get("fastLaneEligible"):
        _audit({"action": "fast_lane", "function_id": fid, "approved_by": approver,
                "outcome": "REJECTED", "reason": elig.get("reasons")})
        return 409, {"ok": False, "error": "not eligible", "detail": elig}

    job_run_id = elig["jobRunId"]
    target = elig["target"]

    # capture status before
    before = httpkit.get_json(
        config.CORE() + "/mf-sla/v1/predictions?function_id={0}&run_id={1}".format(fid, run_id))

    # 2. Execute the write via the Databricks ComputeControl adapter.
    reassign = httpkit.post_json(config.DATABRICKS() + "/compute/reassign",
                                 {"job_run_id": job_run_id, "target": target})
    assignment_id = reassign["assignmentId"]

    # 3. Ask the core to re-evaluate now that compute reflects the higher tier.
    after = httpkit.post_json(config.CORE() + "/internal/repredict",
                              {"function_id": fid, "run_id": run_id, "lane": "fast"})

    record = {
        "assignment_id": assignment_id, "function_id": fid, "run_id": run_id,
        "job_run_id": job_run_id, "approved_by": approver,
        "from_tier": reassign["fromTier"], "to_tier": reassign["toTier"],
        "estimated_minutes_saved": elig.get("minutesSaved"),
        "sla_status_before": before.get("sla_status"),
        "sla_status_after": after.get("sla_status"),
        "status": "ACTIVE",
    }
    with _lock:
        _ASSIGNMENTS[assignment_id] = record
    _audit({"action": "fast_lane", "outcome": "EXECUTED", **record})
    return 200, {"ok": True, **record}


def fast_lane_release(query, body):
    """POST /fast-lane/release {assignment_id} - auto tear-down after the run."""
    assignment_id = body["assignment_id"]
    rec = _ASSIGNMENTS.get(assignment_id)
    if not rec:
        return 404, {"ok": False, "error": "no such assignment"}
    httpkit.post_json(config.DATABRICKS() + "/compute/release", {"assignmentId": assignment_id})
    rec["status"] = "RELEASED"
    _audit({"action": "fast_lane_release", "assignment_id": assignment_id,
            "function_id": rec["function_id"], "outcome": "EXECUTED"})
    return 200, {"ok": True, "released": assignment_id}


def action(query, body):
    """POST /actions {verb, function_id, run_id, args} - OrchestrationControl."""
    verb = body["verb"]
    fid = body["function_id"]
    run = body.get("run_id")
    args = body.get("args", {})
    res = httpkit.post_json(config.MWAA() + "/control/orchestration",
                            {"verb": verb, "run": run, "args": args})
    _audit({"action": "orchestration", "verb": verb, "function_id": fid,
            "run_id": run, "outcome": "EXECUTED" if res.get("ok") else "FAILED",
            "adapter_result": res})
    return (200 if res.get("ok") else 400), {"ok": res.get("ok"), "result": res}


def get_audit(query, body):
    with _lock:
        return 200, {"items": list(_AUDIT)}


def get_assignments(query, body):
    with _lock:
        return 200, {"items": list(_ASSIGNMENTS.values())}


ROUTES = {
    "POST /fast-lane/assignments": fast_lane_assign,
    "POST /fast-lane/release": fast_lane_release,
    "POST /actions": action,
    "GET /audit": get_audit,
    "GET /fast-lane/assignments": get_assignments,
}


if __name__ == "__main__":
    httpkit.run_service("beacon-control", config.PORTS["beacon-control"], ROUTES)
