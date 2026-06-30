# Session context — continue from here

**Last updated:** 2026-06-23 (architecture v3.0: pluggable hexagonal control plane, control-early)  
**Repo purpose:** Standalone docs for BICP / batch orchestration (split from unrelated `synergine-accountant` project).

---

## What this initiative is

Build a **Batch Intelligence & Control Plane (BICP)** for ~**2,000 batch jobs** with SLAs. It is a **platform-agnostic, pluggable product**: the core depends only on the canonical **`mf-sla v1`** contract and on **ports**, and platforms plug in as **out-of-process adapters**. **Databricks** (compute) + **MWAA** (orchestration) + **Nebula RDS** (orchestration metadata) are **our stack and the first adapter bundle**, not assumptions. Externally position as **Managed Flow SLA capability** — reusable by other teams (e.g. Control-M/AutoSys + Snowflake/EMR) with their own adapters.

**One control loop:** observe → predict → evaluate SLA → recommend → act (approved) → show. Both **visibility and control** are committed; **Fast Lane is sequenced early**.

**Core capabilities:**

1. **Predict** start/finish with explainable confidence (rules first, XGBoost second; core-only)
2. **Surface SLA** in any portal (today: Radar, Daily Guard) — replace Excel → Teams
3. **Fast Lane** (`ComputeControl` port) — reassign to a higher **capacity tier** when AtRisk and **compute-bound**
4. **Controlled reschedule** (`OrchestrationControl` port) — SRE approval, audit, reversible, human-in-the-loop

---

## Platform stack (confirmed)

| Layer | Technology | Role |
|-------|------------|------|
| **Compute backend** | **Databricks** | Job execution, clusters, runtime metrics, queue |
| **Orchestration** | **MWAA** | Airflow hosting; **core scheduler** is the batch entry/trigger point |
| **Orchestration metadata** | **Nebula (RDS)** | Proprietary DB—most orchestration definitions, calendars, dependencies; **stored procedures** supply job info when scheduler runs |
| **Airflow version** | **V1** (majority) | Most batches; **V2** only for a subset of batch types |

**Trigger flow:** MWAA core scheduler → Nebula RDS stored procedure(s) → job information → MWAA tasks → Databricks.

Beacon ingests from **all three**; write-back may use **MWAA REST** (run control) and **Nebula stored procedures** (business orchestration changes).

---

### Naming

