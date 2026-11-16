# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu benchmark và crash lấy từ artefact do công cụ lab tạo trong `src/reports/`.

## 1. Thông tin nhóm

- Tên nhóm: Random
- Thành viên và vai trò: xem `TEAM.md`.
- Commit benchmark được ghi trong ADR: `5fb3b5d`. Cập nhật commit chốt sau khi nhóm hoàn thiện và commit báo cáo này.

## 2. Mục tiêu và cách tiếp cận

Bài lab so sánh bốn kiến trúc xử lý cùng một luồng claim hoàn phí: workflow, single agent, orchestrator và swarm tham chiếu. Nhóm đánh giá mức độ hoàn thành nghiệp vụ, độ ổn định qua seed và chi phí mô phỏng, rồi chọn kiến trúc ít tự chủ nhất vẫn xử lý đúng yêu cầu. Dữ liệu và MockLLM đều là thành phần mô phỏng của lab; không cần API key hay model bên ngoài.

Nhóm chia việc theo các mảng workflow và tích hợp, single agent, orchestrator và handoff, ledger và đánh giá. Phần triển khai được kiểm tra bằng test theo shape và test bất biến dùng chung; sau đó nhóm chạy benchmark trên cùng claim, seed, bảng giá và evaluator. Thông tin từng thành viên, commit và test phụ trách được ghi trong `TEAM.md` và báo cáo cá nhân.

## 3. Giải pháp

Cả bốn shape tuân theo cùng chữ ký `run_claim(claim_id, *, seed, store_path, crash_at)` và cùng contract kết quả. Các công cụ đọc trả dữ liệu đã lọc. Ticket là dữ liệu người dùng, không phải nguồn sự thật về đơn hàng hay chính sách.

### Shape A — Workflow

Workflow thực hiện các bước cố định trong Python: đọc claim qua `get_claim_view`, xác minh quyền xem đơn bằng `lookup_order`, rồi lấy quote bằng `compute_compensation` từ dữ liệu order và policy hiện hành. Nếu quote dương, workflow gửi toàn bộ quote cùng `crash_at` đến `durability.issue_refund`. Host kiểm tra approval, trần theo đơn và idempotency trước khi ghi ledger. Workflow dùng MockLLM để soạn phản hồi, không để model quyết định số tiền.

Trace của workflow ghi claim id và cờ có mã đơn, kết quả visibility/reason khi tra order, quote, phản hồi host và quyết định cuối. Các nhánh trả sớm vẫn tạo trace qua helper chung. Không ghi ticket, claim/order row thô, secret hay thông tin cá nhân.

### Shape B — Single agent

Single agent chạy vòng ReAct giới hạn tối đa 8 bước. Agent chọn các công cụ đọc để xác minh order và lấy quote; write tool không được dispatch từ model. Code kiểm tra kết quả sau vòng lặp và chỉ gọi `durability.issue_refund` khi quote dương, truyền quote đầy đủ cùng `crash_at`. Host là nơi duy nhất kiểm approval và ghi refund. Test riêng `test_single_uses_order_facts_instead_of_ticket_delay` kiểm tra ticket khai sai độ trễ không làm thay đổi quyết định, không phát sinh refund sai và trace có cấu trúc hợp lệ.

### Shape C — Orchestrator và investigator chỉ đọc

Orchestrator đọc claim an toàn, rồi tạo handoff bằng `make_handoff` với facts tối thiểu và danh sách công cụ chỉ đọc. Investigator chạy qua `run_readonly_investigators`; quyền truy cập order được kiểm tra theo principal. Handoff không mang ticket, parent context, secret hoặc raw headers. Quote do code tính từ order/policy; orchestrator gửi quote đầy đủ tới host để kiểm approval và ghi refund. Trace ghi handoff đã sanitize, thông tin investigator đã rút gọn, quote và quyết định; không dump claim/order hoặc kết quả thô.

