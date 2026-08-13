"""beacon-adapter-databricks  (out-of-process).

Implements the Producer SPI ``ComputeSource`` (per-run compute profile: the
compute-bound index + an estimated duration at the current capacity tier) and
the Control SPI ``ComputeControl`` -- this is where Fast Lane physically lives.
The core only ever reasons about opaque, ordered *capacity tiers*, never about
"cluster SKUs".
"""

from __future__ import annotations

import uuid

from common import httpkit
from config import PORTS
from mf_sla_contract.ports import AdapterManifest, PortName

SOURCE = "databricks"

# Ordered, opaque capacity tiers (Databricks SKU is hidden behind the ordinal).
TIERS = [
    {"label": "small", "ordinal": 1},
    {"label": "medium", "ordinal": 2},
    {"label": "large", "ordinal": 3},
    {"label": "xl", "ordinal": 4},
]
TIER_BY_LABEL = {t["label"]: t for t in TIERS}

# A bigger tier helps in proportion to how compute-bound the job is.
SPEEDUP_PER_TIER_STEP = 0.30

# Per job-run compute profile. Key = "<functionId>:<jobId>".
_COMPUTE = {
    "daily_core:need_ingest": {"computeIndex": 0.40, "base": 20, "tier": "small"},
    "daily_core:core_calc":   {"computeIndex": 0.82, "base": 80, "tier": "small"},
    "cash_position:calc":     {"computeIndex": 0.30, "base": 20, "tier": "small"},
    "regulatory_x:calc":      {"computeIndex": 0.50, "base": 40, "tier": "medium"},
}

# Active Fast Lane assignments: assignmentId -> (key, previous_tier).
_ASSIGNMENTS = {}


def _key_from_run(job_run_id):
    # "daily_core:core_calc@2026-06-30" -> "daily_core:core_calc"
    return job_run_id.split("@", 1)[0]


def _duration_at_tier(base, compute_index, from_ordinal, to_ordinal):
    steps = max(0, to_ordinal - from_ordinal)
    saved_fraction = min(0.7, compute_index * steps * SPEEDUP_PER_TIER_STEP)
    return round(base * (1.0 - saved_fraction), 1), round(base * saved_fraction, 1)


def get_run_compute(query, body):
    key = _key_from_run(query.get("job_run_id", ""))
    prof = _COMPUTE.get(key)
    if not prof:
        return 404, {"error": "no compute profile for {0}".format(key)}
    tier = TIER_BY_LABEL[prof["tier"]]
    # durationEstimate reflects the *current* tier (small => base runtime).
    duration, _ = _duration_at_tier(prof["base"], prof["computeIndex"], 1, tier["ordinal"])
    return 200, {
        "backend": SOURCE,
        "capacityTier": tier,
        "computeIndex": prof["computeIndex"],
        "baseRuntimeMinutes": prof["base"],
        "durationEstimateMinutes": duration,
    }


def get_capacity_tiers(query, body):
    return 200, {"items": TIERS}


def estimate_speedup(query, body):
    key = _key_from_run(body.get("job_run_id", ""))
    prof = _COMPUTE.get(key)
    if not prof:
        return 404, {"error": "no compute profile for {0}".format(key)}
    target = body.get("target") or {}
    cur = TIER_BY_LABEL[prof["tier"]]
    _, saved = _duration_at_tier(prof["base"], prof["computeIndex"], cur["ordinal"], target["ordinal"])
    cost = round(saved * 0.8, 2)   # toy cost model
    return 200, {"minutesSaved": saved, "cost": cost,
                 "fromTier": cur, "toTier": target}


def reassign(query, body):
    """ComputeControl.reassign -> move this run to a higher capacity tier."""
    job_run_id = body.get("job_run_id", "")
    key = _key_from_run(job_run_id)
    prof = _COMPUTE.get(key)
    if not prof:
        return 404, {"error": "no compute profile for {0}".format(key)}
    target = body.get("target") or {}
    previous = prof["tier"]
    prof["tier"] = target["label"]            # mutate live -> Fast Lane engaged
    assignment_id = str(uuid.uuid4())
    _ASSIGNMENTS[assignment_id] = (key, previous)
    return 200, {"assignmentId": assignment_id, "fromTier": previous,
                 "toTier": target["label"], "jobRun": job_run_id}


def release(query, body):
    """Auto tear-down: restore the original tier when the run completes."""
    assignment_id = body.get("assignmentId", "")
    entry = _ASSIGNMENTS.pop(assignment_id, None)
    if not entry:
        return 404, {"error": "no such assignment"}
    key, previous = entry
    _COMPUTE[key]["tier"] = previous
    return 200, {"released": assignment_id, "restoredTier": previous}


def manifest(query, body):
    m = AdapterManifest(
        adapterId="beacon-adapter-databricks",
        source=SOURCE,
        baseUrl="http://127.0.0.1:{0}".format(PORTS["adapter-databricks"]),
        ports=[PortName.COMPUTE_SOURCE, PortName.COMPUTE_CONTROL],
        mode="poll",
        controlVerbs=["reassign", "release"],
        writeCapable=True,
    )
    return 200, m.__dict__


ROUTES = {
    "GET /manifest": manifest,
    "GET /compute/run": get_run_compute,
    "GET /compute/capacity-tiers": get_capacity_tiers,
    "POST /compute/estimate-speedup": estimate_speedup,
    "POST /compute/reassign": reassign,
    "POST /compute/release": release,
}


if __name__ == "__main__":
    httpkit.run_service("adapter-databricks", PORTS["adapter-databricks"], ROUTES)
