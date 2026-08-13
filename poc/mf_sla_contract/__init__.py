"""mf-sla v1 — the canonical contract (the product surface).

The Beacon core depends ONLY on these types and on the ports declared in
``ports.py``. Every platform-specific system (MWAA, Nebula, Databricks, ...)
maps its native data into these types behind an out-of-process adapter.
"""

from .contract import (
    RunState,
    SlaStatus,
    ExternalRef,
    PctTime,
    DependencyEdge,
    CapacityTier,
    ComputeProfile,
    Function,
    Job,
    JobRun,
    FunctionRun,
    PredictionSnapshot,
    make_urn,
)
from .ports import AdapterManifest, PortName

__all__ = [
    "RunState",
    "SlaStatus",
    "ExternalRef",
    "PctTime",
    "DependencyEdge",
    "CapacityTier",
    "ComputeProfile",
    "Function",
    "Job",
    "JobRun",
    "FunctionRun",
    "PredictionSnapshot",
    "make_urn",
    "AdapterManifest",
    "PortName",
]
