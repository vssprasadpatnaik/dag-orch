"""beacon-core service - the read-only brain + the `mf-sla v1` API (Consumer SPI).

Never writes to a platform. The only mutation it performs is to its own
operational store (predictions/audit). All write-back to platforms goes through
beacon-control.
"""

from __future__ import annotations

from typing import Any, Dict

import config
from common import httpkit
from . import store, pipeline


# ---- internal (ops) endpoints ----

def internal_ingest(query, body):
    return 200, pipeline.run_cycle()


def internal_repredict(query, body):
    fid = body["function_id"]
    run_id = body["run_id"]
    lane = body.get("lane", "normal")
    return 200, pipeline.repredict_function(fid, run_id, lane)


# ---- mf-sla v1 (consumer) endpoints ----

def list_functions(query, body):
    items = []
    for f in store.get_functions():
        fid = f["function_id"]
        run_id = store.latest_run_id(fid)
        snap = store.latest_snapshot(fid, run_id) if run_id else None
        if snap:
            items.append({
                "function_id": fid,
                "display_name": f["display_name"],
                "sla_deadline_local": f["sla_deadline_local"],
                "latest_run_id": run_id,
                "sla_status": snap["sla_status"],
                "predicted_finish_p50": snap["predicted_finish_p50"],
                "lane": snap.get("lane", "normal"),
                "fast_lane_eligible": snap.get("fast_lane_eligible", False),
            })
        else:
            items.append({"function_id": fid, "display_name": f["display_name"],
                          "sla_status": "Unknown", "latest_run_id": run_id})
    return 200, {"items": items}


def get_prediction(query, body):
    fid = query.get("function_id")
    run_id = query.get("run_id") or store.latest_run_id(fid)
    snap = store.latest_snapshot(fid, run_id)
    if not snap:
        return 404, {"error": "no prediction for {0}/{1}".format(fid, run_id)}
    return 200, snap


def at_risk(query, body):
    items = []
    for f in store.get_functions():
        fid = f["function_id"]
        run_id = store.latest_run_id(fid)
        snap = store.latest_snapshot(fid, run_id) if run_id else None
        if snap and snap["sla_status"] in ("AtRisk", "Breached"):
            items.append({
                "function_id": fid, "run_id": run_id,
                "sla_status": snap["sla_status"],
                "predicted_finish_p90": snap["predicted_finish_p90"],
                "sla_deadline": snap["sla_deadline"],
                "fast_lane_eligible": snap.get("fast_lane_eligible", False),
                "top_factors": snap.get("factors", [])[:3],
            })
    return 200, {"items": items}


def fast_lane_eligibility(query, body):
    fid = query.get("function_id")
    run_id = query.get("run_id") or store.latest_run_id(fid)
    snap = store.latest_snapshot(fid, run_id)
    if not snap:
        return 404, {"error": "no prediction"}
    return 200, {"function_id": fid, "run_id": run_id, **snap.get("fast_lane", {})}


def function_graph(query, body):
    fid = query.get("function_id")
    run_id = query.get("run_id") or store.latest_run_id(fid)
    snap = store.latest_snapshot(fid, run_id)
    if not snap:
        return 404, {"error": "no graph"}
    return 200, {"function_id": fid, "run_id": run_id, **snap.get("graph", {})}


ROUTES = {
    "POST /internal/ingest": internal_ingest,
    "POST /internal/repredict": internal_repredict,
    "GET /mf-sla/v1/functions": list_functions,
    "GET /mf-sla/v1/predictions": get_prediction,
    "GET /mf-sla/v1/recommendations/at-risk": at_risk,
    "GET /mf-sla/v1/fast-lane/eligibility": fast_lane_eligibility,
    "GET /mf-sla/v1/functions/graph": function_graph,
}


if __name__ == "__main__":
    store.init(fresh=True)
    httpkit.run_service("beacon-core", config.PORTS["beacon-core"], ROUTES)