### Ranh giới chung giữa model, code và host

`compute_compensation`/quote xác định entitlement; shape không tự trừ số tiền đã hoàn trước đó. `durability.issue_refund` xác minh approval thuộc claim, áp trần theo đơn, bảo đảm idempotency và ghi ledger/audit trong transaction. Các shape chuyển tiếp `crash_at` và để `InjectedCrash` truyền ra để crash suite có thể kiểm tra resume. Trace tuân [contract](../../docs/contracts.md); field nhạy cảm được loại khỏi log, handoff và stdout.

## 4. Kết quả

Benchmark được tạo bằng lệnh sau trong `src/`:

```powershell
python -m lab8.benchmark --shapes workflow,single,orchestrator,swarm --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/benchmark.json
```

Thiết lập gồm 14 claim public (C-001…C-014), năm seed (11, 22, 33, 44, 55), MockLLM, cùng bảng giá và evaluator. Mỗi shape có 70 trial.

| Shape | Pass rate | Pass^5 | Seed min–max | Variance | Cost/success (VND mô phỏng) | Mean / p95 steps | Mean model calls | Mean tool calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A workflow | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.46 | 4.43 / 5 | 0.64 | 2.79 |
| B single | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 28.47 | 3.79 / 4 | 0.93 | 2.79 |
| C orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0.000000 | 47.44 | 3.71 / 4 | 1.00 | 4.64 |
| D swarm (tham chiếu) | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 | 4.66 |

Ba shape nhóm viết đều đạt 70/70 trial; pass rate không phân biệt được chất lượng của chúng trên corpus này. Swarm trượt một trial, `R-swarm-C-002-s55`, vì tin ngày trễ trong ticket thay vì dữ liệu order. Orchestrator có cost/success cao hơn workflow khoảng 67% mà không tăng số trial đạt; workflow thấp hơn single một mức nhỏ về cost/success. Mean/p95 steps là số event trong trace, do đó không phải phép đo latency.

Crash suite được tạo bằng `python -m lab8.crash_test --count 20 --out reports/crash.json`; artefact ghi `crash_safety = 20/20`. Hồ sơ kiểm thử trong báo cáo evaluation ghi cổng host đạt 65 passed và student suite đạt 289 passed, gồm ma trận shape và 40 test ledger (10 test × 4 shape). Kết quả Single được chạy riêng trong terminal là `60 passed, 188 deselected` cho ma trận public; đây không phải benchmark nhóm hay hidden score.

Chưa có `student_drop/` để tự kiểm hidden. Bộ public chỉ có 14 claim nên kết quả này chưa chứng minh pass rate hidden. Chi tiết benchmark và crash được lưu tại `src/reports/benchmark.json` và `src/reports/crash.json`.

### Quyết định kiến trúc

Nhóm chọn **workflow** theo ADR: cả workflow, single và orchestrator đều đạt cùng pass rate/pass^5 trên public, trong khi workflow có mức tự chủ thấp nhất và cost/success thấp nhất (28.46 VND; single 28.47, orchestrator 47.44). Swarm vừa tốn hơn vừa có một lỗi do tin ticket. Kết luận dựa trên MockLLM và corpus public; sẽ cần đánh giá lại nếu hidden hoặc dữ liệu mới cho thấy workflow không đạt ngưỡng, hay nếu tác vụ có nhiều nguồn độc lập cần phối hợp.

## 5. Khó khăn và cách xử lý

- Lọc pytest bằng `-k single` chỉ khớp tên hàm `test_public_single_run_cases`, không tự lọc tham số shape. Để chạy riêng Single trong ma trận public, dùng:

  ```powershell
  python -m pytest -q -m student -o addopts= tests/test_public_matrix.py -k "single_run_cases and not workflow and not orchestrator and not swarm"
  ```

  Kết quả quan sát: `60 passed, 188 deselected`.
