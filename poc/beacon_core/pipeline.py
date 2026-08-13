"""Pipeline - the read-only control-loop half: ingest -> graph -> predict -> policy -> store."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from . import ingest, graph as graph_mod, predict, policy, store


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _snapshot_payload(func, frun, jobs, pred, fast, graph) -> Dict[str, Any]:
    pf = pred.get("predictedFinish") or {}
    ps = pred.get("predictedStart") or {}
    return {
        "function_id": func["id"],
        "run_id": frun["id"],
        "display_name": func["name"],
        "owner": func.get("owner"),
        "business_date": frun["businessDate"],
        "state": frun["state"],
        "predicted_start": ps.get("p50"),
        "predicted_finish_p50": pf.get("p50"),
        "predicted_finish_p90": pf.get("p90"),
        "sla_deadline": pred["slaDeadline"],
        "sla_deadline_local": func["slaDeadlineLocal"],
        "sla_status": pred["slaStatus"],
        "confidence": pred["confidence"],
        "compute_index": pred.get("computeIndex"),
        "criticality": func.get("criticality"),
        "fast_lane_eligible": fast["fastLaneEligible"],
        "fast_lane": fast,
        "model_version": pred["modelVersion"],
        "factors": pred.get("factors", []),
        "graph": graph,
        "jobs": [{"job_id": j["jobId"], "role": j.get("role"), "state": j["state"],
                  "actual_start": j.get("actualStart"), "actual_finish": j.get("actualFinish")}
                 for j in jobs],
        "lane": "fast" if frun.get("_lane") == "fast" else "normal",
        "produced_at": _now_iso(),
    }


def run_cycle() -> Dict[str, Any]:
    """One full pass over the pilot cohort. Returns a short summary."""
    funcs = ingest.fetch_functions()
    fruns = {fr["functionId"]: fr for fr in ingest.fetch_function_runs()}

    summary = []
    for func in funcs:
        fid = func["id"]
        store.upsert_function(fid, func["name"], func.get("owner", ""),
                              func["slaDeadlineLocal"], func.get("criticality", 2))
        frun = fruns.get(fid)
        if not frun:
            continue
        store.upsert_function_run(fid, frun["id"], frun["businessDate"], frun["state"])

        jobs = ingest.fetch_job_runs(fid)
        for j in jobs:
            store.upsert_job_run(fid, frun["id"], j["jobId"], j)
        deps = ingest.fetch_dependencies(fid)

        graph = graph_mod.build_graph(jobs, deps)
        pred = predict.predict_function(func, jobs)
        fast = policy.evaluate_fast_lane(func, pred, jobs)

        payload = _snapshot_payload(func, frun, jobs, pred, fast, graph)
        store.save_snapshot(fid, frun["id"], payload["produced_at"], payload)
        summary.append({"function_id": fid, "sla_status": pred["slaStatus"],
                        "fast_lane_eligible": fast["fastLaneEligible"]})

    return {"functions_processed": len(summary), "results": summary}


def repredict_function(function_id: str, run_id: str, lane: str = "normal") -> Dict[str, Any]:
    """Re-run predict/policy for a single function (used after a Fast Lane reassign).

    Re-pulls compute from the Databricks adapter, which now reflects the higher
    capacity tier, so the new prediction shows the recovery.
    """
    func_row = store.get_function(function_id)
    funcs = {f["id"]: f for f in ingest.fetch_functions()}
    func = funcs.get(function_id)
    if not func:
        raise ValueError("unknown function {0}".format(function_id))

    fruns = {fr["functionId"]: fr for fr in ingest.fetch_function_runs()}
    frun = fruns.get(function_id)
    frun["_lane"] = lane

    jobs = ingest.fetch_job_runs(function_id)
    for j in jobs:
        store.upsert_job_run(function_id, run_id, j["jobId"], j)
    deps = ingest.fetch_dependencies(function_id)

    graph = graph_mod.build_graph(jobs, deps)
    pred = predict.predict_function(func, jobs)
    fast = policy.evaluate_fast_lane(func, pred, jobs)
    payload = _snapshot_payload(func, frun, jobs, pred, fast, graph)
    store.save_snapshot(function_id, run_id, payload["produced_at"], payload)
    return payload
