# BICP — Remaining Copilot Prompts

These are the final prompts to complete the BICP POC scaffolding via GitHub Copilot.
Hand-type each into Copilot Chat (Edits/agent mode) inside the VDI from the
corresponding empty repo clone.

**Build order:** These follow after repos 1–5 are complete:
1. ✅ `mf-sla-contract` — canonical contract
2. ✅ `beacon-core` — read-only intelligence service  
3. ✅ `beacon-adapter-mwaa` — orchestration adapter
4. ✅ `beacon-adapter-nebula` — metadata adapter
5. ✅ `beacon-adapter-databricks` — compute adapter (Fast Lane)
6. ⬜ `beacon-control` — **below**
7. ⬜ Ops Portal SLA module — **below**

---

## Repo #6: `beacon-control`

**The only writer.** Validates → executes via adapters → audits. This closes the
control loop (AtRisk → SRE approves Fast Lane → OnTrack).

```text
@workspace Create a service "beacon-control" (Python 3.9+, stdlib only: http.server,
json, uuid, threading). This is the ONLY service that writes to platforms. It
validates actions against beacon-core's eligibility, executes via adapter Control
ports, and maintains an immutable audit log. Depends on mf-sla-contract.

config.py: Read BICP_ADAPTERS from env (same as beacon-core). Also CORE_URL
defaulting to http://127.0.0.1:9200. BUSINESS_DATE="2026-06-30".

adapters.py: Same capability negotiation as beacon-core — on startup GET
{baseUrl}/manifest, build PortName -> [baseUrl] registry, expose sources_for(port).
For Control ports, also track which verbs each adapter supports.

Audit: Thread-safe in-memory list of audit records. Each record: {at, action,
function_id, run_id?, approved_by?, outcome, detail...}. Immutable once appended.

Endpoints (port 9210, env PORT):
- GET /health
- GET /audit -> {"items":[...audit records...]}
- GET /fast-lane/assignments -> {"items":[...active assignments...]}
- POST /fast-lane/assignments {function_id, run_id, approved_by}:
  1. GET CORE_URL/mf-sla/v1/fast-lane/eligibility?function_id=&run_id= to validate.
     If not eligible, audit REJECTED with reasons, return 409.
  2. Capture "before" status via GET CORE_URL/mf-sla/v1/predictions?function_id=&run_id=.
  3. POST to sources_for(ComputeControl) /compute/reassign {job_run_id, target}.
  4. POST CORE_URL/internal/repredict {function_id, run_id, lane:"fast"} to refresh.
  5. Capture "after" status.
  6. Store assignment record: {assignment_id, function_id, run_id, job_run_id,
     approved_by, from_tier, to_tier, estimated_minutes_saved, sla_status_before,
     sla_status_after, status:"ACTIVE"}.
  7. Audit EXECUTED with full detail.
  8. Return {ok:true, ...assignment details, sla_status_before, sla_status_after}.
- POST /fast-lane/release {assignment_id}:
  POST to ComputeControl /compute/release {assignmentId}, update assignment
  status to RELEASED, audit, return {ok, released, restoredTier}.
- POST /actions {verb, function_id, run_id, args}:
  POST to sources_for(OrchestrationControl) /control/orchestration {verb, run, args},
  audit outcome, return result.

Add pyproject.toml (dep mf-sla-contract), README explaining this is the only writer,
.gitignore, and tests:
- Test that POST /fast-lane/assignments with an ineligible function returns 409 and
  audits REJECTED (mock core returning fastLaneEligible:false).
- Test the full approve flow audits EXECUTED (mock adapters + core).
```

**Verify + push:**
```bash
pip install -e ../mf-sla-contract && pip install -e ".[dev]" && pytest
git add . && git commit -m "beacon-control: Fast Lane + Actions (only writer) with audit"
git push -u origin develop
```

---

## Repo #7: Ops Portal SLA Module

**Not a new repo** — this is a module inside your existing `ops-portal` repository.
It's the consumer of the `mf-sla v1` API, rendering Daily Guard with predicted
finish, SLA chips, and the "Move to Fast Lane" button.

```text
@workspace Add an "sla-command-center" module to this Ops Portal repo (Python 3.9+
or match existing stack). It consumes beacon-core's mf-sla v1 API and beacon-control
for actions. Gate behind feature flag "sla_command_center_mvp".

config: CORE_URL (default http://127.0.0.1:9200), CONTROL_URL (default
http://127.0.0.1:9210).

BFF endpoints (add to existing portal routing):
- GET /sla/daily-guard -> aggregates beacon-core GET /mf-sla/v1/functions and for
  each function GET /mf-sla/v1/predictions?function_id=&run_id=. Returns rows with:
  function_id, display_name, owner, state, predicted_finish_p50, predicted_finish_p90,
  sla_deadline, sla_deadline_local, sla_status, confidence, lane, fast_lane_eligible,
  compute_index, factors, fast_lane (full eligibility detail), run_id.
- GET /sla/audit -> proxies beacon-control GET /audit.
- POST /sla/fast-lane {function_id, run_id, approved_by} -> proxies to beacon-control
  POST /fast-lane/assignments.

UI (if portal is HTML/JS, else adapt to existing framework):
- Daily Guard table columns: Function, State, Predicted finish (p50, tooltip p90),
  SLA deadline, Status chip (OnTrack green, AtRisk amber, Breached red, Unknown gray),
  Lane indicator (normal vs "Fast Lane" highlighted), Action button.
- Action button: "Move to Fast Lane" enabled when fast_lane_eligible=true, disabled
  with tooltip showing reasons when not. On click POST /sla/fast-lane, refresh table.
- Factors shown as bullet list under each function row.
- Audit log panel at bottom showing beacon-control audit trail.
- Auto-refresh every 4 seconds.

Add tests for BFF aggregation logic. Feature flag off = unchanged portal behavior.
```

**Verify + push:**
```bash
pip install -e ".[dev]" && pytest
git add . && git commit -m "sla-command-center: Daily Guard SLA columns + Fast Lane action (behind flag)"
git push -u origin develop
```

---

## End-to-End Verification

After all repos are pushed, run all services locally to verify the full loop:

```bash
# Terminal 1-6: Start each service (from their respective clones)
cd beacon-adapter-mwaa && python -m app &      # :9101
cd beacon-adapter-nebula && python -m app &    # :9102
cd beacon-adapter-databricks && python -m app & # :9103
cd beacon-core && python -m app &              # :9200
cd beacon-control && python -m app &           # :9210
# Start portal per its usual method                # :9300

# Trigger ingest
curl -X POST http://127.0.0.1:9200/internal/ingest

# Check Daily Guard shows daily_core as AtRisk
curl http://127.0.0.1:9200/mf-sla/v1/functions

# Approve Fast Lane
curl -X POST http://127.0.0.1:9210/fast-lane/assignments \
  -H "Content-Type: application/json" \
  -d '{"function_id":"daily_core","run_id":"daily_core@2026-06-30","approved_by":"sre@bank.com"}'

# Verify recovery: daily_core should now be OnTrack on Fast Lane
curl http://127.0.0.1:9200/mf-sla/v1/functions

# Check audit
curl http://127.0.0.1:9210/audit
```

The expected story: `daily_core` starts **AtRisk** (p90 08:37 > SLA 08:00 due to late
file), is compute-bound (index 0.82) and critical (tier 1), so Fast Lane eligible.
SRE approves → Databricks adapter reassigns small→large → core re-predicts →
**OnTrack** (p90 ~07:51). Audit shows the full trail.
