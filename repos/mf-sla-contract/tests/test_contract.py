from mf_sla_contract import (
    RunState, SlaStatus, PctTime, PredictionSnapshot, make_urn, to_dict,
    AdapterManifest, PortName,
)
from mf_sla_contract.contract import to_dict as _td  # noqa: F401


def test_urn_format():
    assert make_urn("mwaa", "dag", "daily_core") == "urn:mfsla:mwaa:dag:daily_core"


def test_enums():
    assert RunState.SUCCEEDED == "SUCCEEDED"
    assert SlaStatus.AT_RISK == "AtRisk"


def test_prediction_snapshot_roundtrip():
    snap = PredictionSnapshot(
        runId="daily_core@2026-06-30",
        functionId="daily_core",
        producedAt="2026-06-30T07:00:00",
        predictedStart=PctTime(p50="2026-06-30T07:05:00", p90="2026-06-30T07:05:00"),
        predictedFinish=PctTime(p50="2026-06-30T08:25:00", p90="2026-06-30T08:37:00"),
        slaDeadline="2026-06-30T08:00:00",
        slaStatus=SlaStatus.AT_RISK,
        confidence="Medium",
        modelVersion="rules-v1",
        computeIndex=0.82,
        fastLaneEligible=True,
    )
    d = to_dict(snap)
    assert d["slaStatus"] == "AtRisk"
    assert d["predictedFinish"]["p90"] == "2026-06-30T08:37:00"
    assert d["fastLaneEligible"] is True


def test_manifest_implements():
    m = AdapterManifest(
        adapterId="beacon-adapter-mwaa", source="mwaa", baseUrl="http://x",
        ports=[PortName.ORCHESTRATION_SOURCE, PortName.ORCHESTRATION_CONTROL],
        writeCapable=True,
    )
    assert m.implements(PortName.ORCHESTRATION_SOURCE)
    assert not m.implements(PortName.COMPUTE_CONTROL)
