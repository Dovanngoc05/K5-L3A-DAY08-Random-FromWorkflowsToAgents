# Trace case — C-002@11

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`; report `E-seeded_regression-20261117-c3d4` |
| Triệu chứng | status resolved thay vì denied; ledger 20.000 VND thay vì 0; reply báo đã hoàn 20.000đ |
| Bước sai đầu tiên | Event 3, `model_override`, payload `delay_days: 5` |
| Vì sao đầu tiên | Event 1 handoff chỉ đọc; event 2 investigator lấy order O-202 có delay DB=2. Event 3 mới thay giá trị bằng lời kể ticket |
| Failure mode | FM-03; các bước quote và ghi tiền sau đó là hậu quả |
| Đối chứng | `fixed`, cùng claim/seed: event 3 là quote=0, không có override, status denied, ledger=0 |
| Regression test | `tests/test_lab9_regressions.py::test_ticket_override_trace_regression`: xác nhận variant lỗi fail và fixed pass trên store mới |
| Chưa chắc chắn | Một trace không ước lượng tần suất ngoài corpus; event override thiếu không chứng minh không có lỗi |

Lệnh: `python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11`; đối chứng đổi shape thành `fixed`.
