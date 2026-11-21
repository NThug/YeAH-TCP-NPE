# I1 – Kiểm toán tổng thể 32 lượt mô phỏng YeAH-TCP

**Trạng thái:** KIỂM TOÁN ĐẠT trên bản sao dữ liệu gốc đã nhận; dữ liệu thí nghiệm được **khóa về mặt phiên bản** để chuyển sang I2. Chưa có cơ sở công nhận mức tương đương định lượng với paper.

**Căn cứ:** `step-I1-analysis.tar.gz` do người thực hiện gửi; bốn gói raw riêng `step-H1-experiments.tar.gz`, `step-H2-buffer.tar.gz`, `step-H3-fairness.tar.gz`, `step-H4-random-loss.tar.gz` đã gửi trước đó; PDF gốc `4-YeAH_TCP.pdf`; source `yeah-experiment.cc` trong I1.

## 1. Kiểm tra thành phần và provenance

| Nhóm | Số lượt chạy | Thời lượng/lượt | Số mẫu trace/lượt | Hình PNG/SVG | Bảng CSV phân tích |
|---|---:|---:|---:|---:|---:|
| H1 | 8 | 600 s | 60.001 | 7 + 7 | 3 |
| H2 | 8 | 600 s | 60.001 | 5 + 5 | 3 |
| H3 | 8 | 600 s | 60.001 | 4 + 4 | 3 |
| H4 | 8 | 600 s | 60.001 | 4 + 4 | 3 |
| **Tổng** | **32** | | **1.920.032 mẫu** | **20 PNG + 20 SVG** | **12 CSV** |

- Source C++ tại I1 SHA-256: `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`.
- NS-3.44 Git commit được ghi trong các môi trường: `43dce6710b8df69685e3479c1d33a571dda714ea`.
- Thông tin build optimized và Git trạng thái sạch được ghi trong metadata. Điều này chứng minh **lịch sử thực thi được ghi**, không phải kiểm tra lại executable trực tiếp từ gói I1 (executable không nằm trong gói).
- 32 `status.json` và `batch_status.json` đều báo PASS; hash của 64 raw CSV khớp trạng thái ghi khi chạy.
- 32 × 60.001 mẫu trace được đọc lại, kiểm tra đúng thời gian, queue không vượt buffer, bộ đếm tích lũy không giảm. Goodput, utilization, trung bình queue và Jain được tính lại từ trace; toàn bộ phù hợp với raw summary.

## 2. Kiểm chứng độc lập đường dữ liệu

Một bản sao độc lập đã được dựng bằng cách giải nén **bốn gói raw gốc**, đặt source và script giống gói I1, sau đó chạy tuần tự `analyze_H1.py`, `analyze_H2.py`, `analyze_H3.py`, `analyze_H4.py` trên bản sao này.

Kết quả: **8/8 AUDIT PASS ở từng nhóm**. Toàn bộ **12 file CSV phân tích tạo lại giống từng byte** các file tương ứng trong gói I1. Điều này xác nhận nhất quán của phép phân tích, không chỉ sự tồn tại của file.

Các PNG/SVG được xuất lại qua Matplotlib có khác biệt byte và kích thước ảnh nhỏ do môi trường render/font. Vì vậy ảnh *không* được tuyên bố trùng hash; tính đúng đắn của biểu đồ được căn cứ vào script đã kiểm toán và số liệu CSV tạo lại trùng khớp. Không chỉnh sửa bất cứ mẫu raw nào.

Script `scripts/audit_I1.py` trong gói kiểm toán cung cấp phép kiểm tra **độc lập, không sửa raw** và tự tạo `results/summary/i1/i1_master_summary.csv` gồm 32 dòng với nguồn hash raw cho mỗi trường hợp.

## 3. Những điều đã xác nhận và giới hạn phải đưa vào báo cáo

**Đã xác nhận:** topology bốn node (hai sender, router, receiver) có bottleneck 500 Mbps; NS-3.44; 600 s mỗi case; 100 Hz sampling; TCP YeAH/NewReno; tham số cấu hình cụ thể có manifest và status; dữ liệu gốc/bảng/hình có thể truy xuất theo ID case.

**Chưa chứng minh:** tái tạo đúng hoàn toàn testbed Linux của paper; thuật toán YeAH trong NS-3 tương đương implementation Linux 2.6.16.2; các kết quả có ý nghĩa thống kê. Mỗi cấu hình chỉ có **1 lần chạy** (`seed=1, run=1`), trong khi paper báo trung bình ≥3 lượt/chỉ số.

**Khác biệt phương pháp:** không có SURGE web cross traffic 4 Mbps; không triển khai Limited Slow Start; NS-3 với MSS 1448 byte và TCP timestamps thay cho testbed Linux truyền gói 1500 byte; Linux vs NS-3, sender socket, mô hình mất gói có thể khác. Hai thuật toán thay cho tập thuật toán rộng hơn. T0 có một luồng tham gia tại 60 s và dừng ứng dụng tại 400 s; **không dùng Jain đo toàn bộ 600 s để kết luận công bằng giữa hai luồng cùng hoạt động**. Goodput/Capacity cũng phải tách biệt với wire utilization.

## 4. Đối chiếu paper sơ bộ: phát hiện cần giải thích trong I2

Bài báo gốc, trang in **40**, Table I “Buffer overflow packet loss probability” công bố:

| RTT | Paper – YeAH | Paper – Reno | NS-3 YeAH – số lần tràn | NS-3 Reno – số lần tràn |
|---:|---|---:|---:|---:|
| 15 ms | Không quan sát thấy gói mất (ký hiệu `–`) | 0,0000057686 | 412 | 736 |
| 60 ms | Không quan sát thấy gói mất (ký hiệu `–`) | 0,0000050669 | 1.968 | 2.508 |
| 240 ms | Không quan sát thấy gói mất (ký hiệu `–`) | 0,0000009400 | 6.581 | 10.003 |

Các số giấy là xác suất **công bố trong paper**, số NS-3 là **đếm sự kiện**, khác đơn vị nên bảng này chỉ phơi bày dữ liệu, **không dùng để tính sai lệch tương đối**. Bước I2 sẽ chuyển số đếm NS-3 thành xác suất theo định nghĩa source: `overflow_drops / (queue_enqueued + overflow_drops)`, rồi kiểm tra tính tương thích của mẫu số đo với paper. Dấu `–` trong paper nghĩa là không quan sát được mất gói trong thí nghiệm, **không có nghĩa xác suất thật bằng 0**.

**Rủi ro phải công khai:** H1 quan sát hàng trăm/hàng nghìn gói tràn ngay cả với YeAH, trong khi paper không quan sát thấy tràn trong Table I. Đây là sai khác thực tế có thể do implementation/môi trường; không được điều chỉnh kết quả để trông giống paper, không được khẳng định một nguyên nhân cụ thể khi chưa chứng minh.

## 5. Tình trạng công việc

- A–G4, H1–H4 và I1: hoàn thành trong phạm vi minh chứng hiện có.
- **I2 – đối chiếu định lượng & giải thích khác biệt:** chưa hoàn thành; bắt buộc làm trước báo cáo.
- J – báo cáo DOCX/PDF, K – đóng gói source/README, L – nộp email + LMS: chưa làm.

**Chính sách chất lượng:** chỉ lấy số liệu thí nghiệm từ raw + script, tách số công bố trong paper; những khác biệt hoặc thông tin thiếu căn cứ luôn có nhãn. Không chạy lại mô phỏng toàn bộ nếu dữ liệu kiểm toán đã hợp lệ.
