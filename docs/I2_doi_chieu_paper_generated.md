# I2 – Đối chiếu bài báo gốc và mô phỏng NS-3.44 (từ dữ liệu đã kiểm toán)

**Trạng thái:** Đây là bảng đối chiếu tự động từ I1 đã khóa; không chạy thêm thí nghiệm.

## Nguồn và giới hạn so sánh
- Paper: A. Baiocchi, A. P. Castellani, F. Vacirca, *YeAH-TCP: Yet Another Highspeed TCP*, PFLDnet 2007, Table I (trang in 40, trang PDF 4); Figure 1, 3, 5, 6, 7 (trang in 39–41).
- NS-3: `results/summary/i1/i1_master_summary.csv`, được tạo bởi `audit_I1.py` từ 32 lượt mô phỏng gốc đã kiểm toán.
- Table I: số giấy báo về Reno là **chính xác**, dấu gạch ngang của YeAH có nghĩa **không phát hiện gói tràn** trong thí nghiệm; không thay bằng tỷ lệ 0 chính xác.
- Chương trình NS-3 đo `overflow_probability = bottleneck_drops/(queue_enqueued+bottleneck_drops)` bằng trace của `DropTailQueue` (kiểm tra từ source). **Chưa chứng minh được mẫu số giống paper**; vì vậy không tính phần trăm sai lệch/nhân tỷ số như thể phép đo hoàn toàn đồng nhất.
- Paper: Linux testbed, 500 Mbps, data packets 1500 bytes, có web cross-traffic SURGE trung bình 4 Mbps, Limited Slow Start, >=3 lần/điểm. NS-3: một seed/run, MSS 1448, không mô phỏng SURGE và Limited Slow Start. Không gọi đây là phép tái hiện chính xác hoàn toàn.

## Table I – Các giá trị paper chính xác và NS-3 tính từ I1

| RTT | TCP | Paper: xác suất tràn | NS-3: xác suất tràn | NS-3: số drop |
|---:|---|---:|---:|---:|
| 15 ms | reno | 0.0000057686 | 2.9483937e-05 | 736 |
| 15 ms | yeah | – (không ghi nhận) | 1.6524463e-05 | 412 |
| 60 ms | reno | 0.0000050669 | 0.000100556606 | 2508 |
| 60 ms | yeah | – (không ghi nhận) | 7.9619261e-05 | 1968 |
| 240 ms | reno | 0.0000009400 | 0.000402808359 | 10003 |
| 240 ms | yeah | – (không ghi nhận) | 0.000265739686 | 6581 |

## Đối chiếu xu hướng các hình (không dựng giá trị số paper từ ảnh)
- **Figure 3:** NS-3 YeAH có queue chuẩn hóa thấp hơn NewReno tại 15, 60, 240 ms: **True**. Paper mô tả YeAH duy trì hàng đợi thấp; mức giảm cụ thể KHÔNG được suy diễn từ nét vẽ.
- **Figure 6:** YeAH NS-3 đi từ 10.1821% (buffer 12,5% BDP) tới 37.1818% (buffer 100% BDP), tăng tại các điểm đo: **True**. Paper mô tả YeAH có xu hướng giảm queue normalized khi buffer tăng; như vậy xu hướng thực nghiệm NS-3 này **không phù hợp với phát biểu định tính đó**, cần phân tích khác biệt mô hình.
- **Figure 7:** YeAH NS-3 có Jain cao hơn NewReno tại tỷ số 2/3/4: **True**. Mỗi tỷ số chỉ có 1 lượt, Jain đo toàn bộ 600s; không khẳng định YeAH luôn RTT-fair hoặc đường cong khớp paper.
- **Figure 5:** 4 so sánh wire utilization YeAH > NewReno theo p tăng dần: **[False, False, False, True]**. Paper cho biết YeAH chịu mất gói độc lập tốt hơn Reno; ở ba trong bốn giá trị đo của NS-3, nhận định về thứ hạng **không khớp**. Không có trị số chính xác của đường Figure 5 nếu chưa số hóa có kiểm chứng.
- **Figure 1:** Chúng ta có T0 với flow2 start=60s, application stop=400s; dữ liệu TCP có thể drain sau stop. Đối chiếu cơ chế động ở mức định tính, không đo đối xứng hoàn toàn khi điều kiện paper không được mô tả đủ chi tiết.

## Những kết luận KHÔNG được rút ra

- Không kết luận thuật toán nào ưu việt trong mọi trường hợp.
- Không gọi 'khớp 100% paper' chỉ vì chương trình đạt 100% audit.
- Không dùng chỉ số Jain toàn thời gian của T0 như độ công bằng trong thời gian hai luồng thực sự hoạt động đồng thời.
- Không chuyển dấu '–' của paper thành 0 như một xác suất chính xác hoặc trích trị số bất kỳ từ đồ thị paper mà không có phương pháp số hóa rõ ràng.
