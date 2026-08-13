"""beacon-adapter-mwaa  (out-of-process).

Implements the Producer SPI ``OrchestrationSource`` (function/job run state from
"Airflow V1") and the Control SPI ``OrchestrationControl`` (trigger/hold/...).
Native Airflow states are mapped into the canonical RunState here; the core
never sees an Airflow state.
"""

from __future__ import annotations

from common import httpkit
from config import PORTS, BUSINESS_DATE
from mf_sla_contract import RunState
from mf_sla_contract.ports import AdapterManifest, PortName

SOURCE = "mwaa"
D = BUSINESS_DATE


def _ts(hhmm):
    return None if hhmm is None else "{0}T{1}:00".format(D, hhmm)


# Native Airflow -> canonical RunState (the core never sees the left column).
AIRFLOW_STATE_MAP = {
    "success": RunState.SUCCEEDED,
    "running": RunState.RUNNING,
    "deferred": RunState.WAITING,   # sensor waiting on a file/upstream
    "queued": RunState.QUEUED,
    "failed": RunState.FAILED,
    "scheduled": RunState.PENDING,
}


# --- Fixture: today's Airflow DAG runs / task instances for the pilot ---
# (functionId is the shared logical key across all adapters.)
FUNCTION_RUNS = [
    {"functionId": "daily_core", "dagId": "dag_daily_core", "airflowVersion": "v1",
     "native_state": "running", "scheduledStart": "06:00"},
    {"functionId": "cash_position", "dagId": "dag_cash_position", "airflowVersion": "v1",
     "native_state": "success", "scheduledStart": "05:30"},
    {"functionId": "regulatory_x", "dagId": "dag_regulatory_x", "airflowVersion": "v2",
     "native_state": "running", "scheduledStart": "07:45"},
]

JOB_RUNS = [
    # daily_core: late upstream file -> need job started 45m late -> core job now running
    {"functionId": "daily_core", "jobId": "need_ingest", "role": "need",
     "native_state": "success", "scheduledStart": "06:00",
     "actualStart": "06:45", "actualFinish": "07:05",
     "waitReasons": [{"toRun": "daily_core:need_ingest", "type": "FILE", "satisfied": True,
                      "satisfiedAt": _ts("06:43"),
                      "detail": {"filePattern": "landing/eod/daily.csv", "expectedBy": "06:00"}}]},
    {"functionId": "daily_core", "jobId": "core_calc", "role": "core",
     "native_state": "running", "scheduledStart": "06:30",
     "actualStart": "07:05", "actualFinish": None,
     "waitReasons": [{"toRun": "daily_core:core_calc", "type": "UPSTREAM", "satisfied": True,
                      "satisfiedAt": _ts("07:05"),
                      "detail": {"upstreamRunId": "daily_core:need_ingest", "requiredState": "SUCCEEDED"}}]},

    # cash_position: finished comfortably before SLA
    {"functionId": "cash_position", "jobId": "calc", "role": "core",
     "native_state": "success", "scheduledStart": "05:30",
     "actualStart": "05:50", "actualFinish": "06:10", "waitReasons": []},

    # regulatory_x: running, plenty of slack
    {"functionId": "regulatory_x", "jobId": "calc", "role": "core",
     "native_state": "running", "scheduledStart": "07:45",
     "actualStart": "08:00", "actualFinish": None, "waitReasons": []},
]

# Mutable control overrides applied by OrchestrationControl (audit-only for POC).
_CONTROL_OVERRIDES = {}


def list_function_runs(query, body):
    out = []
    for fr in FUNCTION_RUNS:
        fid = fr["functionId"]
        out.append({
            "id": "{0}@{1}".format(fid, D),
            "functionId": fid,
            "businessDate": D,
            "state": AIRFLOW_STATE_MAP.get(fr["native_state"], RunState.UNKNOWN),
            "ref": {"source": SOURCE, "nativeId": fr["dagId"], "nativeType": "dag"},
            "airflowVersion": fr["airflowVersion"],
            "scheduledStart": _ts(fr["scheduledStart"]),
        })
    return 200, {"items": out}


def list_job_runs(query, body):
    fid_filter = query.get("function_id")
    out = []
    for jr in JOB_RUNS:
        fid = jr["functionId"]
        if fid_filter and fid != fid_filter:
            continue
        out.append({
            "id": "{0}:{1}@{2}".format(fid, jr["jobId"], D),
            "jobId": jr["jobId"],
            "functionRunId": "{0}@{1}".format(fid, D),
            "functionId": fid,
            "name": jr["jobId"],
            "role": jr["role"],
            "state": AIRFLOW_STATE_MAP.get(jr["native_state"], RunState.UNKNOWN),
            "scheduledStart": _ts(jr["scheduledStart"]),
            "actualStart": _ts(jr["actualStart"]),
            "actualFinish": _ts(jr["actualFinish"]),
            "waitReasons": jr["waitReasons"],
        })
    return 200, {"items": out}


def control(query, body):
    """OrchestrationControl.execute(verb, run, args)."""
    verb = body.get("verb")
    run = body.get("run")
    if verb not in ("trigger", "hold", "release", "rerun", "reschedule", "setPriority"):
        return 400, {"ok": False, "error": "unsupported verb: {0}".format(verb)}
    _CONTROL_OVERRIDES.setdefault(run, []).append(verb)
    return 200, {"ok": True, "verb": verb, "run": run,
                 "result": "accepted by MWAA (Airflow REST stub)",
                 "history": _CONTROL_OVERRIDES[run]}


def manifest(query, body):
    m = AdapterManifest(
        adapterId="beacon-adapter-mwaa",
        source=SOURCE,
        baseUrl="http://127.0.0.1:{0}".format(PORTS["adapter-mwaa"]),
        ports=[PortName.ORCHESTRATION_SOURCE, PortName.ORCHESTRATION_CONTROL],
        mode="poll",
        controlVerbs=["trigger", "hold", "release", "rerun", "reschedule", "setPriority"],
        writeCapable=True,
    )
    return 200, m.__dict__


ROUTES = {
    "GET /manifest": manifest,
    "GET /orchestration/function-runs": list_function_runs,
    "GET /orchestration/job-runs": list_job_runs,
    "POST /control/orchestration": control,
}


if __name__ == "__main__":
    httpkit.run_service("adapter-mwaa", PORTS["adapter-mwaa"], ROUTES)
