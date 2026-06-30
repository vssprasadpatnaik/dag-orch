# Batch Intelligence & Control Plane (BICP)

Documentation for the **Managed Flow SLA** / batch orchestration enhancement initiative.

## Contents

| Document | Description |
|----------|-------------|
| [docs/batch-orchestration-architecture.md](docs/batch-orchestration-architecture.md) | Pluggable hexagonal control plane; `mf-sla v1` contract + ports; Fast Lane; prediction |
| [docs/batch-orchestration-implementation-plan.md](docs/batch-orchestration-implementation-plan.md) | Epic design & implementation: Core/Control + adapter repos, schemas, APIs |
| [docs/batch-orchestration-book-of-work.md](docs/batch-orchestration-book-of-work.md) | Agile backlog: control-early Fast Lane, 2-week sprints, themes A–D |
| [docs/batch-orchestration-presentation-outline.md](docs/batch-orchestration-presentation-outline.md) | Slide outline + speaker notes |
| [docs/CONTEXT.md](docs/CONTEXT.md) | Session continuity — decisions, naming, stakeholders, open items |

## Quick context

- **Platform-agnostic, pluggable** control plane: core depends only on the canonical **`mf-sla v1`** contract + ports; platforms plug in as **out-of-process adapters**
- Backend = **Beacon Core** (read-only) + **Beacon Control** (only writer) + adapter layer
- ~2,000 batch jobs with SLAs; **first adapter bundle** = **Databricks** + **MWAA** (Airflow V1, V2 subset) + **Nebula RDS**; external brand **Managed Flow**
- **Fast Lane** (`ComputeControl`) = priority capacity reassignment when AtRisk + compute-bound; sequenced **early**
- **SLA Predictor** = XGBoost, core-only behind a rules-first interface

Start with `docs/CONTEXT.md` when resuming work in a new chat.
