#!/usr/bin/env python3
"""Launch the whole BICP POC and run the end-to-end control loop.

    observe -> predict -> evaluate SLA -> recommend -> act (approved) -> show

Starts six out-of-process services (3 adapters + core + control + portal),
runs a narrated scenario against their HTTP APIs, then leaves the portal up so
you can click "Move to Fast Lane" yourself.

    python3 run_all.py            # full demo, then keep portal running
    python3 run_all.py --no-wait  # run demo and exit (don't keep serving)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import json

POC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, POC_DIR)

import config  # noqa: E402
from common import httpkit  # noqa: E402

SERVICES = [
    ("adapter-mwaa", "adapters.mwaa.app"),
    ("adapter-nebula", "adapters.nebula.app"),
    ("adapter-databricks", "adapters.databricks.app"),
    ("beacon-core", "beacon_core.app"),
    ("beacon-control", "beacon_control.app"),
    ("consumer-portal", "consumer.portal"),
]

# Light console styling (degrades to plain text if not a TTY).
def _c(code, s):
    return s if not sys.stdout.isatty() else "\033[{0}m{1}\033[0m".format(code, s)

BOLD = lambda s: _c("1", s)        # noqa: E731
DIM = lambda s: _c("2", s)         # noqa: E731
GREEN = lambda s: _c("32", s)      # noqa: E731
AMBER = lambda s: _c("33", s)      # noqa: E731
RED = lambda s: _c("31", s)        # noqa: E731
CYAN = lambda s: _c("36", s)       # noqa: E731


def _status_color(status):
    return {"OnTrack": GREEN, "AtRisk": AMBER, "Breached": RED}.get(status, DIM)(status)


def banner(text):
    print()
    print(BOLD(CYAN("=" * 72)))
    print(BOLD(CYAN("  " + text)))
    print(BOLD(CYAN("=" * 72)))


def wait_healthy(name, timeout=15.0):
    base = config.url(name)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(base + "/health", timeout=1.0).read()
            return True
        except Exception:
            time.sleep(0.2)
    return False


def hhmm(ts):
    if not ts:
        return "-"
    part = ts.split("T")
    return part[1][:5] if len(part) > 1 else ts


def print_board(title):
    print()
    print(BOLD(title))
    funcs = httpkit.get_json(config.CORE() + "/mf-sla/v1/functions")["items"]
    header = "  {0:<16}{1:<10}{2:<14}{3:<8}{4:<12}{5}".format(
        "FUNCTION", "STATE", "PRED p50/p90", "SLA", "STATUS", "LANE")
    print(DIM(header))
    for f in funcs:
        fid = f["function_id"]
        snap = httpkit.get_json(
            config.CORE() + "/mf-sla/v1/predictions?function_id={0}&run_id={1}".format(
                fid, f.get("latest_run_id")))
        pred = "{0}/{1}".format(hhmm(snap.get("predicted_finish_p50")),
                                hhmm(snap.get("predicted_finish_p90")))
        lane = AMBER("Fast Lane") if snap.get("lane") == "fast" else DIM("normal")
        print("  {0:<16}{1:<10}{2:<14}{3:<8}{4:<22}{5}".format(
            snap.get("display_name", fid), snap.get("state", "-"), pred,
            snap.get("sla_deadline_local", "-"), _status_color(snap.get("sla_status", "?")), lane))


def run_scenario():
    banner("STEP 1  -  Adapters register (capability negotiation via AdapterManifest)")
    for name in ("adapter-mwaa", "adapter-nebula", "adapter-databricks"):
        m = httpkit.get_json(config.url(name) + "/manifest")
        print("  {0:<22} ports={1} write={2}".format(
            m["source"], ",".join(m["ports"]), m["writeCapable"]))

    banner("STEP 2  -  Beacon Core: observe -> predict -> evaluate SLA  (read-only)")
    summary = httpkit.post_json(config.CORE() + "/internal/ingest", {})
    print("  ingested + predicted {0} functions from MWAA + Nebula + Databricks".format(
        summary["functions_processed"]))
    print_board("Daily Guard board (initial):")

    banner("STEP 3  -  Recommend: who is AtRisk and why")
    atrisk = httpkit.get_json(config.CORE() + "/mf-sla/v1/recommendations/at-risk")["items"]
    if not atrisk:
        print("  (nothing AtRisk)")
    for r in atrisk:
        print("  {0}  {1}  deadline {2}  eligible={3}".format(
            BOLD(r["function_id"]), AMBER(r["sla_status"]),
            hhmm(r["sla_deadline"]), r["fast_lane_eligible"]))
        for fac in r.get("top_factors", []):
            print(DIM("      - {0}: {1}".format(fac["type"], json.dumps(fac["detail"]))))

    if not atrisk:
        return None

    target = atrisk[0]
    fid, run_id = target["function_id"], target["run_id"]

    banner("STEP 4  -  Fast Lane eligibility gate (compute index + estimated saving)")
    elig = httpkit.get_json(
        config.CORE() + "/mf-sla/v1/fast-lane/eligibility?function_id={0}&run_id={1}".format(fid, run_id))
    print("  function        : {0}".format(fid))
    print("  compute_index   : {0}".format(elig.get("computeIndex")))
    print("  target tier     : {0}".format((elig.get("target") or {}).get("label")))
    print("  est. saving     : {0} min".format(elig.get("minutesSaved")))
    print("  eligible        : {0}".format(GREEN("YES") if elig.get("fastLaneEligible") else RED("NO")))
    print("  reason          : {0}".format("; ".join(elig.get("reasons", []))))

    banner("STEP 5  -  Act (SRE-approved): Beacon Control reassigns capacity")
    print(DIM("  POST beacon-control /fast-lane/assignments  approved_by=sre@bank.com"))
    res = httpkit.post_json(config.CONTROL() + "/fast-lane/assignments",
                            {"function_id": fid, "run_id": run_id, "approved_by": "sre@bank.com"})
    if res.get("ok"):
        print("  {0}  tier {1} -> {2}   SLA {3} -> {4}".format(
            GREEN("EXECUTED"), res["from_tier"], res["to_tier"],
            _status_color(res["sla_status_before"]), _status_color(res["sla_status_after"])))
    else:
        print(RED("  rejected: " + str(res)))

    banner("STEP 6  -  Show: board after recovery")
    print_board("Daily Guard board (after Fast Lane):")

    banner("STEP 7  -  Audit trail (Beacon Control is the only writer)")
    audit = httpkit.get_json(config.CONTROL() + "/audit")["items"]
    for a in audit:
        print("  {0}  {1}  {2}  -> {3}".format(
            a["at"], a["action"], a.get("function_id", ""), a.get("outcome", "")))
    return fid


def main():
    no_wait = "--no-wait" in sys.argv
    log_dir = os.path.join(POC_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    procs = []
    banner("Starting BICP POC services (out-of-process)")
    env = dict(os.environ)
    for name, module in SERVICES:
        logf = open(os.path.join(log_dir, name + ".log"), "w")
        p = subprocess.Popen([sys.executable, "-m", module], cwd=POC_DIR,
                             stdout=logf, stderr=subprocess.STDOUT, env=env)
        procs.append((name, p, logf))
        print("  launched {0:<20} (pid {1})".format(name, p.pid))

    try:
        ok = True
        for name, _, _ in procs:
            healthy = wait_healthy(name)
            print("  {0:<20} {1}".format(name, GREEN("ready") if healthy else RED("NOT READY")))
            ok = ok and healthy
        if not ok:
            print(RED("\nSome services failed to start; check poc/logs/*.log"))
            return

        run_scenario()

        url = config.PORTAL()
        banner("POC ready")
        print("  Open the SLA Command Center:  " + BOLD(CYAN(url)))
        print("  Try the " + BOLD("Move to Fast Lane") + " button on the AtRisk function.")
        print(DIM("  Service logs: poc/logs/*.log"))
        if no_wait:
            print(DIM("  --no-wait set; shutting down."))
            return
        print(DIM("  Press Ctrl+C to stop all services."))
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for name, p, logf in procs:
            p.terminate()
            try:
                logf.close()
            except Exception:
                pass
        for name, p, _ in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()


if __name__ == "__main__":
    main()
