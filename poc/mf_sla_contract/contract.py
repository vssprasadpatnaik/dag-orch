"""Canonical `mf-sla v1` entities (architecture sec.6).

Plain dataclasses so the whole contract is dependency-free and JSON-friendly.
Definitions (static) are separated from runs (instances) so that an Airflow
DAG/Task and a Control-M job both map in without privileging either.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---- Canonical enums (the core NEVER sees a native platform state) ----

class RunState:
    PENDING = "PENDING"        # known, not yet startable (future schedule)
    WAITING = "WAITING"        # startable but blocked - see waitReasons
    QUEUED = "QUEUED"          # submitted, awaiting compute
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"
    SKIPPED = "SKIPPED"
    HELD = "HELD"
    UNKNOWN = "UNKNOWN"


class SlaStatus:
    ON_TRACK = "OnTrack"
    AT_RISK = "AtRisk"
    BREACHED = "Breached"
    UNKNOWN = "Unknown"


def make_urn(source: str, ntype: str, native_id: str) -> str:
    """urn:mfsla:<source>:<type>:<nativeId>"""
    return "urn:mfsla:{0}:{1}:{2}".format(source, ntype, native_id)


# ---- Small value objects ----

@dataclass
class ExternalRef:
    source: str
    nativeId: str
    nativeType: Optional[str] = None


@dataclass
class PctTime:
    p50: Optional[str] = None
    p90: Optional[str] = None


@dataclass
class DependencyEdge:
    """No DAG assumption - a typed edge between runs/inputs."""
    toRun: str
    type: str                      # TIME | FILE | UPSTREAM | RESOURCE | EXTERNAL
    satisfied: bool
    satisfiedAt: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapacityTier:
    """Opaque to the core, but ordered (ordinal). Databricks SKU / Snowflake
    warehouse / EMR instance count all map onto this."""
    label: str
    ordinal: int


@dataclass
class ComputeProfile:
    backend: str
    capacityTier: CapacityTier
    computeIndex: Optional[float] = None   # 0..1 compute-bound score
    costRate: Optional[float] = None
    durationActual: Optional[float] = None
    baseRuntimeMinutes: Optional[float] = None
    queueTime: Optional[float] = None


# ---- Definitions ----

@dataclass
class Function:
    id: str
    name: str
    owner: Optional[str] = None
    criticalityTier: Optional[int] = None
    refs: List[ExternalRef] = field(default_factory=list)


@dataclass
class Job:
    id: str
    functionId: str
    name: str
    role: str                      # core | need | other
    refs: List[ExternalRef] = field(default_factory=list)


# ---- Runs ----

@dataclass
class JobRun:
    id: str
    jobId: str
    functionRunId: str
    state: str
    name: Optional[str] = None
    role: Optional[str] = None
    scheduledStart: Optional[str] = None
    actualStart: Optional[str] = None
    actualFinish: Optional[str] = None
    waitReasons: List[DependencyEdge] = field(default_factory=list)
    compute: Optional[ComputeProfile] = None


@dataclass
class FunctionRun:
    id: str
    functionId: str
    businessDate: str
    state: str
    slaDeadline: Optional[str] = None
    slaStatus: str = SlaStatus.UNKNOWN
    predictedStart: Optional[PctTime] = None
    predictedFinish: Optional[PctTime] = None
    actualFinish: Optional[str] = None


@dataclass
class PredictionSnapshot:
    """Append-only; modelVersion makes the predictor swappable."""
    runId: str
    functionId: str
    producedAt: str
    predictedStart: PctTime
    predictedFinish: PctTime
    slaDeadline: str
    slaStatus: str
    confidence: str                # Low | Medium | High
    modelVersion: str              # rules-v1 | xgb-2026.06
    computeIndex: Optional[float] = None
    fastLaneEligible: bool = False
    factors: List[Dict[str, Any]] = field(default_factory=list)


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to plain dicts for JSON transport."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    return obj
