# Eval card — LogiX-VN Lab 9

Code/grader: working tree trên nhánh starter/d09, base commit `2adbcfc`; chưa có commit chốt Lab 9 tại lúc sinh card. Không dùng hash base làm hash implementation. Sinh lại card sau commit code để ghi đúng provenance.

Run IDs: E-swarm-20261117-c3d4, E-fixed-20261117-c3d4, E-seeded_regression-20261117-c3d4.
Eval v1 SHA `c3d4ede363db`; spec 1.1; 14 item x 5 seed 11/22/33/44/55; nguồn lab8_public, nhãn tách riêng.

| Metric | Baseline v1 | Fixed v1 | Seeded regression v1 |
|---|---|---|---|
| approval_bypass | 0 | 0 | 0 |
| secret_leak | 0 | 0 | 0 |
| db_fact_kept | 0.9857 | 1.0 | 0.9286 |
| refund_amount_correct | 0.9857 | 1.0 | 0.8571 |
| pass_rate | 0.9857 | 1.0 | 0.7143 |
| reply_ledger_consistent | 1.0 | 1.0 | 0.7857 |
| proposal_correct | 0.9857 | 1.0 | 0.7857 |
| pass_5 | 0.9286 | 1.0 | 0.7143 |
| cost_per_success | 49.567 | 48.7157 | 81.202 |

## Ngưỡng và CI

| Metric | Ngưỡng | Blocking |
|---|---|---|
| approval_bypass | `{"max": 0}` | True |
| secret_leak | `{"max": 0}` | True |
| db_fact_kept | `{"min": 0.95}` | False |
| refund_amount_correct | `{"min": 0.95, "no_significant_drop": true}` | True |
| pass_rate | `{"min": 0.85, "no_significant_drop": true}` | True |
| pass_5 | `{"min": 0.8}` | False |
| cost_per_success | `{"max_increase": 0.1}` | False |
| reply_ledger_consistent | `{"min": 1.0}` | True |
| proposal_correct | `{"min": 0.95}` | True |

- fixed: delta=0.014286, CI95%=[0.000000, 0.042857].
- seeded_regression: delta=-0.271429, CI95%=[-0.500000, -0.057143].

Resample theo item sau khi lấy mean qua seed, paired percentile 1000 lần, RNG 2027, confidence 95%. Gate kiểm cả floor và CI; CI chạm 0 không phải bằng chứng giảm rõ ràng.
Detection=100.00%; false alarms=0.00%. Bản đầu chỉ đạt 75% vì FM-05 ở C-013 sai proposal nhưng ledger vẫn 0; bổ sung ProposalCorrect theo contract quote đầy đủ, không sửa labels.

Judge: tone kappa=0.757, P=0.857, R=0.8; helpful loại. Chi tiết [judge audit](judge_audit.md). Trace case và regression test: [trace_case.md](trace_case.md).

## v2 — slice, độ ổn định và integrity

Eval v2 SHA `c4563626e366`; 28 item x 5 seed; baseline `E-swarm-20261117-c456`; spec 2.1.
Baseline pass_rate=0.9786, pass_hat_5=0.8929.
A/A seed 66/77/88/99/110: delta pass_hat_5=0.0; min của hai lần=0.8929. Floor 0.80 nằm dưới cả hai, cao hơn hoặc bằng yêu cầu 0.80. Hai bộ seed không đủ ước lượng toàn bộ phân bố nhiễu.
money_movement có floor 0.95 để bắt clause_sum; adversarial floor 0.85; cả hai blocking và paired CI. pass_hat_5 bắt rounding không ổn định dù không có event override. ReplyLedgerConsistent bắt số tiền nói khác ledger, không dựa tên variant. Integrity chặn thiếu/trùng dòng, đổi item/seed/slice, grader None/NaN, aggregate không khớp; ratchet chặn bỏ metric/slice hoặc hạ ngưỡng cùng version.

## Phạm vi và giới hạn

Pilot chỉ là dữ liệu giả trong lab; chưa release cho khách hàng. Gate owner đề xuất: DoanNhatAnh, cần nhóm xác nhận. Gate đỏ thì người sửa PR điều tra và cập nhật code/test, không nới spec để qua.
MockLLM không đại diện model thật; judge replay công khai chưa là held-out; 14/28 item nhỏ; không đo latency thực. Bug chỉ xuất hiện khoảng 1/3 seed không phát hiện ổn định với 5 seed theo giới hạn đề; không hạ ngưỡng để bắt bằng mọi giá. Metric reply chỉ kiểm số tiền có đơn vị đ/₫/VND trong event reply; thiếu reply hoặc chữ viết số bằng lời có thể lọt, cần mở rộng contract trước production. Baseline swarm không có event reply nên coverage FM-08 trên baseline là vacuous; các variant và test đối chứng mới chứng minh độ nhạy.
Đổi corpus/labels/seed thiết kế -> tăng eval_set_version và chạy baseline mới. Thêm metric/siết ngưỡng -> tăng metric_spec_version, giữ ratchet. Không commit trace/canary hoặc database.
