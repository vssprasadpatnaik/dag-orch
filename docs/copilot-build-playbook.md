# BICP — GitHub Copilot build playbook

**Purpose:** reproduce the BICP scaffolding *inside the company* using only GitHub
Copilot, repo by repo, mapped to the [Book of Work](./batch-orchestration-book-of-work.md)
and [Implementation Plan](./batch-orchestration-implementation-plan.md). No external
code is copied in — Copilot generates everything fresh from these prompts + your docs.

> The local `poc/` folder is a working reference implementation of the same design.
> Use it to *read the shape*; use this playbook to *recreate it* with Copilot.

---

## 0. How to drive Copilot like an agent (read once)

1. **Ground it per repo.** Put a `.github/copilot-instructions.md` in every repo
   (templates below). Copilot loads it automatically as standing context, so all
   devs get the same conventions.
2. **Give it the docs.** Copy `batch-orchestration-architecture.md` (at least §4 and
   §6) and `batch-orchestration-implementation-plan.md` into each repo's `/docs`, or
   keep them in a shared internal Confluence/repo Copilot can see. Then reference
   them in prompts with `@workspace` and `#file:docs/...`.
3. **Use the strongest mode you have.** Prefer **Copilot Edits / agent mode**
   (multi-file scaffolding). If only Chat is available, generate **one file per
   prompt** in the order given.
4. **Work in dependency order:** `mf-sla-contract` → `beacon-core` → adapters →
   `beacon-control` → Ops Portal module.
5. **Commit small, tagged to Jira.** One story per PR (E-01-S1, E-04-S2, …) so
   leadership sees the book of work advancing and devs stay engaged.
6. **Tech stack (house style):** Python 3.11, FastAPI, Pydantic v2, httpx,
   PostgreSQL + SQLAlchemy 2.x, Alembic (or Flyway), pytest, ruff. OpenAPI 3.1 at
   `/mf-sla/v1`.

---

## 1. Repo creation on Bitbucket (polyrepo)

Create these in the **existing Bitbucket Project**, grouped by naming prefix only
(see implementation plan §2.2.1). The Ops Portal module is **not** a new repo.

```
mf-sla-contract
beacon-core
beacon-control
beacon-adapter-mwaa
beacon-adapter-nebula
beacon-adapter-databricks
(existing) ops-portal  →  add an "sla-command-center" module
```

For each new repo, first commit the `.github/copilot-instructions.md` from this
playbook, then run the scaffolding prompts.

---

## 2. Shared `.github/copilot-instructions.md` (base — put in every repo)

```text
# Copilot instructions — BICP

You are helping build the Batch Intelligence & Control Plane (BICP), a
platform-agnostic, pluggable control plane for batch SLAs.

Architecture: hexagonal (ports & adapters). A platform-agnostic core depends ONLY
on the canonical `mf-sla v1` contract and on ports. Platforms (MWAA, Nebula RDS,
Databricks) live behind out-of-process adapters. Beacon Core is read-only; Beacon
Control is the only writer. See docs/architecture §4 and §6.

Conventions:
- Python 3.11, FastAPI, Pydantic v2, httpx, SQLAlchemy 2.x, Alembic, pytest, ruff.
- Public API is OpenAPI 3.1 served under /mf-sla/v1. Never put platform names
  (mwaa, nebula) in public routes.
- Depend on the `mf-sla-contract` package for all canonical types; do not redefine
  them locally.
- Adapters translate native platform states into the canonical RunState; the core
  must never see a native state.
- Every write goes through Beacon Control and is audited. The core never writes to
  a platform.
- Write unit tests for all pure logic (prediction rules, SLA clock, state mapping).
- Prefer small, typed, single-responsibility modules. No business logic in routers.
```

