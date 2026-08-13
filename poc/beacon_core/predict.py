"""Predict module - rules engine v1 (modelVersion 'rules-v1').

    predicted_start  = actualStart or scheduledStart (max with upstream)
    predicted_finish = predicted_start + runtime ; p90 = + 15% buffer
    sla_status       = compare(p90, deadline)

XGBoost would slot in behind this same interface (selected by modelVersion).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mf_sla_contract import SlaStatus
from . import timeutil
from .graph import cascade_delta_minutes

MODEL_VERSION = "rules-v1"
P90_BUFFER = 1.15
LATE_START_THRESHOLD_MIN = 5.0
DEFAULT_RUNTIME_MIN = 30.0


def _job_runtime(job: Dict[str, Any]) -> float:
    compute = job.get("compute") or {}
    return float(
        compute.get("durationEstimateMinutes")
        or compute.get("baseRuntimeMinutes")
        or DEFAULT_RUNTIME_MIN
    )


def _job_finish(job: Dict[str, Any]):
    """Return (p50_finish, p90_finish, start_used) ISO strings."""
    if job["state"] == "SUCCEEDED" and job.get("actualFinish"):
        f = job["actualFinish"]
        return f, f, job.get("actualStart") or f
    start = job.get("actualStart") or job.get("scheduledStart")
    if not start:
        return None, None, None
    runtime = _job_runtime(job)
    return (
        timeutil.add_minutes(start, runtime),
        timeutil.add_minutes(start, runtime * P90_BUFFER),
        start,
    )


def _build_factors(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    factors: List[Dict[str, Any]] = []
    for j in jobs:
        for wr in j.get("waitReasons", []):
            if wr["type"] == "FILE":
                d = wr.get("detail", {})
                factors.append({"type": "file_delay", "detail": {
                    "file": d.get("filePattern"), "expectedBy": d.get("expectedBy"),
                    "arrivedAt": timeutil.hhmm(wr.get("satisfiedAt")), "job": j["jobId"]}})
        sched, actual = j.get("scheduledStart"), j.get("actualStart")
        if sched and actual:
            late = timeutil.minutes_between(sched, actual)
            if late > LATE_START_THRESHOLD_MIN:
                factors.append({"type": "late_start", "detail": {
                    "job": j["jobId"], "minutes": round(late, 1),
                    "scheduled": timeutil.hhmm(sched), "actual": timeutil.hhmm(actual)}})
        if j["state"] == "RUNNING":
            compute = j.get("compute") or {}
            factors.append({"type": "historical_runtime_p90", "detail": {
                "job": j["jobId"], "minutes": round(_job_runtime(j) * P90_BUFFER, 1),
                "capacityTier": (compute.get("capacityTier") or {}).get("label")}})
    cascade = cascade_delta_minutes(jobs)
    if cascade > LATE_START_THRESHOLD_MIN:
        factors.append({"type": "cascade_delta_minutes", "detail": {"value": cascade}})
    return factors


def predict_function(func: Dict[str, Any], jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    deadline = timeutil.deadline_for(func["slaDeadlineLocal"])

    p50_finishes, p90_finishes, starts = [], [], []
    compute_index: Optional[float] = None
    for j in jobs:
        f50, f90, start = _job_finish(j)
        if f50:
            p50_finishes.append(f50)
            p90_finishes.append(f90)
        if start:
            starts.append(start)
        compute = j.get("compute") or {}
        ci = compute.get("computeIndex")
        if j.get("role") == "core" and ci is not None:
            compute_index = ci

    if not p90_finishes:
        return {
            "functionId": func["id"], "slaDeadline": deadline,
            "slaStatus": SlaStatus.UNKNOWN, "confidence": "Low",
            "modelVersion": MODEL_VERSION, "factors": [],
            "computeIndex": compute_index,
        }

    predicted_finish_p50 = max(p50_finishes)
    predicted_finish_p90 = max(p90_finishes)
    predicted_start = min(starts) if starts else None

    all_done = all(j["state"] == "SUCCEEDED" for j in jobs)
    if all_done:
        status = SlaStatus.BREACHED if predicted_finish_p90 > deadline else SlaStatus.ON_TRACK
        confidence = "High"
    else:
        status = SlaStatus.AT_RISK if predicted_finish_p90 > deadline else SlaStatus.ON_TRACK
        confidence = "Medium"

    return {
        "functionId": func["id"],
        "predictedStart": {"p50": predicted_start, "p90": predicted_start},
        "predictedFinish": {"p50": predicted_finish_p50, "p90": predicted_finish_p90},
        "slaDeadline": deadline,
        "slaStatus": status,
        "confidence": confidence,
        "modelVersion": MODEL_VERSION,
        "computeIndex": compute_index,
        "factors": _build_factors(jobs),
    }
