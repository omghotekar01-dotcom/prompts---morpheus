from __future__ import annotations

import hashlib
import json
from dataclasses import replace
import pytest

from app.search_quality_ablation_result_raw_sample_pairing import PAIRING_KEYS, verify_ablation_raw_sample_pairing
from app.search_quality_ablation_result_raw_sample_pairwise_descriptives import (
    EVIDENCE_STATE, verify_ablation_raw_sample_pairwise_descriptives,
)
from app.search_quality_ablation_result_raw_sample_semantics import RAW_SAMPLE_SCHEMA, verify_ablation_raw_sample_semantics
from app.search_quality_ablation_result_raw_samples import AblationResultRawSampleBinding


def _record(sample: str, condition: str, rep: int, value: int) -> dict[str, object]:
    return {"schema": RAW_SAMPLE_SCHEMA, "sample_id": sample, "condition_id": condition,
            "workload_id": "w", "repetition_index": rep, "metric": "latency_ns", "value": value,
            "measurement_source": "native-benchmark", "protocol_id": "ablation-v1", "machine_fingerprint": "m"}


def _jsonl(*rows: dict[str, object]) -> bytes:
    return b"".join(json.dumps(r, sort_keys=True, separators=(",", ":")).encode()+b"\n" for r in rows)

RAW = {"a.jsonl": _jsonl(_record("s1","reference",0,100), _record("s2","ablated",0,108)),
       "b.jsonl": _jsonl(_record("s3","reference",1,110), _record("s4","ablated",1,114))}


def _artifact(mean_delta: object = "6", reference: object = "reference", comparisons: object = None) -> bytes:
    inventory=[{"artifact_id":k,"sha256":hashlib.sha256(v).hexdigest()} for k,v in sorted(RAW.items())]
    comps = comparisons if comparisons is not None else [{"condition_id":"ablated","pair_count":2,"mean_delta":mean_delta}]
    return json.dumps({"schema":"morpheus.ablation-result/v1","raw_sample_evidence":{"inventory_complete":True,"artifacts":inventory,
      "semantics":{"schema":RAW_SAMPLE_SCHEMA,"measurement_source":"native-benchmark","protocol_id":"ablation-v1","machine_fingerprint":"m","metric":"latency_ns","record_count":4,"condition_ids":["reference","ablated"]},
      "pairing":{"pairing_keys":list(PAIRING_KEYS),"complete_pair_count":2},
      "pairwise_descriptives":{"reference_condition_id":reference,"comparisons":comps}},"automatic_control_allowed":False},sort_keys=True,separators=(",",":")).encode()


def _inputs(result: bytes):
    inventory=[{"artifact_id":k,"sha256":hashlib.sha256(v).hexdigest()} for k,v in sorted(RAW.items())]
    inv_sha=hashlib.sha256(json.dumps(inventory,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    binding=AblationResultRawSampleBinding(result_artifact_verification_sha256="11"*32,result_artifact_sha256=hashlib.sha256(result).hexdigest(),raw_sample_inventory_sha256=inv_sha,raw_sample_artifact_count=2,raw_sample_binding_sha256="22"*32,raw_sample_bytes_bound=True)
    semantics=verify_ablation_raw_sample_semantics(binding,result_artifact=result,raw_sample_artifacts=RAW)
    pairing=verify_ablation_raw_sample_pairing(semantics,binding,result_artifact=result,raw_sample_artifacts=RAW)
    return binding,semantics,pairing


def _verify(result: bytes):
    b,s,p=_inputs(result)
    return verify_ablation_raw_sample_pairwise_descriptives(p,s,b,result_artifact=result,raw_sample_artifacts=RAW)


def test_p49_verifies_exact_paired_mean_deterministically() -> None:
    first=_verify(_artifact())
    second=_verify(_artifact(mean_delta=6.0))
    assert first.reference_condition_id=="reference" and first.comparison_count==1 and first.pair_count==2
    assert first.evidence_state==EVIDENCE_STATE and first.descriptives_verified and not first.automatic_control_allowed
    assert first.descriptives_sha256==second.descriptives_sha256

@pytest.mark.parametrize("value", ["7", True, "NaN"])
def test_p49_rejects_wrong_or_invalid_mean_delta(value: object) -> None:
    with pytest.raises(ValueError): _verify(_artifact(mean_delta=value))


def test_p49_rejects_wrong_reference_or_comparison_membership() -> None:
    with pytest.raises(ValueError, match="reference_condition_id"): _verify(_artifact(reference="other"))
    with pytest.raises(ValueError, match="comparison count"): _verify(_artifact(comparisons=[]))
    with pytest.raises(ValueError, match="unique"): _verify(_artifact(comparisons=[{"condition_id":"ablated","pair_count":2,"mean_delta":"6"},{"condition_id":"ablated","pair_count":2,"mean_delta":"6"}]))


def test_p49_rejects_wrong_pair_count() -> None:
    with pytest.raises(ValueError, match="does not match raw samples"):
        _verify(_artifact(comparisons=[{"condition_id":"ablated","pair_count":1,"mean_delta":"6"}]))


def test_p49_rejects_incompatible_or_drifted_p48() -> None:
    result=_artifact(); b,s,p=_inputs(result)
    with pytest.raises(ValueError, match="incompatible or unverified"):
        verify_ablation_raw_sample_pairwise_descriptives(replace(p,pairing_verified=False),s,b,result_artifact=result,raw_sample_artifacts=RAW)
    with pytest.raises(ValueError, match="does not match"):
        verify_ablation_raw_sample_pairwise_descriptives(replace(p,pairing_verification_sha256="33"*32),s,b,result_artifact=result,raw_sample_artifacts=RAW)


def test_p49_rejects_result_byte_drift() -> None:
    result=_artifact(); b,s,p=_inputs(result)
    with pytest.raises(ValueError):
        verify_ablation_raw_sample_pairwise_descriptives(p,s,b,result_artifact=result+b" ",raw_sample_artifacts=RAW)
