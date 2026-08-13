"""beacon-adapter-nebula  (out-of-process).

Implements the Producer SPI ``MetadataSource`` (functions, dependency edges,
holiday calendars) and ``SlaRegistrySource`` (deadline + criticality). In the
real world these come from Nebula RDS tables and stored procedures invoked by
the MWAA core scheduler; here they are static fixtures.
"""

from __future__ import annotations

from common import httpkit
from config import PORTS
from mf_sla_contract.ports import AdapterManifest, PortName

SOURCE = "nebula"


FUNCTIONS = [
    {"id": "daily_core", "name": "Daily Core", "owner": "mis-core@bank.com",
     "criticalityTier": 1, "nebulaId": "NEB-FN-001"},
    {"id": "cash_position", "name": "Cash Position", "owner": "treasury@bank.com",
     "criticalityTier": 2, "nebulaId": "NEB-FN-002"},
    {"id": "regulatory_x", "name": "Regulatory X", "owner": "reg-reporting@bank.com",
     "criticalityTier": 2, "nebulaId": "NEB-FN-003"},
]

# Dependency catalog (function -> ordered job edges). No DAG assumption.
DEPENDENCIES = {
    "daily_core": [
        {"toRun": "daily_core:core_calc", "type": "UPSTREAM", "satisfied": True,
         "detail": {"fromJob": "need_ingest", "toJob": "core_calc"}},
    ],
    "cash_position": [],
    "regulatory_x": [],
}

# SLA registry: deadline (local clock) + criticality.
SLA = {
    "daily_core": {"deadline": "08:00", "criticality": 1},
    "cash_position": {"deadline": "06:30", "criticality": 2},
    "regulatory_x": {"deadline": "09:00", "criticality": 2},
}

CALENDARS = [{"id": "us-bank-holidays", "blocks": ["2026-07-04"]}]


def list_functions(query, body):
    out = []
    for f in FUNCTIONS:
        out.append({
            "id": f["id"], "name": f["name"], "owner": f["owner"],
            "criticalityTier": f["criticalityTier"],
            "refs": [{"source": SOURCE, "nativeId": f["nebulaId"], "nativeType": "function"}],
        })
    return 200, {"items": out}


def get_dependencies(query, body):
    fid = query.get("function_id")
    return 200, {"items": DEPENDENCIES.get(fid, [])}


def get_calendars(query, body):
    return 200, {"items": CALENDARS}


def get_sla(query, body):
    fid = query.get("function_id")
    sla = SLA.get(fid)
    if not sla:
        return 404, {"error": "no SLA for {0}".format(fid)}
    return 200, sla


def manifest(query, body):
    m = AdapterManifest(
        adapterId="beacon-adapter-nebula",
        source=SOURCE,
        baseUrl="http://127.0.0.1:{0}".format(PORTS["adapter-nebula"]),
        ports=[PortName.METADATA_SOURCE, PortName.SLA_REGISTRY_SOURCE],
        mode="poll",
        writeCapable=False,
    )
    return 200, m.__dict__


ROUTES = {
    "GET /manifest": manifest,
    "GET /metadata/functions": list_functions,
    "GET /metadata/dependencies": get_dependencies,
    "GET /metadata/calendars": get_calendars,
    "GET /registry/sla": get_sla,
}


if __name__ == "__main__":
    httpkit.run_service("adapter-nebula", PORTS["adapter-nebula"], ROUTES)
