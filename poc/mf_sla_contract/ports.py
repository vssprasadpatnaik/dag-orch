"""The three SPI families (architecture sec.4.2 / sec.6.3).

In a real deployment these are network SPIs (gRPC/REST + events) implemented by
out-of-process adapters. In this POC each adapter is a small HTTP service and
the port shapes below document the endpoints it must serve. Each adapter also
publishes an ``AdapterManifest`` so the core can compose by port and negotiate
capabilities.

    Producer SPI (read):   OrchestrationSource, MetadataSource, ComputeSource,
                           FileLandingSource, SlaRegistrySource
    Control SPI (write):   OrchestrationControl, ComputeControl
    Consumer SPI (out):    mf-sla v1 REST API, NotificationSink, event stream
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


class PortName:
    ORCHESTRATION_SOURCE = "OrchestrationSource"
    METADATA_SOURCE = "MetadataSource"
    COMPUTE_SOURCE = "ComputeSource"
    FILE_LANDING_SOURCE = "FileLandingSource"
    SLA_REGISTRY_SOURCE = "SlaRegistrySource"
    ORCHESTRATION_CONTROL = "OrchestrationControl"
    COMPUTE_CONTROL = "ComputeControl"


# Control verbs an OrchestrationControl adapter may advertise.
CONTROL_VERBS = (
    "trigger", "hold", "release", "rerun", "reschedule", "setPriority", "forceComplete",
)


@dataclass
class AdapterManifest:
    """Declared by every adapter; the core reads this to know what it can do."""
    adapterId: str
    source: str                       # SourceId, e.g. "mwaa", "nebula", "databricks"
    baseUrl: str
    ports: List[str] = field(default_factory=list)
    mode: str = "poll"                # poll | push
    controlVerbs: List[str] = field(default_factory=list)
    writeCapable: bool = False

    def implements(self, port: str) -> bool:
        return port in self.ports
