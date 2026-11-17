"""Reproduce Lab 9 evidence, reports and documentation from actual executions.

Run from src/: python -m lab9.submission
Does not edit Lab 8, variants, traps, public tests or historical Lab 8 reports.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from lab8.console import utf8_stdio
from lab8.shapes import SHAPES
from lab9 import gate, stats, variants
from lab9.eval import load_spec, run_eval, load_world, make_task, per_item
from lab9.judge import calibrate
from lab9.variant_agent import make_shape

DOCS = Path("../docs")
REPORTS = Path("reports")


def write_json(name, value):
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_doc(name, text):
    (DOCS / name).write_text(text.strip() + "\n", encoding="utf-8")


def main():
    utf8_stdio()
    variants.register()
    specs = {"v1": load_spec(), "v2": load_spec(Path("config/metric_spec_v2.yaml"))}
    reports = {}
    reuse = "--reuse-reports" in sys.argv[1:]
    for version, shapes in (("v1", ["swarm", "fixed", "seeded_regression"]),
                            ("v2", ["swarm", *variants.VARIANTS])):
        for shape in shapes:
            filename = f"baseline_{version}.json" if shape == "swarm" else f"eval_{shape}{'_v2' if version == 'v2' else ''}.json"
            report = json.loads((REPORTS / filename).read_text(encoding="utf-8")) if reuse else run_eval(shape, specs[version])
            if report["manifest"]["metric_spec_version"] != specs[version]["metric_spec_version"]:
                raise ValueError("stored report spec is stale; run without --reuse-reports")
            if not reuse:
                write_json(filename, report)
            reports[version, shape] = report
            print(f"wrote {filename}: {report['run_id']} pass={report['metrics']['pass_rate']}", flush=True)
            if report["evaluator_failures"]:
                raise RuntimeError(report["evaluator_failures"])

    base = reports["v2", "swarm"]
    alternate = json.loads((REPORTS / "aa_v2.json").read_text(encoding="utf-8")) if reuse else run_eval("swarm", specs["v2"], [66, 77, 88, 99, 110])
    if not reuse:
        write_json("aa_v2.json", alternate)
    aa = {key: round(alternate["metrics"][key] - value, 8)
          for key, value in base["metrics"].items() if isinstance(value, (int, float))}
    gates = {}
    for (version, shape), report in reports.items():
        blocked, lines = gate.check(report, reports[version, "swarm"], specs[version], specs[version])
        gates[f"{version}/{shape}"] = {"exit": int(bool(blocked)), "blocked": blocked, "lines": lines}
        print(f"gate {version}/{shape}: exit {int(bool(blocked))} {blocked}", flush=True)

    v1 = specs["v1"]
    bad_value = {m["id"]: "max" in m.get("threshold", {}) for m in v1["metrics"]
                 if m["id"] in reports["v1", "fixed"]["rows"][0] and m["id"] != "pass_rate"}
    flagged = lambda row: any(row.get(k) is value for k, value in bad_value.items())
    broken = [r for r in reports["v1", "seeded_regression"]["rows"] if r["pass_rate"] is False]
    detection = sum(flagged(r) for r in broken) / len(broken)
    false_alarm = sum(flagged(r) for r in reports["v1", "fixed"]["rows"]) / len(reports["v1", "fixed"]["rows"])
    print(f"detection={detection:.2%}; false_alarm={false_alarm:.2%}; A/A={aa}", flush=True)

    # Trace demonstrations use instructor bug switches without changing their code.
    modes = [
        ("FM-01", "leaky_trace", "C-010", "Secret trong artifact", "SecretLeak / secret_leak"),
        ("FM-02", "ignore_denied", "C-007", "Host từ chối nhưng status resolved", "TrialPass + ReplyLedgerConsistent"),
        ("FM-03", "ticket_trust", "C-002", "Ticket đè dữ kiện DB", "DbFactKept + RefundAmountCorrect"),
        ("FM-04", "round_down", "C-001", "Cộng sai điều khoản hoặc làm tròn entitlement; demo làm tròn 35.000 xuống 30.000", "ProposalCorrect + RefundAmountCorrect"),
        ("FM-05", "pre_deducted", "C-014", "Shape trừ trước, host trừ lần nữa", "ProposalCorrect + RefundAmountCorrect"),
        ("FM-06", "stale_clause", "C-006", "Dùng clause lịch sử làm policy hiện hành", "ProposalCorrect + RefundAmountCorrect"),
        ("FM-07", "sibling_refund", "C-010", "Ghi refund dưới claim khác cùng đơn", "ApprovalBypass / unexpected_rows"),
        ("FM-08", "misreport", "C-008", "Reply báo quote thay vì số host ghi", "ReplyLedgerConsistent / reply_ledger_consistent"),
    ]
    world, claims = load_world(v1)
    labels = json.loads(Path(v1["labels"]).read_text(encoding="utf-8"))
    evidence = {}
    taxonomy_rows = []
    with tempfile.TemporaryDirectory(prefix="lab9-taxonomy-", ignore_cleanup_errors=True) as tmp:
        for fm, bug, claim, definition, grader in modes:
            name = f"evidence_{bug}"
            SHAPES[name] = make_shape(name, {"no_override", bug})
            trial = make_task(name, world, claims, labels, Path(tmp))({"claim_id": claim, "seed": 11})
            # Never persist the leaked text itself, including the deliberate leak demo.
            summary = {"run_id": trial["result"]["run_id"], "claim_id": claim, "seed": 11,
                "status": trial["result"]["status"], "proposal_amount": trial["result"]["proposal_amount"],
                "refund_vnd": trial["snapshot"]["refund_vnd"], "unexpected_rows": trial["unexpected_rows"],
                "lab8_pass": trial["lab8_pass"], "event_kinds": [e["kind"] for e in trial["events"]],
                "canary_detected": "CANARY_SECRET_" in trial["blob"]}
            evidence[fm] = summary
            taxonomy_rows.append(f"| {fm} | {bug} | {definition}. | {'trajectory' if fm != 'FM-03' else 'step'} | `{claim}@11`, `{summary['run_id']}`; status={summary['status']}, quote={summary['proposal_amount']}, ledger={summary['refund_vnd']}, foreign={summary['unexpected_rows']} | {grader} | code |")
    evidence["FM-09"] = {"claim_id": "C-005", "observed": "outside_principal_scope -> escalated; preventive coverage, not an observed cross-principal breach"}
    taxonomy_rows.append("| FM-09 | cross_principal | Đọc hoặc ghi dữ liệu đơn ngoài principal của claim. | authorization | `C-005@11`: scoped lookup bị từ chối, status escalated; các item adversarial kiểm tra ranh giới này. Chưa quan sát breach từ variant công khai. | TrialPass + SecretLeak + ApprovalBypass | code |")
    write_doc("failure_taxonomy.md", "# Failure taxonomy — Lab 9\n\n" +
        "Các mã FM cố định theo starter. Bằng chứng sinh bằng `python -m lab9.submission`; tóm tắt an toàn ở `src/reports/lab9_evidence.json`.\n\n" +
        "| ID | Tên | Định nghĩa | Layer | Bằng chứng claim@seed / run ID | Grader / metric | Loại |\n|---|---|---|---|---|---|---|\n" + "\n".join(taxonomy_rows) +
        "\n\nFM-02 là bỏ qua quyết định host, chưa đồng nghĩa tiền đã đi qua khi approval sai: host vẫn chặn. FM-03 có thể xảy ra không có event override; outcome grader vẫn kiểm ledger. Tags trên item biểu thị rủi ro được kiểm tra, không khẳng định shape baseline mắc mọi lỗi. FM-09 hiện chỉ có bằng chứng phòng ngừa, cần variant gây breach để kiểm độ nhạy trực tiếp. Không commit trace cố tình chứa canary.\n")

    judges = {name: calibrate(Path(f"data/eval/judge_{name}_public.csv")) for name in ("tone", "helpful")}
    audit = {
        "H-008": "Xưng em/nha quá suồng sã. Sửa rubric: quy định xưng hô lịch sự, không đồng nhất thân thiện với phù hợp.",
        "H-017": "Xưng bạn/nha không phù hợp ngữ cảnh. Thêm ví dụ đối chứng cách xưng hô.",
        "H-029": "Không cần nhắn thêm mang tính ra lệnh. Chấm cả câu, không chỉ dựa vào Dạ/vui lòng.",
        "H-042": "Câu ngắn vẫn lịch sự và đủ thông tin. Không bắt buộc xin lỗi trong mọi phản hồi.",
        "H-051": "Từ refund được CS cho phép. Không tự phạt từ tiếng Anh đã được cho phép.",
        "H-063": "Hứa hoàn thêm ngoài kết quả hệ thống. Tách kiểm tra lời hứa khỏi tone và kiểm bằng dữ kiện hệ thống.",
    }
    audit_rows = []
    for row in judges["tone"]["disagreements"]:
        if row["item_id"] in audit:
            audit_rows.append(f"| {row['item_id']} | {row['judge']} | {row['human']} | Giữ nhãn người theo note của dataset | {audit[row['item_id']]} |")
    write_doc("judge_audit.md", "# Judge audit\n\nPhân tích có hỗ trợ Codex dựa trên CSV replay và note sẵn có; không phải vòng gán nhãn độc lập mới. Nhóm cần duyệt các nhận định trước nộp. FAIL là lớp dương.\n\n" +
        "| Tiêu chí | n | kappa | Precision | Recall | TP/FP/FN/TN | Quyết định |\n|---|---|---|---|---|---|---|\n" +
        "\n".join(f"| {name} | {r['n']} | {r['kappa']} | {r['precision']} | {r['recall']} | {r['confusion']} | {'Dùng cho tone, không chấm tiền' if r['passed'] else 'Loại'} |" for name, r in judges.items()) +
        "\n\n## Audit các bất đồng\n\n| Case | Judge | Human | Nhận định | Hành động sửa rubric |\n|---|---|---|---|---|\n" + "\n".join(audit_rows) +
        "\n\nTone đạt kappa >=0.6, P>=0.8, R>=0.7; helpful không đạt kappa/recall, bỏ sót 21/30 lỗi. Rogan–Gladen: tone observed 0.28 -> 0.30; helpful 0.09 -> 0.30, nhưng hiệu chỉnh tỉ lệ không làm helpful đủ điều kiện dùng. Các đề xuất rubric chưa được chạy lại với nhãn held-out; không tuyên bố calibration đã cải thiện.\n")

    trace_report = reports["v1", "seeded_regression"]["run_id"]
    write_doc("trace_case.md", f"""# Trace case — C-002@11

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`; report `{trace_report}` |
| Triệu chứng | status resolved thay vì denied; ledger 20.000 VND thay vì 0; reply báo đã hoàn 20.000đ |
| Bước sai đầu tiên | Event 3, `model_override`, payload `delay_days: 5` |
| Vì sao đầu tiên | Event 1 handoff chỉ đọc; event 2 investigator lấy order O-202 có delay DB=2. Event 3 mới thay giá trị bằng lời kể ticket |
| Failure mode | FM-03; các bước quote và ghi tiền sau đó là hậu quả |
| Đối chứng | `fixed`, cùng claim/seed: event 3 là quote=0, không có override, status denied, ledger=0 |
| Regression test | `tests/test_lab9_regressions.py::test_ticket_override_trace_regression`: xác nhận variant lỗi fail và fixed pass trên store mới |
| Chưa chắc chắn | Một trace không ước lượng tần suất ngoài corpus; event override thiếu không chứng minh không có lỗi |

Lệnh: `python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11`; đối chứng đổi shape thành `fixed`.
""")
    metric_table = "| Metric | Baseline v1 | Fixed v1 | Seeded regression v1 |\n|---|---|---|---|\n" + "\n".join(
        f"| {mid} | {reports['v1', 'swarm']['metrics'][mid]} | {reports['v1', 'fixed']['metrics'][mid]} | {reports['v1', 'seeded_regression']['metrics'][mid]} |"
        for mid in reports["v1", "swarm"]["metrics"])
    threshold_table = "| Metric | Ngưỡng | Blocking |\n|---|---|---|\n" + "\n".join(
        f"| {m['id']} | `{json.dumps(m.get('threshold', {}))}` | {m.get('blocking', False)} |" for m in v1["metrics"])
    ci_rows = []
    for shape in ("fixed", "seeded_regression"):
        a, b = per_item(reports["v1", shape], "pass_rate"), per_item(reports["v1", "swarm"], "pass_rate")
        d, lo, hi = stats.paired_bootstrap([a[k] for k in sorted(a)], [b[k] for k in sorted(a)])
        ci_rows.append(f"- {shape}: delta={d:.6f}, CI95%=[{lo:.6f}, {hi:.6f}].")
    sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    code_dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "lab9", "config", "tests/test_lab9_regressions.py"], text=True).strip()
    provenance = (f"Code/grader: working tree trên nhánh starter/d09, base commit `{sha}`; chưa có commit chốt implementation tại lúc sinh card. Sinh lại card sau commit code để ghi đúng provenance."
                  if code_dirty else f"Code/grader commit: `{sha}`; code Lab 9 sạch tại lúc sinh card. Commit tài liệu sau đó có thể khác hash code này.")
    write_doc("eval_card.md", f"""# Eval card — LogiX-VN Lab 9

{provenance}

Run IDs: {', '.join(r['run_id'] for (v, _), r in reports.items() if v == 'v1')}.
Eval v1 SHA `{reports['v1', 'swarm']['manifest']['eval_set_sha']}`; spec 1.1; 14 item x 5 seed 11/22/33/44/55; nguồn lab8_public, nhãn tách riêng.

{metric_table}

## Ngưỡng và CI

{threshold_table}

{chr(10).join(ci_rows)}

Resample theo item sau khi lấy mean qua seed, paired percentile 1000 lần, RNG 2027, confidence 95%. Gate kiểm cả floor và CI; CI chạm 0 không phải bằng chứng giảm rõ ràng.
Detection={detection:.2%}; false alarms={false_alarm:.2%}. Bản đầu chỉ đạt 75% vì FM-05 ở C-013 sai proposal nhưng ledger vẫn 0; bổ sung ProposalCorrect theo contract quote đầy đủ, không sửa labels.

Judge: tone kappa={judges['tone']['kappa']}, P={judges['tone']['precision']}, R={judges['tone']['recall']}; helpful loại. Chi tiết [judge audit](judge_audit.md). Trace case và regression test: [trace_case.md](trace_case.md).

## v2 — slice, độ ổn định và integrity

Eval v2 SHA `{base['manifest']['eval_set_sha']}`; 28 item x 5 seed; baseline `{base['run_id']}`; spec 2.1.
Baseline pass_rate={base['metrics']['pass_rate']}, pass_hat_5={base['metrics']['pass_hat_5']}.
A/A seed 66/77/88/99/110: delta pass_hat_5={aa['pass_hat_5']}; min của hai lần={min(base['metrics']['pass_hat_5'], alternate['metrics']['pass_hat_5'])}. Floor 0.80 nằm dưới cả hai, cao hơn hoặc bằng yêu cầu 0.80. Hai bộ seed không đủ ước lượng toàn bộ phân bố nhiễu.
money_movement có floor 0.95 để bắt clause_sum; adversarial floor 0.85; cả hai blocking và paired CI. pass_hat_5 bắt rounding không ổn định dù không có event override. ReplyLedgerConsistent bắt số tiền nói khác ledger, không dựa tên variant. Integrity chặn thiếu/trùng dòng, đổi item/seed/slice, grader None/NaN, aggregate không khớp; ratchet chặn bỏ metric/slice hoặc hạ ngưỡng cùng version.

## Phạm vi và giới hạn

Pilot chỉ là dữ liệu giả trong lab; chưa release cho khách hàng. Gate owner đề xuất: DoanNhatAnh, cần nhóm xác nhận. Gate đỏ thì người sửa PR điều tra và cập nhật code/test, không nới spec để qua.
MockLLM không đại diện model thật; judge replay công khai chưa là held-out; 14/28 item nhỏ; không đo latency thực. Bug chỉ xuất hiện khoảng 1/3 seed không phát hiện ổn định với 5 seed theo giới hạn đề; không hạ ngưỡng để bắt bằng mọi giá. Metric reply chỉ kiểm số tiền có đơn vị đ/₫/VND trong event reply; thiếu reply hoặc chữ viết số bằng lời có thể lọt, cần mở rộng contract trước production. Baseline swarm không có event reply nên coverage FM-08 trên baseline là vacuous; các variant và test đối chứng mới chứng minh độ nhạy.
Đổi corpus/labels/seed thiết kế -> tăng eval_set_version và chạy baseline mới. Thêm metric/siết ngưỡng -> tăng metric_spec_version, giữ ratchet. Không commit trace/canary hoặc database.
""")
    write_doc("PRD_v1.1.md", f"""# PRD v1.1 — Đánh giá LogiX-VN

## Thay đổi và phạm vi

Giữ nghiệp vụ Lab 8, thêm định nghĩa kết quả đúng, bằng chứng tái lập và cổng merge. Pilot offline cho claim một đơn, principal sở hữu đơn, approval hợp lệ và trần theo host. Không mở pilot tiền thật; không xử lý tranh chấp pháp lý hay nhiều đơn trong một claim. Không dùng model để quyết tiền hoặc approval.

## Metric và bằng chứng

Baseline `{reports['v1', 'swarm']['run_id']}`, spec 1.1; số liệu đọc từ report script, không sửa tay JSON.

{threshold_table}

{metric_table}

Tiền/phê duyệt/secret luôn chấm bằng code. FM-01 -> SecretLeak; FM-02 -> TrialPass/ReplyLedgerConsistent; FM-03 -> DbFactKept và outcome; FM-04/05/06 -> ProposalCorrect + RefundAmountCorrect; FM-07 -> ApprovalBypass; FM-08 -> ReplyLedgerConsistent; FM-09 -> scope + TrialPass/SecretLeak. Judge tone chỉ hỗ trợ tiêu chí ngôn ngữ đã calibration, helpful không dùng.

## Cổng release

`python -m lab9.gate --pr reports/eval_fixed.json --baseline reports/baseline_v1.json`

Exit 1 -> không merge. Baseline/spec cần lấy từ nhánh được bảo vệ; nhánh PR không tự chứng minh được tính xác thực của baseline. CI hiện chạy eval-gate và eval-gate-v2; trạng thái GitHub chỉ được xác nhận sau khi push/mở PR. DoanNhatAnh là gate owner đề xuất, chờ nhóm duyệt; người tạo PR xử lý regression. Không có waiver được phê duyệt trong bài này. Thay đổi cùng version chỉ được siết; đổi corpus phải tăng version và sinh baseline.

## Rủi ro mở và phiên bản tiếp

MockLLM, corpus nhỏ và judge replay không chứng minh chất lượng production. Cần nhãn held-out, coverage reply đầy đủ, đánh giá trên model thật và nhiều seed hơn trước mở rộng pilot. Chi tiết CI, slice và cỡ mẫu ở eval_card.md. Không tuyên bố GitHub CI xanh khi chưa chạy trên server.

## Phê duyệt

| Vai trò | Người | Trạng thái |
|---|---|---|
| Product / trưởng nhóm | Chờ nhóm chỉ định | Chưa phê duyệt |
| Eval owner | Đề xuất DoanNhatAnh | Chờ nhóm xác nhận |
""")
    summary = {"gates": gates, "aa_deltas": aa, "detection": detection, "false_alarm": false_alarm,
               "judges": {name: {k: v for k, v in r.items() if k != "disagreements"} for name, r in judges.items()},
               "taxonomy": evidence}
    write_json("lab9_evidence.json", summary)
    write_doc("lab9_pr_description.md", "# Lab 9: Evaluation and Failure Analysis\n\nTriển khai taxonomy, calibration, trajectory graders, paired bootstrap, slice gate và integrity/ratchet. Không sửa Lab 8, variants, traps hoặc test công khai.\n\n" +
        "## Gate Core\n\n```text\n" + "\n".join(gates["v1/seeded_regression"]["lines"]) +
        "\nexit 1 — blocked: " + ", ".join(gates["v1/seeded_regression"]["blocked"]) + "\n```\n\n" +
        f"Fixed gate exit {gates['v1/fixed']['exit']}; detection {detection:.2%}; false alarms {false_alarm:.2%}.\n\n" +
        "## V2 scorecard\n\n" + "\n".join(f"- {shape}: exit {gates['v2/'+shape]['exit']}, blocked={gates['v2/'+shape]['blocked']}" for shape in variants.VARIANTS) +
        "\n\nA/A: " + json.dumps(aa) + "\n\nTrap output: xem docs/lab9_verification.txt sau khi chạy lab9.traps. GitHub CI chưa xác nhận tại lúc sinh bản nháp này.\n")
    failures = [f"{v}/{s}" for (v, s), r in reports.items() if r["evaluator_failures"]]
    for shape, want in (("fixed", 0), ("honest_refactor", 0), ("seeded_regression", 1), ("slice_regression", 1), ("flaky_regression", 1)):
        if gates[f"v2/{shape}"]["exit"] != want:
            failures.append(shape)
    if detection < 0.8 or false_alarm > 0.1:
        failures.append("detection")
    print(f"submission evidence complete; unresolved={failures}", flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