| Term | Meaning |
|------|---------|
| **BICP** | Batch Intelligence & Control Plane (program) |
| **Fast Lane** | HOV-lane analogy: eligible critical jobs get priority capacity to meet SLA |
| **Managed Flow** | External orchestration brand for cross-team adoption |
| **MWAA** | Amazon Managed Workflows for Apache Airflow—orchestration engine |
| **Nebula** | Proprietary **RDS**—orchestration metadata & rules (not “just an Airflow wrapper”) |
| **Databricks** | Backend compute where jobs run |
| **SLA Command Center** | Ops Portal UI module family |
| **Beacon** | Backend service family: `beacon-core` (read), `beacon-control` (write), `beacon-adapter-*`; early-warning/guidance layer—see [architecture §1.3](./batch-orchestration-architecture.md#13-naming--why-beacon) |
| **SLA Predictor** | XGBoost finish-time model (POC → prod) |

### Areas / responsibilities

| Area | Role |
|--------|------|
| **SLA Predictor / ML** | XGBoost POC, prediction features, model tuning |
| **Ops Portal team** | Radar owner; ~4 peer solutions; portal integration |
| **SRE ops contact** | Manual Excel/Teams process, rainy days, Daily Guard day-to-day |
| **Compute profiling** | Compute index / compute-bound classification |
| **Manager** | Claude Code instruction workflow offer for implementation |

### Batch anatomy

```
Function (Daily Guard parent, e.g. Daily Core)
  └── Subfunction
        └── Core job
              └── Need job(s)
```

Dependencies exist in **Nebula RDS** (and partially MWAA); Radar shows status colors but not full dependency graph visually yet.

### Prediction scope

- **Normal day (primary):** upstream file late, cluster queue, dependency cascade (train-delay model)
- **Rainy day (exception):** validation failure, upstream data fix, rare code deploy → **SRE manual**, not full auto-remediation
- **Compute index** gates Fast Lane — upsizing only helps if compute-bound
- Exclude on-prem historical runtimes from DBX prediction training

### UI / portal

- Extend **Radar** (D3JS) and **Daily Guard** — owned by the Ops Portal team
- Add: predicted finish, SLA chip, lane (normal vs Fast Lane), criticality, Move to Fast Lane
- Audience: MIS, BCA, business teams (earnings, cash position) — stop posting “job done by X” in Teams
- Metaphor: trains on lanes; show which lane job is on

### Claude Code workflow (for implementation)

Manager offered: author **self-contained Claude instructions** on a feature branch; someone with Claude Code license runs it and pushes to Bitbucket with Jira ticket assigned to committer. Use for large greenfield slices (e.g. Fast Lane portal module).

### Peer solutions

The Ops Portal team knows **~4 related tools** from other teams. P0-6 in book of work: document integrate / extend / out of scope per tool. BICP should be comprehensive, not duplicate silos.

---

## Documents in this repo

| File | Version | Notes |
|------|---------|-------|
| `batch-orchestration-architecture.md` | 3.0 | Pluggable hexagonal control plane; `mf-sla v1` contract + ports (§4, §6) |
| `batch-orchestration-implementation-plan.md` | 2.0 | Epic design; Core/Control + out-of-process adapter repos |
| `batch-orchestration-book-of-work.md` | 4.0 | Agile backlog: control-early Fast Lane, themes A–D |
| `batch-orchestration-presentation-outline.md` | 1.x | Slide deck outline; links to docs above |

---

## Delivery approach (summary)

**Agile / MVP-first** — see [book of work v3.0](./batch-orchestration-book-of-work.md).

| Milestone | Sprints (illustrative) | Outcome |
|-----------|------------------------|---------|
| **MVP** | 0–2 | Daily Guard predicted finish + SLA chip (~10 functions) **+ non-prod Fast Lane POC**; control spike started Sprint 0 |
| **R2** | 3–4 | Live ingest, explanations, Teams digest; **Fast Lane eligibility (recommend-only)** |
| **R3** | 5–6 | **Fast Lane execute (approved, audited, reversible)**; Radar overlays; ~50 functions; retire Excel |
| **R4** | 7–9 | XGBoost shadow; reschedule actions; expand |
| **R5** | 10+ | Rollout waves, model ops, hardening, 2nd-adapter readiness |

Full backlog, sprint plan, and themes: [batch-orchestration-book-of-work.md](./batch-orchestration-book-of-work.md)

---

## Service model (3 logical services + adapters)

| Service | Role | Internal modules / notes |
|---------|------|--------------------------|
| **Beacon Core** | Read-only brain | Ingest, Graph, Registry, Predict (rules+XGBoost), Policy, `mf-sla v1` API, Notify |
| **Beacon Control** | Only writer | Fast Lane (`ComputeControl`), Actions (`OrchestrationControl`); validate/simulate/execute/audit |
| **Adapter layer** | Pluggable, out-of-process | Reference: `beacon-adapter-mwaa`, `-nebula`, `-databricks`; declare capabilities via `AdapterManifest` |
| Contract | Product surface | `mf-sla-contract` — canonical entities + port SPIs (architecture §6) |
| External API base | — | `/mf-sla/v1` |

---

## Open items (carry forward)

- [ ] MWAA read/write API inventory (V1 primary; V2 subset batch types)
- [ ] Nebula RDS read model + stored procedure catalog (scheduler job lookup)
- [ ] Nebula RDS write procedures for Fast Lane / reschedule (change management)
- [ ] Airflow V2 batch-type inventory
- [ ] Authoritative SLA registry location today
- [ ] Radar/Daily Guard extension points with the Ops Portal team
- [ ] XGBoost POC notebook + feature list from the SLA Predictor POC
- [ ] Compute index v1 definition with compute profiling
- [ ] Peer solution decision log (Ops Portal team, P0-6)
- [ ] Pilot cohort selection (~30–50 functions)
- [ ] Sample Claude instruction template from manager
- [ ] Update presentation outline slides for Fast Lane / Managed Flow / Radar (still partly v1 wording)
- [ ] Optional: recreate architecture canvas in new repo (was in Cursor canvases under synergine-accountant project)

---

## What was NOT part of this repo

- No application code yet — docs only
- `synergine-accountant` is a separate project (restaurant/accounting); batch docs were removed from there when this repo was created

---

## Suggested next steps in new window

1. Read architecture + book of work; adjust dates/owners to your Jira project
2. Schedule Ops Portal team (portal + peers) and SLA Predictor POC sessions per P0
3. Draft pilot function list for P0-1
4. Update presentation outline for stakeholder review
5. Optionally add `CONTRIBUTING.md`, Confluence export, or Claude instruction templates folder

---

## Chat / agent handoff prompt

When starting a new Cursor chat in this repo, you can paste:

> This repo documents BICP (Batch Intelligence & Control Plane) for Managed Flow SLA on ~2000 batches. **Architecture:** pluggable hexagonal control plane — platform-agnostic core (`mf-sla v1` contract + ports), with MWAA + Nebula RDS + Databricks as the first **out-of-process adapter bundle**. Backend = Beacon Core (read) + Beacon Control (write) + adapters. Control (Fast Lane) is sequenced early. Read `docs/CONTEXT.md` first, then architecture and book of work.
