# BICP end-to-end POC

A tiny, runnable miniature of the **Batch Intelligence & Control Plane**. Every
architectural component from the [architecture doc](../docs/batch-orchestration-architecture.md)
is present and does one simple, real job, so you can watch the whole **control
loop** come together:

> observe → predict → evaluate SLA → recommend → act (approved) → show

**Zero dependencies.** Pure Python standard library (`http.server`, `urllib`,
`sqlite3`, `json`, `dataclasses`). No `pip install`, no Docker, no network.
(Production stack stays FastAPI + Postgres + Delta per the implementation plan;
the POC swaps those for stdlib + SQLite so it runs anywhere instantly.)

## Run it

```bash
cd poc
python3 run_all.py
```

This launches **six out-of-process services**, runs a narrated scenario in your
terminal, then leaves the portal up at **http://127.0.0.1:9300**. Press Ctrl+C to
stop. Use `python3 run_all.py --no-wait` to run the scenario and exit.

## What's inside (maps 1:1 to the architecture)

| Folder | Service | Role | Ports it implements |
|--------|---------|------|---------------------|
| `mf_sla_contract/` | *(library)* | The product surface: canonical `mf-sla v1` types + the three SPI families + `AdapterManifest` | — |
| `adapters/mwaa/` | `adapter-mwaa` :9101 | Out-of-process read/write adapter ("Airflow V1") | `OrchestrationSource`, `OrchestrationControl` |
| `adapters/nebula/` | `adapter-nebula` :9102 | Metadata & SLA registry ("Nebula RDS") | `MetadataSource`, `SlaRegistrySource` |
| `adapters/databricks/` | `adapter-databricks` :9103 | Compute profile + Fast Lane reassignment | `ComputeSource`, `ComputeControl` |
| `beacon_core/` | `beacon-core` :9200 | **Read-only brain**: Ingest → Graph → Registry → Predict (rules) → Policy → store → `mf-sla v1` API | Consumer SPI |
| `beacon_control/` | `beacon-control` :9210 | **The only writer**: Fast Lane + Actions, validate→execute→audit | Control SPI client |
| `consumer/` | `consumer-portal` :9300 | SLA Command Center (Daily Guard view) + its BFF | API consumer |

Each adapter is a separate OS process the core only reaches over HTTP — it never
knows Airflow/RDS/Databricks sit behind them. Native states (e.g. Airflow
`deferred`) are mapped to the canonical `RunState` inside the adapter.

## The scenario

Three pilot functions are served from fixtures:

- **Daily Core** (SLA 08:00) — its upstream file `daily.csv` landed ~45 min late,
  cascading into the core job. Predicted **p90 = 08:37 → AtRisk**. It is
  compute-bound (`compute_index 0.82`) and critical (tier 1) → **Fast Lane eligible**.
- **Cash Position** (SLA 06:30) — already finished at 06:10 → **OnTrack**.
- **Regulatory X** (SLA 09:00) — running with slack → **OnTrack**.

`run_all.py` then walks the loop: ingest+predict → list AtRisk with explanations
→ check the Fast Lane gate → an SRE approves via `beacon-control`, which calls
`ComputeControl.reassign` on the Databricks adapter (small → large tier) → core
re-predicts → **Daily Core recovers to OnTrack on the Fast Lane**, with the write
recorded in the audit log. You can reproduce the last step yourself with the
**Move to Fast Lane** button in the portal.

## Try the API directly

```bash
curl -s -XPOST localhost:9200/internal/ingest
curl -s localhost:9200/mf-sla/v1/functions
curl -s localhost:9200/mf-sla/v1/recommendations/at-risk
curl -s "localhost:9200/mf-sla/v1/fast-lane/eligibility?function_id=daily_core&run_id=daily_core@2026-06-30"
curl -s localhost:9210/audit
```

## Where the POC simplifies (honest tech debt)

- Times are naive ISO strings for one fixed business date (no timezone/DST math).
- Rules predictor only: `finish = start + runtime`, `p90 = +15%`. XGBoost would
  slot behind the same interface via `modelVersion`.
- Fixtures instead of live MWAA/Nebula/Databricks; SQLite instead of Postgres;
  in-memory audit instead of an immutable store.
- Ingest is triggered on demand (`/internal/ingest`) rather than polled on a timer.