Add a one-line repo-specific note at the bottom of each copy (e.g. "This repo is
beacon-core: the read-only intelligence service.").

---

## 3. Prompt pack

Paste each prompt into Copilot Chat (with the repo open). Each is self-contained.

### 3.1 `mf-sla-contract` (build FIRST — Epic: contract / arch §6)

```text
@workspace Create a Python 3.11 package named `mf_sla_contract` (the canonical
"mf-sla v1" contract that the whole BICP depends on). Use Pydantic v2 models.

Define these entities (separating static definitions from runtime instances):
- RunState: enum PENDING, WAITING, QUEUED, RUNNING, SUCCEEDED, FAILED, TERMINATED,
  SKIPPED, HELD, UNKNOWN.
- SlaStatus: enum OnTrack, AtRisk, Breached, Unknown.
- ExternalRef(source, nativeId, nativeType?), and a make_urn(source,type,nativeId)
  helper producing "urn:mfsla:<source>:<type>:<nativeId>".
- PctTime(p50, p90).
- Function(id, name, owner?, criticalityTier?, refs: list[ExternalRef]).
- Job(id, functionId, name, role: "core"|"need"|"other", refs).
- FunctionRun(id, functionId, businessDate, state: RunState, slaDeadline?,
  slaStatus: SlaStatus, predictedStart?: PctTime, predictedFinish?: PctTime,
  actualFinish?).
- JobRun(id, jobId, functionRunId, state, name?, role?, scheduledStart?,
  actualStart?, actualFinish?, waitReasons: list[DependencyEdge], compute?:
  ComputeProfile).
- DependencyEdge(toRun, type: "TIME"|"FILE"|"UPSTREAM"|"RESOURCE"|"EXTERNAL",
  satisfied, satisfiedAt?, detail: dict).
- CapacityTier(label, ordinal). ComputeProfile(backend, capacityTier,
  computeIndex?, costRate?, durationActual?, baseRuntimeMinutes?, queueTime?).
- PredictionSnapshot(runId, functionId, producedAt, predictedStart, predictedFinish,
  slaDeadline, slaStatus, confidence: "Low"|"Medium"|"High", modelVersion,
  computeIndex?, fastLaneEligible: bool, factors: list[dict]).

Then define the three SPI port families as Python Protocols / ABCs:
- Producer SPI: OrchestrationSource, MetadataSource, ComputeSource,
  FileLandingSource, SlaRegistrySource.
- Control SPI: OrchestrationControl (supports/execute/simulate with ControlVerb =
  trigger|hold|release|rerun|reschedule|setPriority|forceComplete), ComputeControl
  (getCapacityTiers, estimateSpeedup, reassign, release).
- Consumer SPI: NotificationSink.
Add an AdapterManifest(adapterId, source, baseUrl, ports: list[str], mode:
"poll"|"push", controlVerbs: list[str], writeCapable: bool).

Package it with pyproject.toml as installable "mf-sla-contract" version 1.0.0, and
add pytest tests that round-trip each model to/from JSON. Add a README explaining
this is the product surface and is the only thing the core may depend on.
```

Follow-up prompt:

```text
@workspace Generate an OpenAPI 3.1 stub `openapi/mf-sla-v1.yaml` for the consumer
API with these endpoints (from architecture §6.5): GET /functions,
GET /functions/{id}/runs/{runId}, GET /functions/{id}/runs/{runId}/graph,
GET /predictions/{runId}, GET /recommendations/at-risk,
GET /fast-lane/eligibility/{runId}, POST /fast-lane/assignments, POST /actions.
Use the Pydantic models as the schema source of truth.
```

### 3.2 `beacon-core` — walking skeleton (Epics E-01, E-04, E-05, E-02)

```text
@workspace Scaffold a FastAPI service "beacon-core" (the read-only intelligence
brain). Depend on the `mf-sla-contract` package. Create this internal module
structure, each with unit tests:

- registry/        : loads FunctionDefinition (sla_deadline_local, timezone, owner,
                     criticality, mwaa_dag_ids, nebula_function_id) from a seed CSV;
                     a sla_clock.resolve_sla_deadline(function_id, logical_date) that
                     applies timezone + DST with zoneinfo. (Epic E-01)
- ingest/          : pulls FunctionRun + JobRun from an OrchestrationSource adapter
                     over HTTP (httpx), normalizes into mf-sla-contract types, and
                     upserts into Postgres. Map native Airflow states to canonical
                     RunState inside the adapter client. (Epic E-04)
- predict/         : rules_engine.py implementing predicted_finish = predicted_start
                     + runtime, p90 = +15% buffer; sla_policy.evaluate_status(p50,
                     p90, deadline) -> SlaStatus. modelVersion="rules-v1". (Epic E-05)
- store/           : SQLAlchemy 2.x models + Alembic migrations for function_definition,
                     job_run, prediction_snapshot (see implementation plan §2.4).
- api/             : FastAPI routers serving /mf-sla/v1/functions,
                     /mf-sla/v1/predictions/{runId}, /mf-sla/v1/recommendations/at-risk.

Add a docker-compose with Postgres for local dev, pytest + Testcontainers
integration tests, ruff config, and a Makefile (run, test, migrate). Keep routers
thin; all logic in modules. Do NOT write to any external platform from this service.
```

Then iterate one story at a time, e.g.:

```text
@workspace Implement registry/sla_clock.py with zoneinfo and golden tests for
spring-forward, fall-back, and a cross-midnight batch. (Story E-01-S3)
```

### 3.3 `beacon-adapter-mwaa` (Epic E-04)

```text
@workspace Scaffold an out-of-process adapter service "beacon-adapter-mwaa" that
implements the Producer port OrchestrationSource and the Control port
OrchestrationControl from `mf-sla-contract`. Expose HTTP endpoints:
GET /manifest (return an AdapterManifest), GET /orchestration/function-runs,
GET /orchestration/job-runs?function_id=, POST /control/orchestration {verb,run,args}.
Internally call the Airflow REST API (V1 primary; handle V2 differences) using
httpx; map Airflow task/dag states to canonical RunState (e.g. deferred->WAITING,
success->SUCCEEDED). Provide a fixtures-backed mode for local tests so it runs
without a live MWAA. Add pytest mapping tests covering >=95% of fields.
```

### 3.4 `beacon-adapter-nebula` and `beacon-adapter-databricks`

```text
@workspace Scaffold "beacon-adapter-nebula" implementing MetadataSource +
SlaRegistrySource: GET /metadata/functions, GET /metadata/dependencies?function_id=,
GET /metadata/calendars, GET /registry/sla?function_id=. Read from Nebula RDS via
SQLAlchemy (read-only replica) with documented stored-procedure interfaces for
later writes. Fixtures mode + tests. read/write = read-only in the manifest.
```

```text
@workspace Scaffold "beacon-adapter-databricks" implementing ComputeSource +
ComputeControl: GET /compute/run?job_run_id=, GET /compute/capacity-tiers,
POST /compute/estimate-speedup, POST /compute/reassign, POST /compute/release.
The core reasons only about opaque ordered CapacityTier (ordinal); map a tier to a
Databricks cluster SKU internally. estimate/reassign must reflect that a bigger
tier helps in proportion to the job's computeIndex. Fixtures mode + tests.
```

### 3.5 `beacon-control` (Epic E-12 — start folded behind a flag)

```text
@workspace Scaffold "beacon-control", the ONLY writer. Endpoints:
POST /fast-lane/assignments {function_id, run_id, approved_by},
POST /fast-lane/release {assignment_id}, POST /actions {verb,function_id,run_id,args},
GET /audit. For fast-lane: (1) re-validate eligibility by calling beacon-core's
/fast-lane/eligibility, (2) execute ComputeControl.reassign on the databricks
adapter, (3) ask beacon-core to re-predict, (4) write an immutable audit row
(approver, from/to tier, status before/after). Reject if not eligible. Implement an
idempotency key {function_id}:{run_id}:fastlane and a cost guardrail env var. Add
tests for the approve/execute/audit and the reject paths.
```

### 3.6 Ops Portal — `sla-command-center` module (Epics E-02, E-03)

```text
@workspace In the existing Ops Portal repo, add an "sla-command-center" module
behind a feature flag `sla_command_center_mvp`. Add a BFF endpoint
GET /sla/daily-guard?date= that aggregates beacon-core's /mf-sla/v1/functions and
/predictions into one response. Add Daily Guard columns: Predicted finish (p50 with
p90 tooltip) and an SLA status chip (OnTrack/AtRisk/Breached/Unknown), matching our
existing component/style conventions. Include a "Move to Fast Lane" action (disabled
with reason when ineligible) that POSTs to beacon-control. Storybook stories per chip
state. Do not change behavior when the flag is off.
```

---

## 4. First two weeks (to keep momentum + leadership visibility)

| Days | Deliverable | Demo to leadership |
|------|-------------|--------------------|
| 1–2  | `mf-sla-contract` v1 published; OpenAPI stub | "The product contract exists and is versioned" |
| 3–5  | `beacon-core` skeleton + registry + rules predictor (mock ingest) | Predicted finish for 1 seeded function via API |
| 6–8  | `beacon-adapter-mwaa` read + ingest wired to 1 real DAG | Live SLA status for 1 real function |
| 9–10 | Daily Guard column + chip behind flag (mock then live) | SLA chip visible in the portal |

Each row = one or two book-of-work stories. Open a PR per story referencing the
Jira ID so the backlog burns down visibly.

---

## 5. Guardrails when using Copilot

- Always have it depend on `mf-sla-contract`; reject any generated code that
  redefines canonical types locally.
- Reject any code in `beacon-core` that writes to MWAA/Nebula/Databricks — writes
  belong only in `beacon-control`.
- Keep native platform state mapping inside adapters, never in the core.
- Ask Copilot to generate tests in the same PR as the code (it will if prompted).
- Review for hardcoded platform names in public `/mf-sla/v1` routes.
```
