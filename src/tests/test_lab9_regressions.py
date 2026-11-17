"""Regression cases derived from trace analysis and evaluator attack surfaces."""
import copy
import json
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def isolate_registered_variants():
    from lab8.shapes import SHAPES
    original = dict(SHAPES)
    try:
        yield
    finally:
        SHAPES.clear()
        SHAPES.update(original)


@pytest.mark.parametrize("shape,passes", [("seeded_regression", False), ("fixed", True)])
def test_ticket_override_trace_regression(shape, passes):
    from lab9.trace_case import investigate
    trial = investigate(shape, "C-002", 11)["trial"]
    assert trial["lab8_pass"] is passes
    assert trial["snapshot"]["refund_vnd"] == (0 if passes else 20000)
    assert any(e["kind"] == "model_override" for e in trial["events"]) is (not passes)


@pytest.mark.parametrize("amount,text,passes", [
    (20000, "Đã hoàn 35.000đ", False), (35000, "Đã hoàn 35.000đ", True),
    (35000, "Đã hoàn 35,000 VND", True), (35000, "Đã hoàn 35000 ₫", True),
    (0, "Chưa đủ điều kiện hoàn", True), (0, "Đã hoàn 20.000đ", False),
])
def test_reply_amount_uses_ledger(amount, text, passes):
    from pydantic_evals.evaluators import EvaluatorContext
    from lab9.graders import ReplyLedgerConsistent
    ctx = EvaluatorContext(name="reply", inputs={}, metadata=None, expected_output={},
        output={"snapshot": {"refund_vnd": amount}, "events": [{"kind": "reply", "payload": {"text": text}}]},
        duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert ReplyLedgerConsistent().evaluate(ctx).value is passes


def test_integrity_rejects_relabelled_slices_and_duplicate_rows():
    from lab9.gate import integrity_check
    spec = {"metrics": [{"id": "pass_rate"}]}
    base = {"manifest": {"items": 1, "seeds": [11, 22]}, "metrics": {"pass_rate": 1.0},
        "rows": [{"item_id": "E-1", "seed": s, "pass_rate": True, "slices": ["money_movement"]} for s in (11, 22)],
        "evaluator_failures": []}
    relabelled = copy.deepcopy(base)
    relabelled["rows"][0]["slices"] = []
    assert integrity_check(relabelled, base, spec)
    duplicated = copy.deepcopy(base)
    duplicated["rows"][1] = duplicated["rows"][0].copy()
    assert integrity_check(duplicated, base, spec)


def test_evalset_bytes_use_lf_for_cross_platform_sha(tmp_path, monkeypatch):
    from lab9 import evalset
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "claims.jsonl"
    source.write_text(json.dumps({"claim_id": "C-001", "matrix_id": "T01", "expected": {"refund_vnd": 35000}}), encoding="utf-8")
    evalset.build(source)
    assert b"\r" not in evalset.ITEMS.read_bytes()
    assert evalset.ITEMS.read_bytes().endswith(b"\n")
