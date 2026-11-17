# Judge audit

Phân tích có hỗ trợ Codex dựa trên CSV replay và note sẵn có; không phải vòng gán nhãn độc lập mới. Nhóm cần duyệt các nhận định trước nộp. FAIL là lớp dương.

| Tiêu chí | n | kappa | Precision | Recall | TP/FP/FN/TN | Quyết định |
|---|---|---|---|---|---|---|
| tone | 100 | 0.757 | 0.857 | 0.8 | {'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66} | Dùng cho tone, không chấm tiền |
| helpful | 100 | 0.375 | 1.0 | 0.3 | {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70} | Loại |

## Audit các bất đồng

| Case | Judge | Human | Nhận định | Hành động sửa rubric |
|---|---|---|---|---|
| H-008 | PASS | FAIL | Giữ nhãn người theo note của dataset | Xưng em/nha quá suồng sã. Sửa rubric: quy định xưng hô lịch sự, không đồng nhất thân thiện với phù hợp. |
| H-017 | PASS | FAIL | Giữ nhãn người theo note của dataset | Xưng bạn/nha không phù hợp ngữ cảnh. Thêm ví dụ đối chứng cách xưng hô. |
| H-029 | PASS | FAIL | Giữ nhãn người theo note của dataset | Không cần nhắn thêm mang tính ra lệnh. Chấm cả câu, không chỉ dựa vào Dạ/vui lòng. |
| H-042 | FAIL | PASS | Giữ nhãn người theo note của dataset | Câu ngắn vẫn lịch sự và đủ thông tin. Không bắt buộc xin lỗi trong mọi phản hồi. |
| H-051 | FAIL | PASS | Giữ nhãn người theo note của dataset | Từ refund được CS cho phép. Không tự phạt từ tiếng Anh đã được cho phép. |
| H-063 | PASS | FAIL | Giữ nhãn người theo note của dataset | Hứa hoàn thêm ngoài kết quả hệ thống. Tách kiểm tra lời hứa khỏi tone và kiểm bằng dữ kiện hệ thống. |

Tone đạt kappa >=0.6, P>=0.8, R>=0.7; helpful không đạt kappa/recall, bỏ sót 21/30 lỗi. Rogan–Gladen: tone observed 0.28 -> 0.30; helpful 0.09 -> 0.30, nhưng hiệu chỉnh tỉ lệ không làm helpful đủ điều kiện dùng. Các đề xuất rubric chưa được chạy lại với nhãn held-out; không tuyên bố calibration đã cải thiện.
