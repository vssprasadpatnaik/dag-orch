# mf-sla-contract

The canonical **`mf-sla v1`** contract — the **product surface** of the BICP.

Every other Beacon repo depends on this package and **only** on this package for
the shared vocabulary: the canonical entities, the `RunState` / `SlaStatus` enums,
and the three SPI port families (Producer / Control / Consumer). Adapters translate
each platform into these types; the core reasons only in this language.

> This is the one repo to keep stable and versioned. Breaking changes here ripple
> to every service, so version it deliberately (`v1`, `v2`, ...).

## Contents

| Module | What it holds |
|--------|---------------|
| `mf_sla_contract/contract.py` | Entities (`Function`, `Job`, `JobRun`, `FunctionRun`, `DependencyEdge`, `ComputeProfile`, `CapacityTier`, `PredictionSnapshot`, `PctTime`, `ExternalRef`) + `RunState`, `SlaStatus`, `make_urn`, `to_dict` |
| `mf_sla_contract/ports.py` | `AdapterManifest`, `PortName`, control verbs — the SPI plug points |

## Install (used by other repos)

```bash
pip install -e .          # local dev
# or publish to the internal package index and pin: mf-sla-contract==1.0.0
```

## Use

```python
from mf_sla_contract import RunState, SlaStatus, PredictionSnapshot, make_urn
from mf_sla_contract import AdapterManifest, PortName
```

## Test

```bash
pip install -e ".[dev]"
pytest
```

## Production note

The POC models are plain dataclasses (zero dependencies). When you harden this,
the recommended upgrade is to convert them to **Pydantic v2** models (validation +
OpenAPI schema generation) without changing field names — that keeps the contract
identical while making it enforce itself at the service boundaries.
