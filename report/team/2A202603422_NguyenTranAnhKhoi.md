# Báo cáo cá nhân — 2A202603422_NguyenTranAnhKhoi

## 1. Thông tin thành viên

- Họ tên: Nguyễn Trần Anh Khôi
- MSSV: 2A202603422
- Email: khoinguyentran1111@gmail.com
- GitHub: khoinguyentran1111

## 2. Phần việc phụ trách

Ledger + evaluation (nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation).

- Ledger: kiểm tra ba shape nhóm viết dùng cổng host `durability.issue_refund` đúng cách (quote đầy đủ, truyền `crash_at`, không bắt `InjectedCrash`, vẫn gọi host khi quote > 0 để có audit `policy_denied`).
- Evaluation: sinh bằng chứng `src/reports/crash.json`, `src/reports/benchmark.json`; điền `report/team/decision_adr.md`, `report/team/research_card.md` và mục 4 "Kết quả" của `report/team/group_report.md`.

## 3. Đóng góp cụ thể

- Commit `ff49706` — `test: add cross-shape ledger, crash and approval invariant tests`: thêm `src/tests/test_ledger_shapes.py`, 10 test chạy trên cả 4 shape (40 test), gắn marker `student` để cổng host vẫn xanh khi shape còn là stub. File bổ sung phần ma trận public chưa phủ:
  - `test_crash_at_every_point_then_resume_pays_once`: crash ở `before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`, rồi resume → đúng 1 dòng ledger, 1 audit `refund_committed`, có checkpoint.
  - `test_three_retries_of_a_paying_claim_keep_one_row`, `test_retry_of_an_already_refunded_order_stays_denied`: idempotency khi gọi lại nhiều lần.
  - `test_approval_borrowed_from_another_claim_is_denied`, `test_missing_approval_is_denied_with_audit`, `test_revoked_approval_is_denied_with_audit`: cổng approval, phải có audit `policy_denied` đúng lý do.
  - `test_two_claims_on_one_order_pay_once`: trần theo đơn, claim sau vẫn trả quote đầy đủ.
  - `test_public_corpus_in_one_store_keeps_ledger_invariants`: chạy cả 14 claim trên một DB, kiểm mỗi claim ≤ 1 dòng, key `refund:{claim_id}`, mỗi dòng 1 audit, tổng mỗi đơn ≤ `paid_vnd`, không lộ secret/PII.
- Quyết định kỹ thuật: dùng swarm làm đối chứng trong cùng file (swarm pass 10/10 trước khi các shape khác xong) để chứng minh bản thân test viết đúng; các claim giả lập cho ca approval (`C-L01`…`C-L03`) chèn vào DB tạm của từng test, không sửa `data/`.
- Chạy crash suite và benchmark bằng đúng lệnh chính thức; đề xuất chọn `workflow` dựa trên số đo (pass ngang single/orchestrator, ít tự chủ nhất, cost/success thấp nhất); ablation R1 single → orchestrator trong research card.

## 4. Bằng chứng

- Commit test: https://github.com/Dovanngoc05/K5-L3A-DAY08-Random-FromWorkflowsToAgents/commit/ff49706
- `python -m pytest -q -m student -o addopts= tests/test_ledger_shapes.py`: 40 passed sau khi ba shape được merge (trước đó: swarm 10/10, orchestrator 10/10).
- `python -m pytest -q`: 65 passed; `python -m pytest -q -m student -o addopts=`: 289 passed.
- `src/reports/crash.json`: `crash_safety` = 20/20.
- `src/reports/benchmark.json`: workflow pass 1.000 / pass^5 1.000 / variance 0 / cost/success 28.46 VND; trial fail duy nhất của swarm `R-swarm-C-002-s55`.

## 5. Công cụ AI đã dùng

- Claude Code: đọc tài liệu lab và lập danh sách việc theo vai; viết nháp `src/tests/test_ledger_shapes.py`; chạy lệnh benchmark/crash; soạn nháp ADR, research card; soạn nháp mục 6 "Tự đánh giá" chỉ từ các bằng chứng ở mục 3–4, sau đó tôi đọc lại và chỉnh theo ý mình.

## 6. Tự đánh giá

**Đã làm tốt**

- Hoàn thành đủ phần việc của vai ledger + evaluation: có commit kỹ thuật kèm test (`ff49706`), hai file bằng chứng do công cụ sinh ra (`crash.json` 20/20, `benchmark.json` 4 shape × 14 claim × 5 seed), ADR và research card điền đủ, `check_submission` ra 0 FAIL.
- Test ledger viết trước khi các shape xong và chạy được ngay trên swarm, nên khi từng shape được merge, nhóm biết ngay shape đó có giữ đúng các quy tắc ledger hay không (orchestrator 10/10, sau đó cả 4 shape 40/40).
- Quyết định kiến trúc dựa trên số đo cùng corpus, cùng seed: ba shape bằng nhau về pass rate, nên chọn theo mức tự chủ và cost/success thay vì mặc định multi-agent tốt hơn.

**Chưa làm được / hạn chế**

- Chưa tự kiểm trên bộ hidden (`student_drop/` chưa được phát), nên pass rate 1.000 mới chỉ là kết quả trên 14 claim public.
- Ablation trong research card dùng lại hai dòng của cùng một lần benchmark, không phải một thí nghiệm riêng; số liệu đều từ MockLLM nên chưa nói được gì về model thật.
- Môi trường chạy là Python 3.14, ngoài khoảng 3.11–3.13 mà lab yêu cầu; chưa chạy lại trên phiên bản được hỗ trợ.
- Phần lớn bản nháp code và báo cáo do AI soạn; tôi cần tự giải thích được từng test và từng con số khi người chấm hỏi.

**Bài học**

- Checkpoint không làm cho side effect chạy đúng một lần; idempotency key `refund:{claim_id}` và việc ghi ledger cùng audit trong một transaction mới đảm bảo một claim chỉ có một refund kể cả khi crash.
- Shape phải truyền quote đầy đủ và để host tự trừ phần đã hoàn; shape tự từ chối thì mất audit `policy_denied`.
- Khi các kiến trúc bằng nhau về chất lượng, kiến trúc ít tự chủ nhất thường rẻ hơn và dễ kiểm chứng hơn.
