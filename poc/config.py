"""Central port map + URLs for the POC services (single source of truth)."""

import os

HOST = "127.0.0.1"

PORTS = {
    "adapter-mwaa": 9101,
    "adapter-nebula": 9102,
    "adapter-databricks": 9103,
    "beacon-core": 9200,
    "beacon-control": 9210,
    "consumer-portal": 9300,
}


def url(service: str) -> str:
    # Allow env override so services can be relocated if a port is busy.
    env = os.environ.get("BICP_URL_" + service.replace("-", "_").upper())
    if env:
        return env
    return "http://{0}:{1}".format(HOST, PORTS[service])


# Convenience accessors used across services.
MWAA = lambda: url("adapter-mwaa")          # noqa: E731
NEBULA = lambda: url("adapter-nebula")      # noqa: E731
DATABRICKS = lambda: url("adapter-databricks")  # noqa: E731
CORE = lambda: url("beacon-core")           # noqa: E731
CONTROL = lambda: url("beacon-control")     # noqa: E731
PORTAL = lambda: url("consumer-portal")     # noqa: E731

# Fixed business date for a deterministic demo.
BUSINESS_DATE = "2026-06-30"
