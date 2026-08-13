"""Ingest module - pulls canonical signals from adapters via the Producer SPI.

The core talks only to adapter HTTP endpoints (the network SPI). It never knows
that behind them sit Airflow, an RDS, or Databricks.
"""

from __future__ import annotations

from typing import Any, Dict, List

import config
from common import httpkit


def fetch_functions() -> List[Dict[str, Any]]:
    """MetadataSource.listFunctions + SlaRegistrySource.getSla (Nebula)."""
    funcs = httpkit.get_json(config.NEBULA() + "/metadata/functions")["items"]
    for f in funcs:
        sla = httpkit.get_json(config.NEBULA() + "/registry/sla?function_id=" + f["id"])
        f["slaDeadlineLocal"] = sla["deadline"]
        f["criticality"] = sla["criticality"]
    return funcs


def fetch_function_runs() -> List[Dict[str, Any]]:
    """OrchestrationSource.listFunctionRuns (MWAA)."""
    return httpkit.get_json(config.MWAA() + "/orchestration/function-runs")["items"]


def fetch_job_runs(function_id: str) -> List[Dict[str, Any]]:
    """OrchestrationSource.listJobRuns (MWAA), enriched with ComputeSource (Databricks)."""
    jobs = httpkit.get_json(
        config.MWAA() + "/orchestration/job-runs?function_id=" + function_id
    )["items"]
    for j in jobs:
        try:
            j["compute"] = httpkit.get_json(
                config.DATABRICKS() + "/compute/run?job_run_id=" + j["id"]
            )
        except Exception:
            j["compute"] = None
    return jobs


def fetch_dependencies(function_id: str) -> List[Dict[str, Any]]:
    """MetadataSource.getDependencies (Nebula)."""
    return httpkit.get_json(
        config.NEBULA() + "/metadata/dependencies?function_id=" + function_id
    )["items"]
