"""Policy module - SLA status is set by Predict; this adds Fast Lane eligibility.

Gate (architecture sec.5.4):
    fast_lane_eligible =
        sla_status == AtRisk
        AND compute_index >= threshold
        AND estimated minutes_saved >= min
        AND criticality <= configured tier
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import config
from common import httpkit
from mf_sla_contract import SlaStatus

COMPUTE_INDEX_THRESHOLD = 0.60
MIN_MINUTES_SAVED = 10.0
MAX_CRITICALITY_TIER = 2          # 1 = most critical
DEFAULT_TARGET_TIER = "large"


def _core_job_run_id(jobs: List[Dict[str, Any]]) -> Optional[str]:
    for j in jobs:
        if j.get("role") == "core" and j["state"] in ("RUNNING", "QUEUED", "WAITING", "PENDING"):
            return j["id"]
    return None


def evaluate_fast_lane(func: Dict[str, Any], prediction: Dict[str, Any],
                       jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {"fastLaneEligible": False, "computeIndex": prediction.get("computeIndex"),
              "reasons": [], "target": None, "minutesSaved": None, "cost": None,
              "jobRunId": None}

    if prediction.get("slaStatus") != SlaStatus.AT_RISK:
        result["reasons"].append("not AtRisk")
        return result

    ci = prediction.get("computeIndex")
    if ci is None or ci < COMPUTE_INDEX_THRESHOLD:
        result["reasons"].append("compute_index {0} < {1} (upsize won't help)".format(ci, COMPUTE_INDEX_THRESHOLD))
        return result

    if func.get("criticality", 99) > MAX_CRITICALITY_TIER:
        result["reasons"].append("criticality below configured tier")
        return result

    job_run_id = _core_job_run_id(jobs)
    if not job_run_id:
        result["reasons"].append("no in-flight core job to reassign")
        return result
    result["jobRunId"] = job_run_id

    tiers = httpkit.get_json(config.DATABRICKS() + "/compute/capacity-tiers")["items"]
    target = next((t for t in tiers if t["label"] == DEFAULT_TARGET_TIER), tiers[-1])
    est = httpkit.post_json(config.DATABRICKS() + "/compute/estimate-speedup",
                            {"job_run_id": job_run_id, "target": target})
    result["target"] = target
    result["minutesSaved"] = est.get("minutesSaved")
    result["cost"] = est.get("cost")

    if (est.get("minutesSaved") or 0) < MIN_MINUTES_SAVED:
        result["reasons"].append("estimated saving < {0} min".format(MIN_MINUTES_SAVED))
        return result

    result["fastLaneEligible"] = True
    result["reasons"].append(
        "AtRisk + compute-bound ({0}) + saves ~{1} min on {2}".format(
            ci, est.get("minutesSaved"), target["label"]))
    return result