- Môi trường của một lần kiểm tra chỉ có Python 3.10; `python -m lab8.smoke` yêu cầu Python 3.11 trở lên. Pytest vẫn chạy ở lần đó, nhưng trước khi nộp cần xác nhận smoke trên Python 3.11–3.13 theo yêu cầu lab.
- Các lần chạy student trước khi workflow và orchestrator được tích hợp còn có lỗi ở những shape đó. Sau khi ghép, báo cáo evaluation ghi suite student đạt 289 passed. Nên chạy lại trên commit nộp cuối để bảo đảm kết quả tương ứng với đúng phiên bản đang nộp.

## 6. Tổng hợp đóng góp

Chi tiết commit và test của thành viên nằm trong `TEAM.md` và các báo cáo cá nhân.

### Đỗ Văn Ngọc — Single agent

- Triển khai `src/lab8/shapes/single.py`: vòng ReAct tối đa 8 bước, dùng tool đọc, tính quote từ dữ kiện đã xác minh và gọi host cho refund.
- Thêm `src/tests/test_single_agent.py::test_single_uses_order_facts_instead_of_ticket_delay`.
- Bằng chứng chạy riêng ma trận public: 60 passed; benchmark chung ghi Single đạt 1.000 pass rate và 1.000 pass^5. Bổ sung commit kỹ thuật cụ thể trong `TEAM.md` trước khi nộp.

### Đoàn Nhật Anh — Orchestrator, handoff và bảo mật trace

- Triển khai orchestrator và test bảo mật handoff/trace; commit `158d999`.
- Chi tiết và giới hạn kiểm thử được ghi trong báo cáo cá nhân `report/team/2A202603408_DoanNhatAnh.md`.

### Nguyễn Trần Anh Khôi — Ledger và evaluation

- Thêm test ledger liên shape, sinh benchmark/crash artefact và hoàn thiện ADR/research card; commit test `ff49706`.
- Chi tiết phương pháp và kết quả được ghi trong báo cáo cá nhân `report/team/2A202603422_NguyenTranAnhKhoi.md`.

### Nguyễn Quang Duy-Workflow và tích hợp

- Shape workflow và tích hợp được hoàn thiện trong các commit đã merge vào nhánh nhóm. 

## 7. Hạn chế và hướng cải thiện

MockLLM là mô phỏng xác định theo seed, không đại diện đầy đủ cho hành vi hoặc chi phí của model sản xuất; latency là `unavailable`. Corpus public có 14 claim và không thay thế hidden suite. Pass rate public 1.000 của ba shape không đảm bảo kết quả tương tự trên claim mới hoặc model thật. Workflow ổn định và rẻ trên luật hiện tại nhưng chỉ xử lý được các tình huống đã mã hóa; nếu cần đọc chứng từ tự do hoặc tổng hợp nhiều nguồn không cấu trúc, nhóm nên đánh giá lại single/orchestrator bằng cùng corpus, seed, giá và evaluator. Không dùng các số public để suy ra điểm hidden.

## 8. Tài liệu tham khảo

- `README.md`, `CHECKPOINTS.md`, `RULES.md`, `RUBRIC.md`, `SUBMISSION.md` — đề bài, checkpoint, quy tắc và yêu cầu nộp.
- [`docs/business_rules.md`](../../docs/business_rules.md), [`docs/contracts.md`](../../docs/contracts.md), [`docs/architecture.md`](../../docs/architecture.md), [`docs/metrics.md`](../../docs/metrics.md) — nghiệp vụ, contract, kiến trúc và định nghĩa metric.
- `src/lab8/shapes/swarm_reference.py` — shape swarm tham chiếu.
- `src/reports/benchmark.json`, `src/reports/crash.json` — artefact đo benchmark và crash suite.
- `report/team/decision_adr.md`, `report/team/research_card.md` — quyết định kiến trúc và phiếu nghiên cứu/ablation của nhóm.
