# NHẬT KÝ THỰC NGHIỆM — YeAH-TCP trên NS-3.44

**Bản 09 — 20/11/2026, cập nhật tái tạo H2 trên WSL và kế hoạch H3**  
Học phần Đánh giá hiệu năng mạng (INT3308) · BTL cá nhân  
Tài liệu làm việc, không phải báo cáo nộp cuối kỳ.

## 0. Quy tắc quản lý dữ liệu

- **XÁC NHẬN:** có bằng chứng xác định được (paper, ảnh, source, log, CSV); ghi rõ phạm vi xác nhận. Kiểm tra nội dung file không đồng nghĩa chạy lại độc lập trên máy sinh viên.
- **CẦN KIỂM CHỨNG:** chưa đủ bằng chứng hoặc cần thí nghiệm đối chứng. **DỰ KIẾN:** cấu hình/giả thuyết/kế hoạch, chưa phải kết quả. **ĐÃ THAY THẾ:** phiên bản cũ không dùng cho kết quả tiếp theo. **CHƯA THỰC HIỆN:** chưa có dữ liệu.
- Không ghi giá trị dự kiến như dữ liệu đo. Giữ nguyên raw CSV và log; tạo bản tổng hợp riêng, ghi công thức, đơn vị, cấu hình, source version, seed/run, cửa sổ đo, số lượt thành công. Không xóa lần chạy lỗi; không trộn pilot với thực nghiệm chính thức. Nếu thay code hoặc cấu hình, dùng ID/đường dẫn mới và ghi lý do.
- Sau mỗi lượt trao đổi: cập nhật trạng thái, mục tiêu, cấu hình, lệnh, file đầu ra, kiểm tra, kết quả, hạn chế, việc tiếp theo. Chỉ viết báo cáo chính thức sau khi khóa bộ dữ liệu và kiểm chứng; tài liệu kế hoạch Word cũ và bản nháp phần 1 là tư liệu làm việc, không phải bản cuối.

## 1. Đề bài và phạm vi

Căn cứ: `Hướng dẫn Bài tập lớn.pptx`, slide 2–5; `4-YeAH_TCP.pdf`, tr. 37–42; thông báo nộp bài do sinh viên cung cấp. Báo cáo nhóm `Bao_cao_5G_Network_Slicing_Wi-Fii.docx` chỉ là mẫu bố cục/cách minh chứng, không phải rubric hoặc dữ liệu của YeAH.

| Yêu cầu | Minh chứng cần có | Hiện trạng |
|---|---|---|
| 1. Ý tưởng chính | Phân tích High BDP, hạn chế Reno, mục tiêu YeAH | Đã phân tích paper, chưa chốt báo cáo |
| 2. Cải tiến/mô hình | Q, L, Fast/Slow, giảm tải, cạnh tranh Reno, giảm cửa sổ khi loss | Đã phân tích và đối chiếu code |
| 3. Cài đặt NS-3 | Mã TcpYeah upstream + C++ testbed, phiên bản và hướng dẫn chạy | Pilot chạy được |
| 4. Kiểm tra tính đúng đắn | Unit test, kiểm thử mô hình, trace, cấu hình, tái lập, kiểm tra loss | Đã xác nhận pilot, tái lập G1 và chức năng G2; G3/G4 đã hoàn thành trong phạm vi kiểm chứng |
| 5. Test và thu kết quả | Batch có log, CSV, metadata, nhiều lượt khi phù hợp | Đã có H1: 8/8 lượt chạy 600 s, mỗi cấu hình 1 lượt; chưa có H2–H5 |
| 6. So sánh paper/nhận xét | Đồ thị, bảng số liệu, sai lệch, giới hạn | Chưa thực hiện chính thức |

Nộp báo cáo và mã nguồn (file hoặc link Git public ghi rõ) qua **cả** email `congdm@vnu.edu.vn` và LMS https://portal.uet.vnu.edu.vn/courses/6990/assignments/96056, trước 00:00 22/11/2026 (hết ngày 21/11). PDF + ZIP là khuyến nghị, không phải định dạng bắt buộc đã xác minh; chưa biết giới hạn upload LMS. Không cần nộp nhật ký/gói trao đổi nguyên bản nếu không được yêu cầu, nhưng giữ minh chứng thiết yếu và lịch sử kỹ thuật trong project.

## 2. A — Phân tích bài báo [XÁC NHẬN từ paper]

- Mục tiêu: kiểm chứng các đặc tính YeAH trên mạng High BDP so với TCP đối chứng, không đặt mục tiêu chứng minh YeAH luôn tốt hơn.
- Paper mục III: RTTqueue = RTTmin − RTTbase; Q = RTTqueue × cwnd/RTTmin (cwnd theo segment); L = RTTqueue/RTTbase. Fast Mode nếu Q < Qmax và L < 1/phi; nếu không thì Slow Mode. Fast tăng theo Scalable TCP, Slow tăng theo Reno. Giảm tải chủ động và bộ đếm cạnh tranh Reno. Khi ba ACK trùng lặp và không cạnh tranh Reno, giảm min(max(cwnd/8,Q),cwnd/2); khi cạnh tranh Reno giảm một nửa.
- Mục IV: testbed vật lý Linux 2.6.16.2 đã sửa; access 1 Gbps, bottleneck 500 Mbps ở các thí nghiệm chính, gói dữ liệu 1500 byte, B = tỷ lệ × C × min(RTT1,RTT2) (đổi đơn vị sang gói); mặc định 600 s, mỗi điểm trung bình ít nhất 3 thí nghiệm; mô tả web cross traffic SURGE trung bình 4 Mbps, Limited Slow Start, cửa sổ nhận lớn. Không khẳng định SURGE có mặt ở từng hình nếu chưa xác định được từ paper.
- Mục V: Fig. 1 quan sát cwnd; Fig. 3/Tab. I RTT và queue/loss; Fig. 4–5 random loss; Fig. 6 buffer; Fig. 7 fairness; Fig. 8 duration. Queue lấy mẫu 100 Hz. Paper báo cáo YeAH có hàng đợi thấp, sử dụng link tốt và fairness tốt trong testbed đã chọn; đây là kết quả tác giả, không phải kết quả BTL.
- Chưa có CSV gốc YeAH hoặc patch Linux được xác minh tải được. Không dùng các điểm ước lượng minh họa trong chat như số liệu chính xác của tác giả. Khi số hóa đồ thị, lưu nguồn hình, cách đọc, sai số/xấp xỉ và bảng riêng.

## 3. B — Môi trường [XÁC NHẬN qua ảnh và terminal người dùng]

- Windows 11; `wsl -l -v` đã hiển thị Ubuntu-20.04 và docker-desktop đều WSL2. Sau đó cài Ubuntu 24.04 LTS song song; ảnh VS Code hiển thị WSL: Ubuntu-24.04; VS Code Server compatibility check thành công. Không cần xóa distro cũ.
- G++ 13.3.0, Python 3.12.3, CMake 3.28.3, Ninja 1.11.1, Git 2.43.0 (ảnh terminal). `nproc` = 12, RAM WSL 7.6 GiB, available 5.9 GiB lúc kiểm tra, swap 2 GiB; dung lượng filesystem ảo hiển thị 953 GiB available, không suy ra dung lượng ổ C vật lý.
- Thư mục: `~/projects/ns-3.44` và `~/projects/YeAH-TCP-NPE`.
- Lệnh đã hướng dẫn: `wsl --install -d Ubuntu-24.04`, `wsl --set-default Ubuntu-24.04`; `sudo apt update`, `sudo apt upgrade -y`, `sudo apt install -y build-essential python3 python3-pip python3-venv cmake ninja-build git gdb ccache`; `mkdir -p ~/projects; cd ~/projects; code .`. Không có log đầy đủ của từng lệnh apt; chỉ xác nhận công cụ hoạt động từ ảnh.
- Cảnh báo WSL PATH ổ D: giả thuyết đường dẫn cũ sau khi gộp ổ D/C, chưa xác minh từng mục PATH; không có bằng chứng gây lỗi mô phỏng. Windows Security cảnh báo file ZIP qua WSL/Internet: không phải chứng cứ nhiễm virus; không thay đổi bảo mật.

## 4. C–D — Cài đặt và kiểm thử upstream [XÁC NHẬN]

Lệnh đã dùng/hướng dẫn (ảnh build và log unit test xác nhận các đầu ra):

```bash
cd ~/projects
git clone --depth 1 --branch ns-3.44 https://gitlab.com/nsnam/ns-3-dev.git ns-3.44
cd ns-3.44
./ns3 configure --enable-examples --enable-tests --enable-modules="core;network;internet;point-to-point;applications;traffic-control;flow-monitor"
./ns3 build -j 4
./ns3 run hello-simulator
./test.py -s tcp-yeah-test
```

- NS-3.44 commit `43dce6710b8df69685e3479c1d33a571dda714ea`; git status trống tại thời điểm xuất bước E. Build 637/637 và Hello Simulator thành công (ảnh). Profile build `default`, ASSERT/LOG ON theo ảnh cấu hình và tên executable trong log.
- Unit test log: `PASS: TestSuite tcp-yeah-test`, `1 of 1 tests passed`; source đăng ký 6 test case (4 kiểm tra tăng cwnd, 2 kiểm tra ssthresh khi loss). Không diễn giải 1/1 suite là sáu lần chạy độc lập hoặc kiểm chứng mọi trường hợp.
- Minh chứng: ảnh terminal build/PASS; `tests/tcp-yeah-unit-test.log` trong gói E. Cần lưu ảnh gốc vào `docs/evidence/` nếu chưa lưu; log đã có.

## 5. E — Đối chiếu source [XÁC NHẬN tĩnh; ảnh hưởng thực nghiệm CẦN KIỂM CHỨNG]

Gói `step-E-source-review.tar.gz` chứa `docs/tcp-yeah-source-review.txt` (VERSION, commit, status, các file có đánh số dòng) và `tests/tcp-yeah-unit-test.log`. Đã mở và kiểm tra trực tiếp. Lệnh xuất source: `nl -ba` cho tcp-yeah.h/.cc, tcp-scalable.h/.cc, tcp-congestion-ops.cc, tcp-yeah-test.cc; `./test.py -s tcp-yeah-test 2>&1 | tee ...`; `tar -czf ~/projects/step-E-source-review.tar.gz docs/tcp-yeah-source-review.txt tests/tcp-yeah-unit-test.log`.

| Paper | Code đúng bản 3.44 | Ghi nhận |
|---|---|---|
| Ngưỡng/heuristic | tcp-yeah.cc:25–74 | Alpha=80, Gamma=1, Delta=3, Epsilon=1, Phy=8, Rho=16, Zeta=50, StcpAiFactor=100 |
| RTT, Q, L | tcp-yeah.cc:138–155, 214–247 | min-filter; đủ hơn 2 mẫu RTT mới tính trong nhánh này |
| Fast/Slow | tcp-yeah.cc:193–212 | Slow Start riêng; STCP hoặc NewReno khi congestion avoidance |
| Điều kiện chuyển | tcp-yeah.cc:250, tcp-yeah.h:158 | `1 / m_phy` là chia nguyên do uint32_t; mặc định 8 cho 0, paper 1/8=0.125; khác cả điều kiện biên > so với mô tả paper |
| Giảm chủ động | tcp-yeah.cc:252–259 | min(Q/Gamma, cwnd >> Epsilon), sàn m_renoCount, ssthresh=cwnd mới; khác mô tả paper |
| Bộ đếm | tcp-yeah.cc:266–291 | reset m_renoCount=2 khi fastCount>Zeta; paper mô tả cwnd/2 |
| Sau loss | tcp-yeah.cc:310–337 | bytesInFlight/MSS, m_lastQ, sàn 2 MSS; không đồng nhất với công thức cwnd paper |

**Điểm audit mới:** tcp-yeah-test.cc dòng 185 cũng dùng `(1 / phy.Get())`; oracle của unit test có cùng biểu thức chia nguyên. PASS không kiểm chứng độc lập rằng ngưỡng phù hợp paper. Chưa có phép chạy với `1.0 / m_phy`. Giữ nguyên upstream làm baseline; nếu thử patch, tạo nhánh/phiên bản riêng, ghi diff và chạy đối chứng cùng cấu hình. Không gọi bản sửa là cải tiến thuật toán mới hay khẳng định tác động nếu chưa có dữ liệu.

## 6. F — Chương trình mô phỏng và pilot [XÁC NHẬN đã chạy]

### F0. Phiên bản

- Bản đầu `step-F-pilot-source.zip`: simulation/yeah-experiment.cc, scripts/run_pilot.sh, docs/source-review-summary.md. Bản C++ này **ĐÃ THAY THẾ**: compile thành công nhưng `tc.Uninstall(a/b/c)` gặp assertion `No root queue disc installed on device`, SIGABRT (6), ở t=0, không có CSV. Minh chứng: log người dùng dán trong chat; đã hướng dẫn sao lưu `tests/pilot-queue-error.log`, chưa nhận file này riêng. Không cần đưa lỗi tự viết này vào báo cáo chính, nhưng giữ nhật ký.
- Bản chạy thành công: `simulation/yeah-experiment.cc` trong gói F. Diff so với bản đầu chỉ thay đoạn Uninstall bằng vòng kiểm tra `GetRootQueueDiscOnDevice` trước khi gỡ. Không chỉnh sửa file thuật toán upstream trong diff này; cần kiểm tra trạng thái thư viện ở G để xác nhận lần chạy tiếp theo.
- Lệnh: `cd ~/projects/YeAH-TCP-NPE; python3 -m zipfile -e step-F-pilot-source.zip .; bash scripts/run_pilot.sh`. Script copy source vào `ns-3.44/scratch/`, chạy từng case bằng `./ns3 run "scratch/yeah-experiment ... --out=..."`, lưu `run.log`, rồi tạo `~/projects/step-F-pilot.tar.gz`.

### F1. Cấu hình chung (đọc từ source phiên bản chạy thành công)

4 node: 0,1 sender → 2 router → 3 receiver; access 1 Gbps, bottleneck cấu hình; FIFO DropTail NetDevice; access queue 20.000 gói; bottleneck queue floor(BDP × bufferRatio), BDP dùng 1500 B; tắt flow control; router bottleneck queue được đo trực tiếp. Bottleneck propagation 1 ms một chiều; access RTT/2 − 1 ms; RTT mục tiêu chỉ là propagation danh nghĩa, không gồm serialization/queue/ACK delay. BulkSend không giới hạn, 2 PacketSink, MSS 1448 byte, MTU 1500, timestamp/SACK/window scaling bật, DelAckCount=2, send/receive buffer 64 MiB, InitialCwnd=10 segment, ssthresh ban đầu UINT32_MAX (giá trị cấu hình CSV=0). Hai luồng cùng chạy từ t=1 đến 1+duration, cửa sổ đo toàn duration. Lấy mẫu 10 ms. Seed=1, run=1, bufferRatio=1, loss=0. Không có SURGE hoặc Limited Slow Start như paper. Đường lỗi packet ngẫu nhiên có code nhưng chưa kích hoạt. CUBIC, H-TCP, HighSpeed có tùy chọn CLI nhưng chưa chạy.

| ID | TCP1/TCP2 | C (Mbps) | RTT1/2 (ms) | B (gói) | duration (s) | seed/run |
|---|---|---:|---|---:|---:|---|
| yeah50 | YeAH/YeAH | 50 | 80/80 | 333 | 20 | 1/1 |
| reno50 | NewReno/NewReno | 50 | 80/80 | 333 | 20 | 1/1 |
| yeah500 | YeAH/YeAH | 500 | 80/80 | 3333 | 15 | 1/1 |

Lệnh tương ứng (chạy ở `~/projects/ns-3.44`, OUT là thư mục ID):

```bash
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=50 --rtt1=80 --rtt2=80 --duration=20 --out=$OUT"
./ns3 run "scratch/yeah-experiment --tcp1=reno --tcp2=reno --capacity=50 --rtt1=80 --rtt2=80 --duration=20 --out=$OUT"
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=500 --rtt1=80 --rtt2=80 --duration=15 --out=$OUT"
```

### F2. Kết quả thực tế (summary.csv, tính lại từ timeseries.csv)

| Chỉ số | yeah50 | reno50 | yeah500 |
|---|---:|---:|---:|
| RX1 bytes | 54123344 | 60597352 | 324288288 |
| RX2 bytes | 58310960 | 56670376 | 216878544 |
| Goodput 1 (Mbps) | 21.6493376 | 24.2389408 | 172.9537536 |
| Goodput 2 (Mbps) | 23.3243840 | 22.6681504 | 115.6685568 |
| Tổng goodput (Mbps) | 44.9737216 | 46.9070912 | 288.6223104 |
| Goodput/C (%) | 89.9474432 | 93.8141824 | 57.7244621 |
| Wire utilization (%) | 93.3092256 | 97.3189648 | 59.8840830 |
| Queue trung bình (gói) | 109.235 | 219.165 | 65.3786667 |
| Queue/B (%) | 32.8033033 | 65.8153153 | 1.9615562 |
| Queue max sampled (gói) | 333 | 333 | 3134 |
| Queue samples dùng tính TB | 2000 | 2000 | 1500 |
| Số dòng timeseries (không header) | 2001 | 2001 | 1501 |
| Queue enqueued | 77775 | 81283 | 373781 |
| Bottleneck drops | 758 | 337 | 0 |
| Overflow ratio (drop/(enqueued+drop)) | 0.0096519934 | 0.0041288900 | 0 |
| Other drops / random drops | 0/0 | 0/0 | 0/0 |
| Jain index | 0.9986147314 | 0.9988798589 | 0.9620994941 |
| Min RTT trace 1/2 (ms) | 80/80 | 80/80 | 80/80 |
| Max wire packet (byte) | 1502 | 1502 | 1502 |
| Wall time thực tế (s) | 13.171 | 2.308 | 25.785 |

Wall time yeah50 gồm build lại; hai case kia log ninja no work to do. Không dùng các số này như benchmark ổn định hoặc runtime so sánh thuật toán. 1502 byte là trace PHY có overhead PPP; BDP dùng 1500 byte IP danh nghĩa.

### F3. Kiểm tra lại file đã nhận

- 3/3 case có summary.csv, timeseries.csv, run.log; log đúng SocketType và ghi Saved. Source kèm gói.
- Tính lại goodput từ byte nhận cuối/ duration, wire utilization từ wire bytes cuối / capacity × duration, Jain từ goodput hai luồng; tất cả khớp summary trong sai số làm tròn. Queue mean/max tính từ mẫu `time_s < duration`; tất cả khớp. Mẫu cuối là mốc kết thúc, không đưa vào trung bình. Các mốc cách 0.01 s, bắt đầu 0, kết thúc đúng duration. RX, wire bytes và drop counter không giảm. RX/drop cuối khớp summary. Queue sampled không vượt cap; wire utilization ≤ 1; trace RTT/cwnd có sự kiện; không thấy drop ngoài bottleneck.
- Công thức: goodput Mbps = 8 × payload bytes / (T × 10^6); wire utilization = 8 × PHY bytes / (C × T), C bit/s; queue/B = mean sampled queue/B; overflow ratio = overflow/(accepted+overflow); Jain = (g1+g2)^2/[2(g1²+g2²)]. Phân biệt goodput/C và wire utilization; paper chưa cung cấp đủ chi tiết đếm byte để khẳng định efficiency của họ trùng định nghĩa nào.
- Phạm vi xác nhận ở thời điểm F: tính nhất quán nội bộ file và smoke test; việc chạy lại cùng seed/run đã được xác nhận ở G1 (mục 7); chưa xác nhận toàn bộ mô hình hoặc so sánh chính thức paper. Min RTT trace khớp mục tiêu trong pilot nhưng không đồng nhất với RTTmin nội bộ YeAH.
- Nhận xét sơ bộ: tại 50 Mbps/80 ms/20 s, YeAH queue thấp hơn Reno nhưng goodput thấp hơn và overflow cao hơn; không kết luận ưu thế toàn diện. Tại 500 Mbps/80 ms/15 s, wire utilization chỉ 59.88%; cần đánh giá thời lượng/khởi động và các yếu tố khác, chưa kết luận nguyên nhân. Một run/case, chưa có thống kê biến thiên. Zero drop tại yeah500 không đồng nghĩa xác suất mất gói bằng 0 trong mọi kịch bản.

### F4. Điểm kỹ thuật còn mở

- Mô hình đơn giản hóa so với testbed gốc: Linux TCP 2007 vs NS-3.44, không Limited Slow Start/SURGE, khác tham số/implementation, PPP overhead, chưa đủ 600 s và 3 lượt mỗi điểm.
- Counter queue/drop không lọc theo start/end trong callback; hiện mô phỏng kết thúc gần end, cần rà lại biên cửa sổ khi thay lịch flow. WireTx đo theo [start,end), sink lấy byte tại cuối; lưu định nghĩa rõ. Queue sample max không phải max liên tục.
- `flow2Stop` dừng BulkSend nhưng TCP có thể tiếp tục truyền dữ liệu đã đệm. T0 cần xác minh goodput theo từng khoảng, thời điểm thực sự ngừng truyền, không diễn giải Jain toàn khoảng như fairness khi hai luồng đồng thời. Chưa có trace trực tiếp Q nội bộ hoặc mode, không suy ra mode chỉ từ cwnd.
- Random error model chỉ ở chiều forward receiver. Tại thời điểm F chưa kiểm thử loss>0; G2 đã kiểm thử (xem mục 7).

## 7. G — Kiểm chứng chương trình [ĐÃ HOÀN THÀNH TRONG PHẠM VI G1–G4]

### G1 — Tái lập pilot và kiểm tra độ nhạy thời lượng [XÁC NHẬN]

**Mục tiêu:** G1-01 chạy lại yeah50 cùng cấu hình; G1-02 tăng duration từ 15 lên 60 s tại 500 Mbps. Giữ nguyên mã nguồn F, không chỉnh sửa TcpYeah. Gói nhận được: `step-G1-validation.tar.gz`, đầy đủ `simulation/yeah-experiment.cc`, `results/raw/validation/g1/environment.log` và 2 bộ summary.csv, timeseries.csv, run.log. `environment.log` ghi NS-3.44, commit `43dce6710b8df69685e3479c1d33a571dda714ea`, git status và diff src/internet không có nội dung; hash scratch trùng source trong gói F và G1. Đây là bằng chứng từ log nhận được, không phải kiểm tra trực tiếp máy sinh viên.

**Lệnh đã dùng theo hướng dẫn** (chạy tại ns-3.44, sau khi copy source F vào scratch; OUT=`$HOME/projects/YeAH-TCP-NPE/results/raw/validation/g1`):

```bash
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=50 --rtt1=80 --rtt2=80 --duration=20 --seed=1 --run=1 --out=$OUT/replay-yeah50"
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=500 --rtt1=80 --rtt2=80 --duration=60 --seed=1 --run=1 --out=$OUT/yeah500-60s"
```

**Cấu hình xác nhận từ summary và log:** 2 luồng YeAH; access 1 Gbps, RTT danh nghĩa 80/80 ms, bufferRatio=1, loss=0, seed/run=1/1, MSS=1448, InitialCwnd=10, initialSsthreshSegments=0 (UINT32_MAX), flow2Start=0, flow2Stop=duration. Buffer G1-01=333; G1-02=3333 gói.

| Độ đo | G1-01 replay-yeah50 | G1-02 yeah500-60s |
|---|---:|---:|
| Duration (s) | 20 | 60 |
| RX1 bytes | 54123344 | 1476128848 |
| RX2 bytes | 58310960 | 976958360 |
| Goodput 1 (Mbps) | 21.6493376 | 196.8171797333 |
| Goodput 2 (Mbps) | 23.3243840 | 130.2611146667 |
| Tổng goodput (Mbps) | 44.9737216 | 327.0782944 |
| Goodput/C (%) | 89.9474432 | 65.41565888 |
| Wire bytes | 116636532 | 2544634552 |
| Wire utilization (%) | 93.3092256 | 67.8569213867 |
| Queue mean (gói) | 109.235 | 16.660 |
| Queue/B (%) | 32.8033033 | 0.49984998 |
| Queue max sampled (gói) | 333 | 3134 |
| Queue samples dùng tính TB | 2000 | 6000 |
| Queue enqueued | 77775 | 1694169 |
| Overflow drops | 758 | 0 |
| Other drops / random drops | 0/0 | 0/0 |
| Wire packets | 77658 | 1694168 |
| Jain | 0.9986147314 | 0.9602395390 |
| Min RTT trace (ms) | 80/80 | 80/80 |
| Wall time (s) | 6.094 (có build) | 109.394 (ninja no work) |

**Audit trực tiếp trên file:** 2/2 case log đúng SocketType và Saved. Tính lại goodput, wire utilization, Jain, queue mean/max từ CSV khớp trong sai số làm tròn. Mẫu 10 ms, 2001 và 6001 dòng dữ liệu (gồm mẫu cuối). Tính queue mean/max với time < duration. Bộ đếm RX/wire/drop không giảm; queue sampled không vượt buffer. So sánh byte trực tiếp G1-01 với F/yeah50: summary.csv (974 byte), timeseries.csv (212051 byte) đều giống hệt. SHA-256 tương ứng: `ccd4cbccb58c009732edd8449ace3a1e6fd3f7cf25bd208fd657821468f0f71d` và `c4dd01a55ff027c9b2024ecd5c8100f7343deaa168c3317f849bd760b3c3da89`. Toàn bộ file timeseries F/yeah500 (header + 1501 mẫu 0–15 s) cũng là tiền tố trùng byte của G1-02.

**G1-02 theo cửa sổ 15 s** (lấy chênh lệch bộ đếm byte ở hai mốc, chia 15 s; queue mean từ mẫu thuộc [a,b)):

| Khoảng (s) | Tổng goodput (Mbps) | Wire utilization (%) | Queue mean (gói) |
|---|---:|---:|---:|
| 0–15 | 288.6223104 | 59.8840830 | 65.3786667 |
| 15–30 | 318.4472491 | 66.0644486 | 0.370 |
| 30–45 | 339.0343339 | 70.3288469 | 0.424 |
| 45–60 | 362.2092843 | 75.1503070 | 0.4673333 |

**Nhận xét sơ bộ:** G1-01 xác nhận tái lập cùng cấu hình/seed/run; không chứng minh đúng tuyệt đối hay khớp paper. G1-02 tăng goodput và wire utilization so với 15 s; ngay khoảng cuối vẫn chưa đạt 100% và diễn biến còn tăng, chưa xác nhận trạng thái ổn định. Queue thấp và zero drop không chứng minh hiệu năng tối ưu. Chưa xác định nguyên nhân (thời lượng, khác biệt implementation, yếu tố khác); cần đối chứng. Wall time 109.394 s là một phép đo thực tế cho 60 s mô phỏng, không phải thời gian chạy 600 s hay benchmark nhiều thuật toán. Pilot 15 s vẫn hợp lệ cho cấu hình cũ, không bị thay thế; G1-02 là dữ liệu bổ sung. Cả G1 vẫn là kiểm chứng, không gộp vào H như dữ liệu chính thức.

### G2 — Kiểm tra chức năng còn thiếu [XÁC NHẬN trong phạm vi kiểm thử]

**Mục tiêu:** xác minh mixed TCP, error model, CUBIC và RTT bất đối xứng. Gói nhận được `step-G2-validation.tar.gz`: đầy đủ source, environment.log, 3 bộ summary.csv, timeseries.csv, run.log. Log môi trường ghi NS-3.44, commit `43dce6710b8df69685e3479c1d33a571dda714ea`; git status và diff src/internet trống; source hash trùng F/G1. Không có bằng chứng sửa upstream. Đây là kiểm tra file gửi, không phải truy cập trực tiếp máy sinh viên.

**Cấu hình xác nhận:** 2 luồng, capacity=50 Mbps, bufferRatio=1, seed/run=1/1, MSS=1448, initialCwnd=10, initialSsthreshSegments=0 (UINT32_MAX), access=1 Gbps theo source. Loss ở chiều forward receiver, packet error unit, stream=17 theo source.

| ID | TCP1/2 | RTT1/2 (ms) | Duration (s) | Buffer (gói) | Loss | Flow2 start/stop (s, tương đối) |
|---|---|---|---:|---:|---:|---|
| mixed-50 | yeah/reno | 80/80 | 60 | 333 | 0 | 10/30 |
| loss-50 | yeah/yeah | 80/80 | 20 | 333 | 0.001 | 0/20 |
| cubic-asym-50 | cubic/cubic | 25/100 | 20 | 104 | 0 | 0/20 |

**Lệnh theo hướng dẫn đã thực hiện** (tại ns-3.44, copy source vào scratch, OUT=`$HOME/projects/YeAH-TCP-NPE/results/raw/validation/g2`):

```bash
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=reno --capacity=50 --rtt1=80 --rtt2=80 --duration=60 --flow2Start=10 --flow2Stop=30 --seed=1 --run=1 --out=$OUT/mixed-50"
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=50 --rtt1=80 --rtt2=80 --duration=20 --loss=0.001 --seed=1 --run=1 --out=$OUT/loss-50"
./ns3 run "scratch/yeah-experiment --tcp1=cubic --tcp2=cubic --capacity=50 --rtt1=25 --rtt2=100 --duration=20 --seed=1 --run=1 --out=$OUT/cubic-asym-50"
```

**Kết quả xác nhận từ CSV/log:**

| Độ đo | mixed-50 | loss-50 | cubic-asym-50 |
|---|---:|---:|---:|
| RX1 bytes | 181306976 | 18016016 | 108068584 |
| RX2 bytes | 147024128 | 12533888 | 8533064 |
| Goodput 1 (Mbps) | 24.1742634667 | 7.2064064 | 43.2274336 |
| Goodput 2 (Mbps) | 19.6032170667 | 5.0135552 | 3.4132256 |
| Tổng goodput (Mbps) | 43.7774805333 | 12.2199616 | 46.6406592 |
| Goodput/C (%) | 87.55496107 | 24.43992320 | 93.28131840 |
| Wire bytes | 340584786 | 31726970 | 120959288 |
| Wire utilization (%) | 90.82260960 | 25.38157600 | 96.76743040 |
| Queue mean (gói) | 139.3921666667 | 7.408 | 69.504 |
| Queue/B (%) | 41.85950951 | 2.22462462 | 66.83076923 |
| Queue max sampled | 333 | 333 | 104 |
| Queue samples dùng tính TB | 6000 | 2000 | 2000 |
| Queue enqueued | 226759 | 21127 | 80630 |
| Overflow drops | 326 | 72 | 288 |
| Overflow/(accepted+overflow) | 0.0014355858 | 0.0033963866 | 0.0035591587 |
| Other drops | 0 | 0 | 0 |
| Random drops | 0 | 25 | 0 |
| Wire packets | 226759 | 21127 | 80536 |
| Jain (toàn cửa sổ) | 0.9892149932 | 0.9688029106 | 0.5784704747 |
| Cwnd events 1/2 | 62191/50534 | 6012/4092 | 995/311 |
| RTT events 1/2 | 62009/50002 | 5543/3668 | 35370/2836 |
| Min RTT trace (ms) | 80/80 | 80/80 | 25/100 |
| Wall time (s) | 14.495 (có build) | 1.509 | 5.218 |

**Audit:** 3/3 log đúng SocketType và Saved; 6001/2001/2001 dòng mẫu gồm mốc cuối, interval 10 ms. Tính lại goodput từ byte nhận cuối, wire utilization từ wire_bytes, Jain, queue mean/max (time < duration), bộ đếm drop từ timeseries khớp summary trong độ chính xác làm tròn. Bộ đếm RX/wire/drop không giảm, sampled queue không vượt buffer. Overflow ratio là số drop/attempt enqueue, không phải xác suất loss toàn tuyến. G2 không thay thế F/G1, vẫn là kiểm thử, không gộp với H.

**Mixed-50:** Dùng chênh lệch RX tại hai mốc, chia độ dài cửa sổ. Queue mean từ [a,b).

| Khoảng (s) | Goodput YeAH (Mbps) | Goodput Reno (Mbps) | Queue mean (gói) |
|---|---:|---:|---:|
| 0–10 | 31.0231104 | 0 | 17.084 |
| 10–20 | 16.1504128 | 31.4806784 | 132.559 |
| 20–30 | 15.621024 | 32.5811584 | 208.074 |
| 30–40 | 16.6994944 | 31.5038464 | 270.812 |
| 40–50 | 23.5954496 | 22.0536192 | 207.190 |
| 50–60 | 41.9560896 | 0 | 0.634 |

RX2 bắt đầu tăng ở mẫu 10.13 s, cuối cùng tăng ở mẫu 47.73 s; sau mốc app stop=30 s, nhận thêm 66,946,832 bytes (~63.85 MiB). Source cấu hình send buffer 64 MiB, phù hợp với giả thuyết drain; chưa đo trực tiếp nội dung send buffer hay TCP close event. Mốc RX cuối là mốc quan sát dữ liệu tại sink, không chứng minh toàn bộ packet/ACK đã ngừng. Với T0, đánh dấu cả mốc app stop và mốc RX2 cuối, chọn khoảng sau drain để nhận xét, không diễn giải flow2Stop là ngắt TCP tức thì. Không dùng Jain toàn 60 s làm fairness trong giai đoạn cùng hoạt động. Không bắt buộc giảm send buffer hay sửa TCP tại thời điểm này.

**Loss-50:** 25 random drops và 72 overflow drops; no-loss cases đều random drops=0. 25/21127 ≈ 0.00118332 là tỷ số random drop trên số gói bắt đầu truyền qua bottleneck (mẫu số không phải số phép thử RX chính xác, có thể còn packet in flight). Xác nhận chức năng sinh lỗi, không xác nhận phân bố hay giá trị xác suất chính xác chỉ từ một lần chạy. p=0.001 là mức test chức năng, không phải điểm chính thức Fig.4–5.

**Cubic-asym-50:** log xác nhận TcpCubic hai luồng, min RTT trace=25/100 ms; goodput không đều trong một lần chạy 20 s. Không suy rộng thành kết luận về fairness của CUBIC hay YeAH. G2 đạt mục tiêu chức năng; còn hạn chế T0 drain cần xử lý khi phân tích, không chặn chạy benchmark.

### G3 — Benchmark [XÁC NHẬN]

Giữ nguyên source F/G1/G2 và build hiện tại (chưa đổi sang optimized). Hai case 500 Mbps, RTT 80/80 ms, B/BDP=1 (3333 gói), duration=180 s, hai luồng cùng chạy từ 0 đến 180 s, p=0, seed/run=1/1, MSS=1448, initialCwnd=10, initialSsthreshSegments=0. G3-01 yeah180 (YeAH/YeAH), G3-02 reno180 (NewReno/NewReno). Đây là benchmark kiểm chứng do lựa chọn nội bộ, không phải kết quả H, không thay thế 600 s trong paper. 180 s được chọn để quan sát dài hơn G1 và có dữ liệu thời gian chạy hai TCP chính. Không tự suy ra thời gian 600 s hay trạng thái ổn định từ duration 180 s.

Lệnh đã hướng dẫn, cấu hình xác nhận từ CSV (OUT=`$HOME/projects/YeAH-TCP-NPE/results/raw/validation/g3`, sau copy source vào scratch):

```bash
./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --flows=2 --capacity=500 --rtt1=80 --rtt2=80 --bufferRatio=1 --duration=180 --loss=0 --flow2Start=0 --flow2Stop=180 --seed=1 --run=1 --mss=1448 --initialCwnd=10 --initialSsthreshSegments=0 --out=$OUT/yeah180"
./ns3 run "scratch/yeah-experiment --tcp1=reno --tcp2=reno --flows=2 --capacity=500 --rtt1=80 --rtt2=80 --bufferRatio=1 --duration=180 --loss=0 --flow2Start=0 --flow2Stop=180 --seed=1 --run=1 --mss=1448 --initialCwnd=10 --initialSsthreshSegments=0 --out=$OUT/reno180"
```

Đầu ra `step-G3-benchmark.tar.gz`: source, environment.log (version/commit/diff/hash/build type nếu có), 2 bộ CSV/log. Audit lại số liệu, so sánh 60 s đầu của yeah180 với G1-02, phân tích từng cửa sổ 30 s; thời gian wall log theo TCP; không đặt tiêu chí YeAH phải thắng. Sau đó mới chốt số lượt, duration và mức tham số cho H, ưu tiên T0/T1/T2, T3/T4 nếu khả thi; giữ rõ các giới hạn so với paper. Nếu tối ưu build hoặc patch upstream sau này, phải ghi phiên bản mới và kiểm chứng lại; không ghi đè baseline.

**Kết quả G3 (đã kiểm tra trực tiếp archive):** source SHA-256 trùng F/G1/G2; môi trường 3.44, commit không đổi, git status và diff src/internet trống; `CMAKE_BUILD_TYPE:STRING=default`. Hai log đúng SocketType và Saved, không ghi nhận lỗi. Cả hai có 18.001 mẫu gồm mốc cuối, 18.000 mẫu tính queue, bước 10 ms. Bộ đếm RX/wire/drop không giảm. Tính lại goodput, wire utilization, queue mean/max, Jain từ CSV khớp summary (sai số làm tròn). Queue không vượt buffer.

| Chỉ số | yeah180 | reno180 |
|---|---:|---:|
| RX1 bytes | 5467361296 | 5573893552 |
| RX2 bytes | 3801228784 | 5212374288 |
| Goodput 1 Mbps | 242.9938353778 | 247.7286023111 |
| Goodput 2 Mbps | 168.9435015111 | 231.6610794667 |
| Tổng goodput Mbps | 411.9373368889 | 479.3896817778 |
| Goodput/C % | 82.38746738 | 95.87793636 |
| Wire bytes | 9614306730 | 11188582970 |
| Wire utilization % | 85.46050427 | 99.45407084 |
| Queue mean | 68.4623333333 | 1774.7419444444 |
| Queue/B % | 2.05407541 | 53.24758309 |
| Queue max sampled | 3134 | 3333 |
| Queue enqueued | 6401493 | 7450012 |
| Overflow drops | 0 | 3336 |
| Overflow probability | 0 | 0.0004475841 |
| Other / random drops | 0 / 0 | 0 / 0 |
| Wire packets | 6401007 | 7449127 |
| Jain | 0.9686974384 | 0.9988778966 |
| Min RTT trace ms | 80/80 | 80/80 |
| Wall time s | 547.065 (có build) | 1288.201 (không build) |

**Phân tích cửa sổ 30 s**, goodput từng luồng từ chênh lệch RX, wire utilization từ chênh lệch wire bytes, queue mean lấy [a,b), drops từ chênh lệch bộ đếm. Các tỷ số wire gần hoặc hơi trên 100% ở cửa sổ nhỏ do quy ước đếm cả packet tại thời điểm bắt đầu truyền, không phải vượt dung lượng vật lý.

| Khoảng s | YeAH GP1 | GP2 | Wire % | Queue | Drops | Reno GP1 | GP2 | Wire % | Queue | Drops |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0–30 | 182.345675 | 121.189105 | 62.974266 | 32.874333 | 0 | 240.915151 | 225.303780 | 96.724566 | 1794.883000 | 3333 |
| 30–60 | 211.288685 | 139.333124 | 72.739577 | 0.445667 | 0 | 249.194622 | 232.829519 | 99.999956 | 2283.199333 | 0 |
| 60–90 | 240.318189 | 158.810462 | 82.802657 | 0.524333 | 0 | 249.002327 | 233.021427 | 100.000036 | 2714.263000 | 0 |
| 90–120 | 273.658871 | 180.632015 | 94.246535 | 0.946000 | 0 | 249.222423 | 232.800945 | 99.999876 | 2950.287333 | 3 |
| 120–150 | 282.778955 | 199.245186 | 99.999956 | 100.581333 | 0 | 249.053297 | 232.970844 | 99.999956 | 237.379333 | 0 |
| 150–180 | 267.572638 | 214.451117 | 100.000036 | 275.402333 | 0 | 248.983793 | 233.039962 | 100.000036 | 668.439667 | 0 |

GP Mbps; queue gói. 6001 mẫu đầu (0–60 s) của yeah180 khớp toàn bộ 14 cột với G1-02 khi đọc CSV. Kết quả xác nhận thời lượng ảnh hưởng mạnh tới goodput/utilization trung bình: YeAH gần 100% wire trong hai khoảng cuối ở cấu hình này, nhưng queue thay đổi, chưa chứng minh trạng thái ổn định hay đủ 180 s cho RTT khác. Reno khai thác link nhanh hơn trong case này; YeAH có queue thấp và không ghi nhận overflow; không suy rộng ra toàn bộ các cấu hình. Không chứng minh nguyên nhân phép chia nguyên từ benchmark. Ảnh top trước đó xác nhận PID đang R, CPU 91.1%, không dùng thay CSV/log. G3 không thay thế pilot, không gộp H.

**Quyết định:** tổng wall time hai case khoảng 30 phút 35 giây (YeAH có build), nên chạy lặp 600 s tuần tự nhiều điểm có rủi ro thời gian. Chưa ngoại suy tốc độ chính xác. Giữ mục tiêu 500 Mbps và ưu tiên 600 s cho các thí nghiệm chính nếu khả thi; chốt phạm vi sau G4. Không sửa TcpYeah.

### G4 — Kiểm chứng build optimized [XÁC NHẬN]

Căn cứ hướng dẫn NS-3.44: https://www2.nsnam.org/docs/release/3.44/tutorial/html/getting-started.html mục 4.4.3.3 và 4.6.4; https://www2.nsnam.org/docs/release/3.44/manual/html/working-with-cmake.html mục 4.3.6. Profile optimized có cấu hình compiler khác và tắt log/assert mặc định; không giả định kết quả giống trước khi kiểm tra. Giữ build cũ và raw cũ, không clean, dùng `--out=build/optimized`, cùng module/source/commit; build target `scratch_yeah-experiment` bằng `cmake --build cmake-cache -j 4 --target scratch_yeah-experiment`. Script `scripts/run_G4_optimized.sh` lưu configure/build/environment/run.log, chạy `./ns3 run "scratch/yeah-experiment ..." --no-build`, không chạy song song trong benchmark để đo thời gian riêng. Kiểm tra SHA nguồn, commit, diff trước build.

| Case | Cấu hình | Đối chiếu |
|---|---|---|
| yeah60 | YeAH×2, 500 Mbps, RTT 80/80, B/BDP=1, 60 s, p=0, seed/run=1/1 | G1 yeah500-60s toàn bộ CSV, G3 prefix |
| reno60 | NewReno×2, cấu hình như trên | G3 reno180 prefix 0–60 s; không so summary 180 s trực tiếp |
| loss50 | YeAH×2, 50 Mbps, RTT 80/80, B/BDP=1, 20 s, p=0.001, seed/run=1/1 | G2 loss-50 toàn bộ CSV |

Tiêu chí: đúng profile/commit/source, 3/3 chạy thành công, so sánh các trace và counter; nếu sai khác, ghi rõ và xác định nguyên nhân trước H. Thời gian đo từ run.log, không tính build. Phần dưới ghi kết quả thực tế G4; đoạn trên là thiết kế kiểm chứng trước khi chạy. Đầu ra `step-G4-optimized.tar.gz`. Điều kiện trước G4: nếu parity đạt, có thể dùng optimized cho H và chạy tối đa 2–3 case độc lập cùng lúc; không chạy build/config đồng thời. Nếu chưa đạt, giữ default hoặc điều tra khác biệt. Quyết định thực tế xem dưới.

**Kết quả G4 (đã xác nhận từ archive gốc):** archive `step-G4-optimized.tar.gz`; script trong gói khớp SHA của script đã cung cấp. `environment.log` ghi version 3.44, commit 43dce6710b8df69685e3479c1d33a571dda714ea, source SHA trùng F/G1/G2/G3; build type release, NS3_ASSERT=OFF, NS3_LOG=OFF, NS3_NATIVE_OPTIMIZATIONS=ON, NS3_OUTPUT_DIRECTORY=build/optimized. Configure 35.3 s; build target 356/356 thành công, wall 154.199 s. Log không ghi diff src; executable `build/optimized/scratch/ns3.44-yeah-experiment-optimized` SHA-256 `91c1b8ddc4460d79f1d95855a7692dc67b6c29ae0e50f4bdae319ba6a3775590`. 12 CPU logic; available RAM 6.4 GiB tại thời điểm log. Dung lượng đĩa WSL không phải xác nhận dung lượng ổ vật lý Windows.

| Chỉ số | yeah60 | reno60 | loss50 |
|---|---:|---:|---:|
| Goodput 1 Mbps | 196.8171797333 | 245.0548864000 | 7.2064064000 |
| Goodput 2 Mbps | 130.2611146667 | 229.0666496000 | 5.0135552000 |
| Tổng goodput Mbps | 327.0782944000 | 474.1215360000 | 12.2199616000 |
| Goodput/C % | 65.41565888 | 94.82430720 | 24.43992320 |
| Wire utilization % | 67.85692139 | 98.36226101 | 25.38157600 |
| Queue mean | 16.6600000000 | 2039.0411666667 | 7.4080000000 |
| Queue/B % | 0.49984998 | 61.17735274 | 2.22462462 |
| Queue max sampled | 3134 | 3333 | 333 |
| Overflow drops | 0 | 3333 | 72 |
| Other drops | 0 | 0 | 0 |
| Random drops | 0 | 0 | 25 |
| Jain | 0.9602395390 | 0.9988641311 | 0.9688029106 |
| Mẫu timeseries | 6001 | 6001 | 2001 |
| Wall seconds | 48.440 | 197.952 | 0.519 |

Kiểm tra lại goodput, wire utilization, queue mean/normalized, Jain từ CSV: khớp summary trong sai số làm tròn; counter không giảm, queue không vượt buffer. `yeah60` summary và timeseries giống từng byte G1 `yeah500-60s`; `loss50` giống từng byte G2 `loss-50`; `reno60` giống header và 6001 dòng đầu G3 `reno180` (14 cột), không so summary khác thời lượng. Tăng tốc quan sát: 109.394/48.440 ≈ 2.26 lần (YeAH 60 s), 1.509/0.519 ≈ 2.91 lần (loss50). Không tính tỷ số Reno do không có default 60 s độc lập. Không coi timing là benchmark kiểm soát mọi yếu tố; wrapper/build overhead và tải máy có thể khác. G4 xác nhận parity ở đúng 3 case, không chứng minh mọi cấu hình đều giống nhau.

**Quyết định:** dùng optimized cho H, không đổi source/thuật toán. Giữ tất cả dữ liệu default và G4 như dữ liệu kiểm chứng; không gộp H. Cấu hình H1 ở mục 8.

## 8. H–I — Ma trận thực nghiệm (H1 đã chạy và kiểm chứng, H2–H5 chưa triển khai)

| ID | Paper | Cấu hình gốc (C=500 Mbps) | Độ đo | Ưu tiên nội bộ |
|---|---|---|---|---|
| T0 | Fig. 1 | YeAH/YeAH và YeAH/Reno, flow 2 vào/rời, điều kiện cụ thể cần chốt | cwnd theo segment, queue, goodput từng khoảng | Trọng tâm |
| T1 | Fig. 3, Table I | RTT bằng nhau 15,30,60,120,240,480 ms; B=BDP; p=0 | Queue/B, utilization, overflow ratio | Trọng tâm |
| T2 | Fig. 6 | RTT=80 ms; B/BDP=0.125,0.25,0.5,1; p=0 | Queue/B, utilization | Trọng tâm |
| T3 | Fig. 7 | RTT1=25 ms; RTT2=25,50,75,100 ms; B=BDP | Jain, goodput từng luồng | Cao |
| T4 | Fig. 4–5 | Fig.4 RTT như T1, p=5e-7; Fig.5 RTT=200 ms, p=1e-8…1e-4 | Efficiency, random drops | Cao |
| T5 | Fig. 8 | RTT=480 ms, B=BDP, p=0; 100–1800 s, initial ssthresh lớn hoặc 2 segment | Efficiency | Mở rộng |

YeAH và NewReno là đối chứng tối thiểu dự kiến, CUBIC nếu khả thi. Paper có thêm Compound, Africa, H-TCP, HS-TCP; nếu giảm số TCP/mức/lượt, ghi rõ giới hạn, chưa có xác nhận thầy cho phép bỏ thí nghiệm. Mặc định hướng tới 600 s, ≥3 lượt/điểm như paper; nếu mô hình không có biến ngẫu nhiên hữu hiệu, seed/run khác nhau có thể cho kết quả giống nhau, không xem đó là mẫu độc lập giả tạo. Đo cả xu hướng và mức sai lệch, không ép khớp paper. Đối chiếu thông số và phạm vi trước khi gọi là tái hiện.

### H1 — T0 và ba điểm RTT dự kiến đối chiếu Table I [ĐÃ CHẠY, dữ liệu chi tiết tại mục 11]

Chọn 8 case, 600 s/case, 500 Mbps, B/BDP=1, p=0, MSS=1448, initial cwnd=10, ssthreshSegments=0, seed/run=1/1, hai luồng. T0 chọn RTT 80 ms dựa trên G3, thời điểm 60/400 s đọc xấp xỉ từ Fig. 1; không khẳng định RTT/buffer chính xác của Fig. 1. T0 dừng ứng dụng ở 400 s, dữ liệu đã đệm có thể drain sau đó; phân tích từ RX theo thời gian, Jain trong cửa sổ hai luồng cùng hoạt động, không dùng Jain toàn phiên làm fairness cạnh tranh. T1 chọn 15/60/240 ms vì có số liệu overflow Table I và thuộc Fig. 3; chưa chạy 30/120/480 ms.

| Case ID | TCP 1/2 | RTT 1/2 ms | Buffer packets | Start/stop app 2 (s) |
|---|---|---|---:|---|
| t0-yeah-yeah | YeAH/YeAH | 80/80 | 3333 | 60/400 |
| t0-yeah-reno | YeAH/NewReno | 80/80 | 3333 | 60/400 |
| t1-yeah-rtt15 | YeAH/YeAH | 15/15 | 625 | 0/600 |
| t1-reno-rtt15 | NewReno/NewReno | 15/15 | 625 | 0/600 |
| t1-yeah-rtt60 | YeAH/YeAH | 60/60 | 2500 | 0/600 |
| t1-reno-rtt60 | NewReno/NewReno | 60/60 | 2500 | 0/600 |
| t1-yeah-rtt240 | YeAH/YeAH | 240/240 | 10000 | 0/600 |
| t1-reno-rtt240 | NewReno/NewReno | 240/240 | 10000 | 0/600 |

Script `scripts/run_H1.py` (Python 3.12, stdlib) SHA-256 `84bae916c1b07039b144a435049604a98fa924624159c1524a2b666d8fa3081f`. Câu lệnh: `cd ~/projects/YeAH-TCP-NPE && python3 scripts/run_H1.py`. Script kiểm tra commit, git status src, source hash, executable hash, cache profile; không configure/build lại; chạy `./ns3 run "scratch/yeah-experiment --..." --no-build` theo manifest, tối đa 3 case song song; log và config riêng, kiểm tra số mẫu 60001, queue bounds, counter monotonic, queue mean, cấu hình summary. Lưu `results/raw/experiments/h1/{manifest.json,environment.json,batch_status.json,<case>/...}`; archive `~/projects/step-H1-experiments.tar.gz` gồm source, script, raw H1. Không ghi đè output; case lỗi được lưu trạng thái và gói dữ liệu nếu runner kết thúc bình thường. Kiểm tra cú pháp và thử validator trên CSV G4 đã đạt trước đó; H1 sau đó được chạy trên WSL của sinh viên. Audit độc lập từ dữ liệu nhận được trình bày ở mục 11.

H1 một lần mỗi cấu hình không random loss, chưa đáp ứng số lần lặp ≥3 của paper. Không coi chạy lại cùng seed hoặc đổi seed không có tác động như mẫu độc lập. H2 dự kiến bổ sung các điểm T1, T2; T3/T4 sau khi kiểm tra H1, tùy ngân sách thời gian; T5 mở rộng. Không khẳng định việc rút phạm vi được giảng viên cho phép. Mô hình thiếu SURGE, Limited Slow Start; TCP NS-3 khác Linux gốc, nên so sánh định lượng có điều kiện. Không lấy số liệu pilot/benchmark làm điểm H.

## 9. J–L — Sau khi xác nhận dữ liệu [CHƯA THỰC HIỆN]

- Khóa danh sách case, source, config, raw/summary, hình, log; audit dữ liệu thiếu, lỗi, trùng, các lần chạy thay thế; đối chiếu 6 yêu cầu.
- Viết báo cáo thống nhất 6 phần: (1) ý tưởng, (2) mô hình/cải tiến, (3) cài đặt, (4) kiểm chứng, (5) thí nghiệm và kết quả, (6) so sánh/nhận xét/kết luận; tài liệu tham khảo. Phần phân tích paper khoảng 2–3 trang theo slide; độ dài còn lại linh hoạt.
- Đóng gói README, C++ cuối, scripts, configs, kết quả và minh chứng thiết yếu, patch nếu có; PDF báo cáo và ZIP hoặc Git public. Không nộp cache, build, gói trao đổi thừa. Kiểm tra chạy lại theo README và nộp cả email/LMS.

## 10. Danh mục minh chứng và dấu vết phiên bản

| File | SHA-256 |
|---|---|
| step-E-source-review.tar.gz | 5b9a2bd409b3fe51fabfd05b0049dc415c54b6a1a3954a0f48608f2d6b8202ba |
| step-F-pilot-source.zip | 7c2838a03c441059d5183163b1404e066b169ce7e24daec74ca8a9841499ecb0 |
| step-F-pilot.tar.gz | 961f8fa23d16b0f7f446254646696db3b73af35352e288af989b00c4802fa5d6 |
| step-G1-validation.tar.gz | 0a56e05d8a62ac0503c3386bf0bde5474210121edd301dafdbe74404f99a076c |
| step-G2-validation.tar.gz | 1f25062409ec3b07514512421552f0d3f0f9508a0d7f1dff63132451b28ae9a3 |
| step-G3-benchmark.tar.gz | 86bd1a64454ab7ae34e23f872307b3bf430dc23a43f8d636b89051874ac83475 |
| step-G4-optimized.tar.gz | 04f891c57410c190e341856e22b5899b3c380d1f7e079c053a324d21471f8af9 |
| C++ bản đầu | 8444e8b89a42f8ea71038ac785f869fdf8a65c78034b40030b0cd8ff8160d8da |
| C++ bản F chạy thành công | 460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969 |

Trạng thái tổng thể tại bản 06: A–E đã xong trong phạm vi nêu; F pilot đạt; G1–G4 hoàn thành trong phạm vi kiểm chứng; H1 có 8/8 lượt chạy PASS và CSV được audit độc lập. H2–H5, so sánh định lượng paper, nghiệm thu I, báo cáo J và nộp K–L chưa hoàn tất. Không quy đổi số mốc sang tỷ lệ điểm BTL.

Script G4 SHA-256: `1437c78c42bfdc889f51da82f103654be137af8f299ece135a6e6130a04fa831`. Kiểm tra cú pháp bash -n đã đạt; script trong archive G4 có cùng SHA-256 và đã chạy thành công trên máy sinh viên.


## 11. H1 — T0 và T1: audit sau khi chạy [XÁC NHẬN TỪ ARCHIVE, CHƯA CHẠY LẠI NS-3 ĐỘC LẬP]

**Nguồn:** `step-H1-experiments.tar.gz` do sinh viên gửi ngày 20/11/2026; bộ `manifest.json`, `environment.json`, `batch_status.json`, cấu hình, `status.json`, `run.log`, `summary.csv`, `timeseries.csv` của 8 trường hợp, cùng `simulation/yeah-experiment.cc` và `scripts/run_H1.py`.

### 11.1. Mục tiêu, môi trường, cấu hình và lệnh đã chạy

- Mục tiêu T0: quan sát diễn biến cửa sổ TCP và hàng đợi khi luồng thứ hai bắt đầu vào giây 60 và ứng dụng gửi dừng ở giây 400; so sánh YeAH–YeAH và YeAH–NewReno.
- Mục tiêu T1: so sánh hai thuật toán tại RTT danh nghĩa 15, 60, 240 ms với buffer 100% nominal BDP, phục vụ Figure 3 và Table I (đối chiếu số liệu paper **chưa thực hiện**).
- NS-3.44, Git commit `43dce6710b8df69685e3479c1d33a571dda714ea`, source SHA-256 `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`. Build optimized: CMAKE_BUILD_TYPE=release, NS3_NATIVE_OPTIMIZATIONS=ON, NS3_ASSERT=OFF, NS3_LOG=OFF. Bản ghi môi trường cho thấy git status sạch trong lúc batch chạy.
- Băng thông nghẽn 500 Mbps, access 1 Gbps, 600 s/case, IPv4 TCP timestamps, MSS 1448 byte, `initialCwnd=10`, `initialSsthreshSegments=0` (UINT32_MAX), packet loss ngẫu nhiên = 0, seed/run = 1/1, bufferRatio=1; lấy mẫu queue/cwnd/RTT/counters mỗi 10 ms. Có 8 case chạy tối đa ba tiến trình song song. Không thay thế kết quả G1–G4.
- Câu lệnh sinh viên đã thực hiện: `cd ~/projects/YeAH-TCP-NPE && python3 scripts/run_H1.py`. Script gọi `./ns3 run "scratch/yeah-experiment --<các tham số theo manifest> --out=<thư mục case>" --no-build`; câu lệnh đầy đủ riêng từng lượt nằm trong `run.log` và `status.json`. Không suy diễn rằng cùng dữ liệu trên máy khác sẽ chắc chắn khớp bit-for-bit khi chưa chạy lại.

### 11.2. Xác minh và kiểm toán

- 8/8 `status=PASS`, `returncode=0`, mỗi lượt có đủ file cấu hình/log/CSV; 60.001 mẫu `timeseries.csv` tại t=0..600 s, bước 0,01 s, chứa header một lần.
- Mỗi cấu hình khớp `manifest.json`, khớp tham số ghi trong `summary.csv`; hai loại socket của từng node khớp log; queue sampled không vượt buffer; bộ đếm RX, wire, overflow/other/random không giảm; 60.000 mẫu đầu dùng tính queue mean, mốc cuối ghi giá trị kết thúc.
- SHA-256 của `summary.csv` và `timeseries.csv` của từng case khớp với `status.json`/`batch_status.json`; bản ghi source SHA trùng file C++ đính kèm. Tính lại goodput từ RX bytes, wire utilization từ byte PhyTxBegin, queue mean/max từ trace, overflow từ bộ đếm, Jain từ goodput; tất cả khớp trong giới hạn làm tròn.
- **Giới hạn phạm vi xác minh:** chỉ audit dữ liệu do máy sinh viên tạo và source gửi kèm, chưa chạy lại độc lập toàn bộ mô phỏng trên máy người kiểm tra; không khẳng định mô hình trùng testbed Linux của paper.

### 11.3. Kết quả H1 (được tính lại từ raw CSV)

Đơn vị: `goodput` Mbps, `wire` và `queue/buffer` %, `loss` = số packet bị DropTail loại, `overflow/10⁶` = số drop trên một triệu lần thử enqueue tại bottleneck, `Jain` dùng **toàn bộ 600 giây** (với T0 không được dùng làm fairness của hai luồng đồng thời), `wall` phút thời gian chạy thực tế, không phải thời gian mô phỏng.

| Case | TCP1/TCP2 | RTT (ms) | Goodput | Wire (%) | Queue/B (%) | Drops | Overflow/10⁶ | Jain* | Wall (phút) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t0-yeah-yeah | yeah/yeah | 80 | 457.7462 | 94.964 | 22.157 | 2198 | 92.694 | 0.7922 | 59.9 |
| t0-yeah-reno | yeah/reno | 80 | 395.2708 | 82.002 | 29.933 | 4226 | 206.372 | 0.9641 | 65.4 |
| t1-yeah-rtt15 | yeah/yeah | 15 | 481.3524 | 99.861 | 70.988 | 412 | 16.524 | 0.9991 | 14.8 |
| t1-reno-rtt15 | reno/reno | 15 | 481.9238 | 99.979 | 72.946 | 736 | 29.484 | 0.9663 | 15.5 |
| t1-yeah-rtt60 | yeah/yeah | 60 | 477.1383 | 98.987 | 46.937 | 1968 | 79.619 | 0.9927 | 43.2 |
| t1-reno-rtt60 | reno/reno | 60 | 481.4666 | 99.885 | 59.499 | 2508 | 100.557 | 0.9019 | 54.2 |
| t1-yeah-rtt240 | yeah/yeah | 240 | 477.9984 | 99.165 | 0.725 | 6581 | 265.740 | 1.0000 | 145.5 |
| t1-reno-rtt240 | reno/reno | 240 | 479.1833 | 99.411 | 50.990 | 10003 | 402.808 | 0.9998 | 198.4 |


Đối với T1, ở ba RTT đã đo, YeAH có `queue/buffer` thấp hơn NewReno, trong khi goodput và wire utilization có thể thấp hơn một ít. YeAH vẫn xuất hiện overflow drops (không khẳng định YeAH luôn không mất gói); tại 240 ms `queue/buffer` trung bình rất thấp nhưng số drop tích lũy khác 0, nghĩa là trung bình thấp **không** đồng nghĩa không có pha nghẽn. Mỗi điểm T1 là một lần chạy, chưa có khoảng tin cậy/thống kê nhiều lượt; không nội suy sang RTT 30/120/480 ms như đã có số liệu.

### 11.4. T0: theo dõi thời điểm luồng vào/rời, không đọc sai Jain

Luồng hai bắt đầu ứng dụng gửi ở 60 s, ứng dụng được đặt dừng ở 400 s. Dữ liệu RX2 thực tế vẫn tăng đến 402,71 s (YeAH/YeAH) và 401,29 s (YeAH/NewReno). Đây là *mốc nhận thêm byte cuối cùng ở PacketSink tại độ phân giải mẫu 10 ms*, **không** chứng minh TCP đã đóng ngay ở mốc này. Khoảng 400–600 có thêm dữ liệu RX2 nhỏ do drain sau ứng dụng stop.

Tổng hợp goodput từng khoảng bằng **chênh lệch bộ đếm RX** ở đúng hai mốc biên, chia độ dài khoảng; queue mean lấy các mẫu t thuộc [a,b):

| Case | Khoảng (s) | YeAH flow1 (Mbps) | Flow2 (Mbps) | Tổng (Mbps) | Queue trung bình (gói) |
|---|---|---:|---:|---:|---:|
| t0-yeah-yeah | 0–60 | 468.215 | 0.000 | 468.215 | 32.552 |
| t0-yeah-yeah | 60–400 | 282.162 | 195.476 | 477.637 | 1164.775 |
| t0-yeah-yeah | 400–600 | 418.140 | 2.651 | 420.791 | 225.561 |
| t0-yeah-reno | 0–60 | 468.215 | 0.000 | 468.215 | 32.552 |
| t0-yeah-reno | 60–400 | 67.475 | 414.549 | 482.024 | 1744.633 |
| t0-yeah-reno | 400–600 | 223.319 | 2.588 | 225.907 | 17.332 |


Các số Jain trong `summary.csv` phản ánh cả giai đoạn chỉ có một luồng; **không sử dụng** để kết luận về Reno-friendliness/fairness khi hai luồng cùng truyền. Có thể tính Jain riêng giai đoạn 60–400 s nếu sau đó nêu rõ cửa sổ và quá trình startup. Trong hình cwnd, ứng dụng dừng nhưng biến cwnd lưu giá trị cuối; script biểu đồ che phần flow2 trước khi bắt đầu và sau lần RX2 tăng cuối để tránh diễn giải nhầm cwnd phẳng thành luồng đang hoạt động. Dữ liệu gốc không bị chỉnh sửa.

### 11.5. Pipeline phân tích và hình sơ bộ từ dữ liệu thực

File `scripts/analyze_H1.py` đã được chạy thử trực tiếp với bản giải nén của gói H1, 8/8 audit PASS. Chức năng: xác minh cấu hình/hash/log; tính lại các độ đo; tạo `results/summary/h1/{h1_summary_verified.csv,t0_windows.csv,t1_rtt_verified.csv,h1_audit.json}` và 7 hình PNG 300 DPI + SVG trong `results/figures/h1/`. Hình T0 là cwnd và hàng đợi (bình quân 1 s, từ 100 mẫu 10 ms); T1 là queue normalized, wire utilization và overflow per million attempts theo ba RTT thực có. Hình từ dữ liệu H1, không phải các hình do AI tự ước lượng. Cần chạy cùng script trên WSL của sinh viên để xác nhận quy trình tái tạo từ project; biểu đồ chưa phải kết luận hoặc bảng so sánh paper cuối cùng.

**Công thức kiểm tra** (cùng cửa sổ 600 s với source C++):

- `Goodput_i (Mbps) = 8 × RX_i_bytes / (600 × 10^6)`.
- `Wire utilization = 8 × wire_bytes / (600 × 500 × 10^6)`.
- `Queue/B = mean(queue_packets over t ∈ [0,600)) / buffer_packets`.
- `Overflow probability (theo source) = bottleneck_drops / (queue_enqueued + bottleneck_drops)`. Đây là tỷ lệ ở hàng đợi, **không tự động tương đương xác suất mất gói end-to-end hoặc công thức Table I của paper**.
- `J = (g1+g2)^2 / [2(g1^2+g2^2)]`. Với T0, chỉ tính Jain ở cửa sổ hai luồng cùng hoạt động nếu muốn đánh giá công bằng.

Các dữ liệu cần bổ sung/chưa xác nhận: RTT 30/120/480 ms (T1), T2 buffer, T3 RTT fairness, T4 random loss, T5 mở rộng; thời gian chạy và số lượt lặp cần cân đối trước hạn nộp; chưa có kết quả định lượng khớp paper; không có SURGE hoặc Limited Slow Start; chưa có các biến thể TCP đầy đủ như paper; chỉ có một seed/run/case nên chưa suy luận độ biến thiên thống kê.

### 11.6. Dấu vết file và quyết định

- `step-H1-experiments.tar.gz` SHA-256 `3451956e059bbab7d0dd1d172fa40b452305328ff0e02f8d66208908c4734c21`.
- `scripts/analyze_H1.py` SHA-256 `0d2ba5554f8ff562583e1f5a79598f8101f57ab7af6a01f2cd4d24e5a139b998`.
- Bảng xác minh `h1_summary_verified.csv` SHA-256 `afdd72634491376ee7ac2a5db4a0a5e5a68404f80173fc67a87f9360f8e9c1bb` (tạo từ bản giải nén).
- Quyết định: **H1 hoàn thành trong phạm vi dữ liệu kiểm toán**, H2–H5 chưa thực hiện. Chưa viết báo cáo chính thức. Tiếp theo sinh viên chạy pipeline H1 tại WSL, gửi log `AUDIT PASS`, sau đó chốt nhóm thí nghiệm H2 có mức ưu tiên cao nhất theo thời gian còn lại.


## 12. Tái tạo H1 trên máy sinh viên và chốt thiết kế H2 (20/11/2026)

### 12.1. H1: tái tạo pipeline phân tích trên WSL [XÁC NHẬN TỪ TERMINAL NGƯỜI DÙNG]

Người dùng chạy trực tiếp trên máy Ubuntu 24.04, trong project hiện tại:

```bash
cd ~/projects/YeAH-TCP-NPE
python3 -m zipfile -e H1_analysis_package.zip .
python3 scripts/analyze_H1.py
```

Terminal trả về `AUDIT PASS` cho lần lượt các ID `t0-yeah-yeah`, `t0-yeah-reno`, `t1-yeah-rtt15`, `t1-reno-rtt15`, `t1-yeah-rtt60`, `t1-reno-rtt60`, `t1-yeah-rtt240`, `t1-reno-rtt240`, mỗi case 60.001 mẫu, và dòng kết thúc:

```text
VERIFIED H1: 8/8, source and hashes match, metrics recomputed
OUTPUT: /home/hung/projects/YeAH-TCP-NPE/results/summary/h1
FIGURES: /home/hung/projects/YeAH-TCP-NPE/results/figures/h1
```

**Phạm vi xác nhận:** chính script phân tích H1 báo kiểm tra đạt trên WSL của sinh viên, sau khi đã được thử với archive H1. Chưa có kiểm tra ảnh chụp từng biểu đồ trên WSL; không khẳng định PNG có hash giống máy khác (font/thư viện có thể khác). Script không tự chạy lại simulation; các bảng và hình được tái tạo từ raw CSV đã xác nhận. H1 được khóa làm bộ dữ liệu đầu vào hợp lệ, không cần chạy lại chỉ vì bước tiếp theo.

### 12.2. H2: ảnh hưởng kích thước bộ đệm [DỰ KIẾN, CHƯA CHẠY]

**Căn cứ paper:** Section V-C, Figure 6, RTT1=RTT2=80 ms, C=500 Mbps, mất gói ngẫu nhiên = 0, buffer B/BDP = 0,125; 0,25; 0,5; 1; paper sử dụng mặc định 600 s. H2 chỉ đối chiếu YeAH với NewReno (không có tất cả thuật toán paper). Chưa có SURGE, Limited Slow Start và khác biệt physical testbed Linux với NS-3.44 vẫn tồn tại.

- Kịch bản: 2 luồng đồng thời từ đầu đến cuối; TCP cùng loại YeAH×2 hoặc NewReno×2.
- Thông số: bottleneck 500 Mbps, access 1 Gbps, RTT 80/80 ms, 600 s, random loss 0, MSS 1448, initialCwnd 10, ssthresh UINT32_MAX, seed/run 1/1, profile optimized, lấy mẫu 100 Hz.
- 8 case = 4 mức beta × 2 thuật toán. Buffer kỳ vọng theo công thức trong source `floor(500e6 × 0,080 × beta / (8×1500))`: beta=0,125 → 416; 0,25 → 833; 0,5 → 1666; 1,0 → 3333 gói.
- Dùng script `scripts/run_H2.py` (SHA-256 `f7f1f65a3bba2ddf56087036e84c401643cf42980d0eaf81dfb3423abd407625`), ba worker; kiểm tra commit, source, executable và CMake profile; mỗi case xuất config/log/summary/timeseries/status; không được ghi đè H1.
- Script đã qua `py_compile` và hàm kiểm tra CSV đã được thử với **dữ liệu thật từ case H1 T0** (đạt). Script H2 **chưa chạy trên máy sinh viên**, vì vậy tuyệt đối chưa được điền số liệu H2 vào nhật ký hoặc báo cáo.
- Nếu bị ngắt do mất điện hoặc shutdown, lần chạy `--resume` giữ nguyên các case PASS có hash và cấu hình hợp lệ, di chuyển case dở dang vào `_interrupted/` trước khi chạy lại. **Không** tiếp tục simulator giữa chừng; phải chạy lại case bị ngắt từ đầu.
- Kết quả mong muốn khi chạy: `results/raw/experiments/h2/...` và `~/projects/step-H2-buffer.tar.gz` (mới là đường dẫn dự kiến). Sau đó cần audit độc lập và tạo script bảng/hình tương tự H1, chưa tự động xem H2 là hợp lệ.

**Quyết định:** H1 hoàn thành + pipeline tái tạo trên WSL đạt; tiếp theo H2. Mọi dữ liệu được giữ tách biệt giữa raw H1 và H2; báo cáo chính thức vẫn tạm dừng cho đến khi khóa bộ thực nghiệm.


## 13. H2 – Đánh giá ảnh hưởng của kích thước bộ đệm (20/11/2026)

### 13.1. Nguồn minh chứng và trạng thái xác minh

- File do người dùng tải lên: `step-H2-buffer.tar.gz`, SHA-256: `b3bb1da1c21337dd7cfdba11731f8ede82bd9cfa710d9d84044d0eaa0ab8663d`.
- Đã giải nén và **audit độc lập tất cả 8/8** thư mục `results/raw/experiments/h2/t2-*/`, kiểm tra `environment.json`, `manifest.json`, `batch_status.json`, `config.json`, `status.json`, `run.log`, `summary.csv`, `timeseries.csv` và bản `simulation/yeah-experiment.cc` + `scripts/run_H2.py` đi kèm.
- Mã nguồn mô phỏng SHA-256: `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`.
- SHA-256 của script chạy H2: `f7f1f65a3bba2ddf56087036e84c401643cf42980d0eaf81dfb3423abd407625`.
- NS-3: `3.44`, Git commit `43dce6710b8df69685e3479c1d33a571dda714ea`, build `optimized`; `git_status` được script ghi rỗng. Hash mã nguồn **trùng với H1/G3**. Hash executable được **ghi nhận bởi script H2 trên WSL**, người kiểm tra chỉ có file log/manifest, không có file nhị phân để tự đối chiếu.
- Trạng thái: tất cả 8 kịch bản `PASS`, `returncode=0`, log xác nhận lớp TCP đúng loại, mỗi CSV time series có **60.001 mẫu từ 0 đến 600 s**, cách nhau 10 ms; các hash raw CSV khớp status; không phát hiện đếm byte/drops giảm ngược; hàng đợi nằm trong giới hạn buffer vật lý.
- Các chỉ số `goodput`, `wire utilization`, queue mean/normalized, `overflow_probability`, Jain được tính lại từ dữ liệu thô và khớp `summary.csv` trong dung sai làm tròn. Số mẫu queue mean là **60.000** (t ∈ [0,600)), không lấy mẫu cuối tại t=600 vào trung bình.
- **Đối chiếu chéo độc lập:** với β=1.0, 18.001 dòng đầu (t=0..180s), 14 cột `timeseries.csv` đều trùng từng giá trị với benchmark G3 `yeah180` và `reno180` tương ứng. Không khẳng định mọi kịch bản/phiên bản tương đương ngoài phạm vi này.
- **Giới hạn:** chưa chạy lại mô phỏng từ đầu trong môi trường phân tích; mới audit file kết quả tải lên. Mỗi cấu hình là một lượt chạy, seed/run=1/1, chưa có sai số thống kê hoặc khoảng tin cậy.

### 13.2. Cấu hình thí nghiệm đã đối chiếu source/manifest

| Thuộc tính | Giá trị thực chạy |
|---|---|
| Mục tiêu | Ảnh hưởng tỷ lệ buffer/BDP, so sánh hai thuật toán, liên hệ một phần Figure 6 |
| Topology | 2 sender → router → receiver; access link 1 Gbps, bottleneck 500 Mbps |
| RTT danh định | 80 ms / 80 ms |
| Thuật toán | YeAH × 2 hoặc NewReno × 2 |
| β | 0.125 / 0.25 / 0.5 / 1.0 |
| Buffer | 416 / 833 / 1666 / 3333 packet |
| Thời lượng | 600 s/case; hai ứng dụng gửi từ đầu đến hết mô phỏng |
| Loss random | 0; nguồn đếm overflow là FIFO DropTail của bottleneck |
| MSS / cửa sổ đầu | 1448 byte / initialCwnd=10 segment / initialSsthreshSegments=0 (mã C++ diễn giải là UINT32_MAX) |
| Seed/run/profile | 1/1, optimized |
| Dữ liệu | 10 ms/sample, cấu hình + log + CSV + SHA-256/case |
| Mã nguồn được sử dụng | Giữ nguyên `TcpYeah` gốc của NS-3.44, chỉ dùng scratch `yeah-experiment.cc` |

**Câu lệnh tạo toàn bộ loạt chạy (đã được thực thi trên máy người dùng):**

```bash
cd ~/projects/YeAH-TCP-NPE
python3 scripts/run_H2.py
```

**Đường dẫn kết quả thô:** `results/raw/experiments/h2/`. Đường dẫn lưu trữ và lệnh cụ thể cho từng case có trong `batch_status.json` / `status.json`.

### 13.3. Bảng kết quả H2 đã tính lại từ CSV gốc

Goodput = tổng byte payload nhận ở 2 PacketSink × 8 / (600×10^6); `wire` = số byte truyền trên bottleneck / (capacity×600 s); `queue/buffer` = trung bình 60.000 mẫu queue vật lý / dung lượng buffer; `drop` = DropTail loại gói ở bottleneck; `overflow/10^6` = DropTail drops / (enqueue thành công + drops) ×10^6. Jain tính goodput của hai luồng trên toàn bộ 600 s.

| β (Buffer/BDP) | TCP | Buffer (pkts) | Goodput (Mbps) | Wire (%) | Queue/Buffer (%) | Drops | Overflow / 10^6 attempts | Jain |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0.125 | yeah | 416 | 401.8073 | 83.3585 | 10.1821 | 352 | 16.9131 | 0.987971 |
| 0.125 | reno | 416 | 358.0683 | 74.2843 | 7.3580 | 349 | 18.8174 | 1.000000 |
| 0.250 | yeah | 833 | 440.3134 | 91.3470 | 21.6636 | 1161 | 50.9043 | 0.998940 |
| 0.250 | reno | 833 | 434.8358 | 90.2106 | 20.0271 | 828 | 36.7612 | 0.999738 |
| 0.500 | yeah | 1666 | 469.7198 | 97.4474 | 35.2039 | 2064 | 84.8284 | 0.876614 |
| 0.500 | reno | 1666 | 466.7756 | 96.8368 | 44.6031 | 2508 | 103.7244 | 0.902105 |
| 1.000 | yeah | 3333 | 460.9980 | 95.6381 | 37.1818 | 4 | 0.1675 | 0.983954 |
| 1.000 | reno | 3333 | 481.2336 | 99.8362 | 53.4412 | 3344 | 134.1388 | 0.998874 |

**Nhận xét sơ bộ có căn cứ:**

- β=0,125: YeAH có goodput 401,8073 Mbps so với NewReno 358,0683 Mbps, **nhưng** queue/buffer của YeAH 10,1821% cao hơn NewReno 7,3580%. β=0,25: YeAH queue/buffer cũng cao hơn một ít (21,6636% so với 20,0271%). Không kết luận YeAH luôn giữ queue thấp hơn ở mọi mức buffer.
- β=0,5: YeAH queue/buffer 35,2039% thấp hơn Reno 44,6031%, goodput 469,7198 vs 466,7756 Mbps. β=1,0: YeAH queue/buffer 37,1818% thấp hơn 53,4412%; chỉ có 4 overflow drops so với 3.344 nhưng goodput toàn 600 s thấp hơn (460,9980 so với 481,2336 Mbps). Các giá trị này là **một lần chạy**, không phải trung bình nhiều seed.
- Kiểm tra bổ sung **giai đoạn [300,600] s** (được tính từ hai mốc bộ đếm RX + wire và 30.000 mẫu queue) tại β=1,0: YeAH goodput 482,0239 Mbps, wire 99,999996%; NewReno goodput 482,0239 Mbps, wire 99,999980%. Điều này cho thấy chênh lệch **goodput toàn 600s** liên quan đến diễn biến theo thời gian/khởi động; không thể suy diễn YeAH kém về thông lượng ổn định chỉ từ trung bình toàn thời gian. Giai đoạn đo được nêu rõ, không sử dụng để thay thế số liệu toàn 600 s.
- Số **drop tích lũy** không tương đương tự động với **xác suất mất gói đầu cuối**; biểu đồ so sánh xác suất overflow cần chuẩn hóa theo enqueue attempts (số đơn vị trên 1 triệu). Không đồng nhất phép đo này với Table I hoặc hiệu suất trong paper nếu định nghĩa không trùng.
- Khác biệt testbed: NS-3.44 thay cho Linux vật lý, chưa SURGE, chưa Limited Slow Start, chỉ so sánh YeAH/NewReno; không tuyên bố tái hiện chính xác toàn bộ Figure 6.

### 13.4. Pipeline phân tích và trạng thái báo cáo

- Tạo script độc lập `scripts/analyze_H2.py`, đầu vào duy nhất cho số liệu đo là `results/raw/experiments/h2/` + bản source/runner để kiểm tra hash; chạy kiểm thử trên bản giải nén của gói H2: **8/8 `AUDIT PASS`**.
- Sinh **bảng** `results/summary/h2/{h2_summary_verified.csv,t2_buffer_verified.csv,t2_windows.csv}` và `h2_audit.json`; sinh **5 biểu đồ** cùng phiên bản PNG (300 DPI) và SVG tại `results/figures/h2/`. Tên/nguồn các biểu đồ: `t2_buffer_goodput`, `t2_buffer_wire_utilization`, `t2_buffer_queue_normalized`, `t2_buffer_overflow`, `t2_buffer_fairness`.
- Pipeline mới **chưa được người dùng chạy lại trên chính WSL** ở thời điểm ghi nhật ký bản 08; các bảng/hình đã sinh trong môi trường kiểm tra từ bản giải nén thực tế. Khi người dùng chạy `python3 scripts/analyze_H2.py`, chỉ đánh dấu "đã tái tạo trên máy sinh viên" khi có log terminal.
- Chưa đối chiếu số liệu định lượng với đường cong của Figure 6; chưa có 3+ seeds/case; chưa tiến hành H3 fairness RTT bất đối xứng và H4 random loss. **Chưa viết báo cáo chính thức**.

**Quyết định:** H2 hoàn thành trong phạm vi audit dữ liệu thực tế; tiếp theo tái tạo pipeline H2 trên máy sinh viên, sau đó chọn thí nghiệm H3 hoặc H4 phù hợp thời gian trước hạn nộp. Không thay đổi H1/H2 raw CSV hay source mô phỏng đã được kiểm chứng.

## 14. H2: xác nhận tái tạo bảng, hình trên WSL (20/11/2026)

### 14.1. Minh chứng mới [XÁC NHẬN TỪ TERMINAL NGƯỜI DÙNG]

Sinh viên đã thực thi trong WSL Ubuntu 24.04:

```bash
cd ~/projects/YeAH-TCP-NPE
python3 -m zipfile -e H2_analysis_package.zip .
python3 scripts/analyze_H2.py
explorer.exe results/figures/h2
```

Terminal có 8 dòng `AUDIT PASS`, một dòng cho từng ID: `t2-yeah-beta0p125`, `t2-reno-beta0p125`, `t2-yeah-beta0p25`, `t2-reno-beta0p25`, `t2-yeah-beta0p5`, `t2-reno-beta0p5`, `t2-yeah-beta1p0`, `t2-reno-beta1p0`, mỗi lượt có 60.001 mẫu. Dòng cuối:

```text
VERIFIED H2: 8/8, source and hashes match, metrics recomputed
OUTPUT: /home/hung/projects/YeAH-TCP-NPE/results/summary/h2
FIGURES: /home/hung/projects/YeAH-TCP-NPE/results/figures/h2
```

**Trạng thái:** H2 hoàn thành cả khâu audit dữ liệu tải lên và chạy lại script kiểm toán/phân tích trên máy sinh viên. Lệnh `explorer.exe` chỉ xác nhận được gọi và trả về prompt, không có ảnh duyệt xác minh trực quan từng PNG; các hình đã được kiểm tra trong môi trường phân tích. Không khẳng định việc chạy script đã chạy lại simulator; các bảng và hình được tạo từ dữ liệu raw H2 đã có. Không viết lại/ghi đè kết quả raw.

### 14.2. Quyết định dữ liệu

- Dữ liệu H1 và H2 được giữ nguyên làm bộ thí nghiệm đã kiểm toán; file tóm tắt/hình nằm trong `results/summary/` và `results/figures/`, script nằm trong `scripts/`.
- Mỗi cấu hình chỉ có một lượt chạy, seed/run=1/1. Trạng thái **PASS** là đạt kiểm tra nhất quán, không phải kết luận thuật toán vượt trội hay chứng minh kết quả giống Linux testbed trong paper.
- Trước khi nộp cần đối chiếu định lượng paper Figure 3/6/7, trình bày sai biệt và giới hạn. Kết quả H3/H4 hiện chưa có.

## 15. Thiết kế H3: fairness theo RTT bất đối xứng [DỰ KIẾN, CHƯA CHẠY]

**Căn cứ:** Section V-D/Figure 7 paper, `RTT1=25 ms`, tỷ số `RTT2/RTT1 = 1,2,3,4`, bottleneck `500 Mbps`, buffer `B=100% BDP`. Chỉ so sánh YeAH và NewReno, không đại diện toàn bộ thuật toán trong paper.

- 8 lượt = bốn RTT2 25/50/75/100 ms × hai loại TCP (YeAH/YeAH hoặc NewReno/NewReno), mỗi lượt 600 giây.
- Hai luồng bắt đầu cùng lúc, `flow2Start=0`, `flow2Stop=600` (dừng ứng dụng ở cuối); `loss=0`, `bufferRatio=1`, MSS=1448 B, initialCwnd=10, initialSsthreshSegments=0, seed/run=1/1, optimized, sample 10 ms.
- BDP theo code C++ dựa trên min RTT 25 ms: `floor(500e6×0.025/(8×1500)) = 1041` gói, giữ không đổi giữa bốn tỷ số. Đây là BDP danh định theo source, không phải kích thước đo thực tế từ router.
- Fairness dùng Jain từ goodput hai luồng trên cửa sổ 0–600s; cần nêu rõ giai đoạn khởi động có thể ảnh hưởng. Có thể tính thêm cửa sổ ổn định sau khi nhận dữ liệu, không được thay thế số liệu toàn thời gian một cách im lặng.
- Output dự kiến: `results/raw/experiments/h3/`, file `step-H3-fairness.tar.gz`. Chưa có số liệu thực tế, chưa tạo đồ thị kết quả H3.
- Script `scripts/run_H3.py`: SHA-256 `91948c8cba0eae07e2fa37857dee831f0535fc6b6e7e00c7066bef038cc92526`, dựa trên runner H2 đã chạy; bản mới đã kiểm tra cú pháp Python, cấu hình tám case và thử audit với dữ liệu thật G2 (`cubic-asym-50`, RTT 25/100 ms). Điều này **không** thay thế kiểm thử thực tế H3 trên máy sinh viên.
- Kiểm tra tính toàn vẹn: commit NS-3, git status `src`, SHA-256 mã C++ và binary, `run.log`, `config.json`, `summary.csv`, `timeseries.csv`, hash mỗi CSV, time series 60.001 mẫu, các phép tính goodput/queue/wire/Jain và RTTmin không nhỏ hơn propagation RTT theo sai số cho phép.
- Nếu ngắt giữa chừng: `python3 scripts/run_H3.py --resume`. Runner bảo tồn lượt PASS hợp lệ, lưu riêng lần bị ngắt và chỉ chạy lại lượt dở dang.
- **Giới hạn:** chưa có các lượt lặp với seed độc lập; chưa có SURGE, Limited Slow Start; testbed NS-3 khác Linux paper, kết quả không buộc giống nguyên văn Figure 7.

**Việc tiếp theo:** Chạy H3, gửi archive/log và nhận kết quả audit độc lập. Sau H3, chốt nhóm random loss H4 có phạm vi khả thi, đồng thời dành thời gian cho đối chiếu paper, báo cáo PDF/DOCX và source trước hạn nộp 22/11/2026 00:00 (giờ Việt Nam).


## 16. H3: kiểm chứng fairness theo tỷ số RTT (20/11/2026) [ĐÃ XÁC NHẬN TỪ GÓI UPLOAD]
### 16.1. Đầu vào, cấu hình và bằng chứng
- Đầu vào: gói thực nghiệm `step-H3-fairness.tar.gz` người dùng gửi; giải nén, kiểm tra độc lập. Không phát sinh số liệu mô phỏng bằng công cụ phân tích.
- Source mô phỏng `simulation/yeah-experiment.cc` SHA-256: `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969` (trùng H1/H2 và manifest H3).
- Script chạy `scripts/run_H3.py` SHA-256: `91948c8cba0eae07e2fa37857dee831f0535fc6b6e7e00c7066bef038cc92526`.
- NS-3 3.44; commit `43dce6710b8df69685e3479c1d33a571dda714ea`, build `optimized`; executable hash `91c1b8ddc4460d79f1d95855a7692dc67b6c29ae0e50f4bdae319ba6a3775590`.
- Tám case, hai luồng cùng loại YeAH hoặc NewReno; RTT1 25 ms; RTT2 25/50/75/100 ms; bottleneck 500 Mbps; access 1 Gbps; `bufferRatio=1`, `buffer_packets=1041` vì `floor(500e6×0.025/(8×1500))=1041`; loss ngẫu nhiên = 0.
- Duration 600 s, ứng dụng bắt đầu từ đầu và dừng ở cuối, `flow2Start=0, flow2Stop=600`; TCP MSS 1448 B, initialCwnd=10 segment, initialSsthreshSegments=0, seed/run=1/1, mẫu cách 10 ms.
- Lệnh người dùng đã thực thi: `python3 scripts/run_H3.py`. Câu lệnh NS-3 chi tiết của từng case trong `status.json`/`run.log`; môi trường trong `environment.json`; ma trận trong `manifest.json`.
- **Kiểm toán độc lập:** đủ 8/8 status PASS và returncode 0; cấu hình mỗi case khớp manifest/CSV/log; hash của `summary.csv`, `timeseries.csv` khớp status; các biến đếm tích lũy không giảm; 60.001 mẫu/case; queue nằm trong `[0,1041]`; goodput, wire utilization, queue mean/normalized, overflow probability, Jain tính lại đều khớp.

### 16.2. Bảng kết quả H3 (Jain trên toàn 600 giây) [XÁC NHẬN]
| RTT2/RTT1 | TCP | Goodput1 (Mbps) | Goodput2 (Mbps) | Tổng goodput (Mbps) | Jain | Queue/Buffer (%) | Overflow drops |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | NewReno | 239.6783 | 242.1552 | 481.8335 | 0.999974 | 68.35 | 1076 |
| 1 | YeAH | 242.7515 | 238.7151 | 481.4665 | 0.999930 | 69.22 | 929 |
| 2 | NewReno | 347.7654 | 133.3380 | 481.1035 | 0.834273 | 56.75 | 979 |
| 2 | YeAH | 318.2852 | 158.9373 | 477.2226 | 0.899690 | 50.72 | 566 |
| 3 | NewReno | 434.5300 | 46.9373 | 481.4674 | 0.606773 | 53.32 | 1128 |
| 3 | YeAH | 421.7570 | 55.4727 | 477.2297 | 0.629291 | 48.89 | 623 |
| 4 | NewReno | 377.9429 | 101.9952 | 479.9382 | 0.751549 | 48.31 | 1095 |
| 4 | YeAH | 363.1793 | 112.1602 | 475.3394 | 0.781939 | 44.27 | 730 |

- **Jain toàn 600 s:** `J=(g1+g2)^2/[2×(g1²+g2²)]`, trong đó `g1,g2 = payload receiver bytes × 8/(600 × 10^6)` Mbps. Chỉ số này phản ánh công bằng của **một lần chạy**, không phải trung bình nhiều seed.
- Kết quả toàn 600 s: tại tỷ số 1, NewReno (0,999974) nhỉnh hơn YeAH (0,999930); tại tỷ số 2, 3 và 4, YeAH đạt Jain cao hơn NewReno trong các lần chạy này. Xu hướng **không đơn điệu**: tỷ số 4 có Jain cao hơn tỷ số 3 với cả hai thuật toán. Không điều chỉnh hay làm mượt dữ liệu để khớp kỳ vọng.
- Khi RTT bất đối xứng, luồng RTT ngắn thường giành goodput cao hơn trong các lần chạy; bảng gốc cung cấp goodput riêng từng luồng để kiểm chứng.

### 16.3. Kiểm tra cửa sổ thời gian [PHÂN TÍCH BỔ SUNG TỪ DỮ LIỆU GỐC]
Jain 300–600 s được tính từ **chênh lệch** bộ đếm byte ở giây 300 và 600, không lấy trung bình Jain của các khoảng.
| RTT2/RTT1 | TCP | Jain 0–300s | Jain 300–600s |
|---:|---|---:|---:|
| 1 | NewReno | 0.994379 | 0.992759 |
| 1 | YeAH | 0.983499 | 0.979136 |
| 2 | NewReno | 0.790496 | 0.875803 |
| 2 | YeAH | 0.953003 | 0.835344 |
| 3 | NewReno | 0.592715 | 0.621067 |
| 3 | YeAH | 0.597590 | 0.661492 |
| 4 | NewReno | 0.717990 | 0.784955 |
| 4 | YeAH | 0.845753 | 0.718115 |

- Ở tỷ số 2, YeAH Jain toàn 600 s là 0,899690 nhưng riêng 300–600 s là 0,835344; NewReno 300–600 s là 0,875803. Vì vậy thứ hạng giữa hai thuật toán **có thể đảo chiều theo khoảng đo**. Kết luận chỉ áp dụng cho chỉ số/cửa sổ đã nêu.
- Không kết luận thuật toán YeAH luôn công bằng hơn Reno; chưa có lặp độc lập hoặc khoảng tin cậy.

### 16.4. Bộ phân tích và hình [ĐÃ KIỂM CHỨNG TRONG MÔI TRƯỜNG PHÂN TÍCH]
- Đã tạo `scripts/analyze_H3.py` độc lập; SHA-256 `3cdd2cd182de766165989669622c5b499146734c276b491010f349836be1cf99`. Script **chỉ đọc** dữ liệu raw H3, kiểm tra source/runner hashes, status/config/manifest, tính lại chỉ số và tạo bảng/hình.
- Đã chạy `analyze_H3.py` trên bản giải nén của dữ liệu upload: **8/8 AUDIT PASS**. Tạo bảng `h3_summary_verified.csv`, `t3_fairness_comparison.csv`, `t3_fairness_windows.csv`, `h3_audit.json`.
- Bốn biểu đồ có PNG 300 dpi và SVG: `t3_rtt_ratio_fairness_0_600`, `t3_rtt_ratio_fairness_300_600`, `t3_rtt_ratio_per_flow_goodput`, `t3_rtt_ratio_queue`. Trục và giá trị chỉ xuất phát từ dữ liệu đã kiểm chứng. Các đường nối điểm không có nghĩa đã chạy RTT trung gian.
- **Chưa xác nhận chạy lại script phân tích H3 trên chính Ubuntu của sinh viên** tại thời điểm lập nhật ký v10. Cần chờ log `VERIFIED H3: 8/8` trước khi đánh dấu hoàn thành tái tạo tại máy sinh viên.

### 16.5. Giới hạn, thông tin chưa đủ căn cứ và quyết định
- H3 có một lượt chạy cho mỗi cấu hình; seed/run=1/1. Không có sai số, khoảng tin cậy hay kiểm định khác biệt theo nhiều lần chạy.
- Mô hình dùng NS-3.44 thay cho Linux testbed vật lý; chưa tái tạo SURGE cross traffic và Limited Slow Start; đối chứng chỉ YeAH/NewReno.
- **Chưa đối chiếu định lượng Figure 7** với dữ liệu đọc chính xác từ paper; không gán cứng số liệu paper hoặc tuyên bố khớp paper trước khi kiểm tra.
- H1/H2 vẫn giữ nguyên; dữ liệu H3 chỉ bổ sung. Không sửa upstream `TcpYeah`, không chỉnh sửa dữ liệu raw.
- Trạng thái: **H3 đạt kiểm toán dữ liệu tải lên; tái tạo pipeline H3 trên WSL đang chờ.** H4 random loss chưa thực hiện. Chỉ viết báo cáo sau khi thực nghiệm và kiểm toán tổng thể hoàn tất.

**Bước tiếp theo:** sinh viên chạy `python3 scripts/analyze_H3.py` từ `H3_analysis_package.zip`, gửi log xác nhận. Sau đó chọn cấu hình H4 random loss có phạm vi phù hợp, hoàn tất phân tích, so sánh paper và đóng gói trước 00:00 ngày 22/11/2026 (GMT+7).

---

## 17. H3 – Xác nhận tái tạo bộ phân tích trên máy sinh viên (20/11/2026) [ĐÃ XÁC NHẬN TỪ TERMINAL]

Sinh viên thực thi trên WSL Ubuntu 24.04:

```bash
cd ~/projects/YeAH-TCP-NPE
python3 -m zipfile -e H3_analysis_package.zip .
python3 scripts/analyze_H3.py
explorer.exe results/figures/h3
```

Terminal có tám dòng `AUDIT PASS` cho `t3-yeah-ratio1`, `t3-reno-ratio1`, ..., `t3-yeah-ratio4`, `t3-reno-ratio4`, mỗi kịch bản có **60001 samples**, theo sau là:

```text
VERIFIED H3: 8/8, source and hashes match, metrics recomputed
OUTPUT: /home/hung/projects/YeAH-TCP-NPE/results/summary/h3
FIGURES: /home/hung/projects/YeAH-TCP-NPE/results/figures/h3
```

**Trạng thái mới:** H3 đã qua cả kiểm toán độc lập dữ liệu gốc do sinh viên gửi và chạy lại script kiểm toán/phân tích trên máy sinh viên. H1 và H2 vẫn giữ nguyên; bảng số liệu H3 ở mục 16 không thay đổi. `explorer.exe` đã được gọi để mở thư mục, nhưng không chứng minh từng ảnh PNG được xem trực quan trên máy sinh viên. Mỗi cấu hình H3 mới có **một lần chạy** seed/run=1/1; chưa có khoảng tin cậy, chưa đối chiếu định lượng Figure 7.

## 18. Thiết kế H4 – Mất gói ngẫu nhiên [DỰ KIẾN, CHƯA CHẠY]

**Căn cứ:** Figure 5 paper YeAH-TCP (2007) đo link utilization theo xác suất mất gói, với RTT1=RTT2=200ms, C=500Mbps, B=100% BDP=8333 packets. Chọn bốn điểm `p=1e-8, 1e-6, 1e-5, 1e-4` thuộc miền khảo sát; không nội suy hay giả định thêm điểm chưa chạy.

- Tám kịch bản = 4 xác suất × 2 TCP (YeAH/YeAH và NewReno/NewReno). Mỗi lượt 600s, `flows=2`, `capacity=500`, `rtt1=rtt2=200`, `bufferRatio=1`, `flow2Start=0`, `flow2Stop=600`, `mss=1448`, `initialCwnd=10`, `initialSsthreshSegments=0`, `seed=1`, `run=1`, build optimized, trace 10ms.
- Buffer = `floor(500e6×0.2/(8×1500))=8333` gói theo **định nghĩa BDP trong chương trình hiện tại**. Mô hình lỗi dùng `RateErrorModel(ERROR_UNIT_PACKET)` tại phía nhận liên kết bottleneck. `p` là xác suất cấu hình, **không phải** tỷ lệ quan sát trong kết quả; mức p rất nhỏ có thể ghi nhận 0 random drops.
- Mục tiêu: goodput, `wire_utilization`, `random_drops`, `bottleneck_drops`, queue normalized và Jain. Không đánh đồng goodput, link utilization hay các loại mất gói; so sánh Figure 5 chủ yếu dùng wire utilization nếu định nghĩa tương thích.
- Script `scripts/run_H4.py`, SHA-256: `c77cb78d9ab921a4994e778586473a1bf587e4b4e9bba75d3faf1313f6138c74`; cố định git commit `43dce6710b8df69685e3479c1d33a571dda714ea`, source SHA-256 `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`, optimized executable SHA-256 `91c1b8ddc4460d79f1d95855a7692dc67b6c29ae0e50f4bdae319ba6a3775590`. Không thay đổi source hay build; chạy tối đa 3 process song song; `--resume` chỉ tái dùng kết quả PASS đã xác nhận và bảo tồn dữ liệu gián đoạn trong `_interrupted`.
- IDs: `t4-yeah-p1e-8`, `t4-reno-p1e-8`, `t4-yeah-p1e-6`, `t4-reno-p1e-6`, `t4-yeah-p1e-5`, `t4-reno-p1e-5`, `t4-yeah-p1e-4`, `t4-reno-p1e-4`.
- Đầu ra **dự kiến, chưa tồn tại tại thời điểm ghi**: `results/raw/experiments/h4/` và `~/projects/step-H4-random-loss.tar.gz`, có manifest/environment/config/status/log/summary.csv/timeseries.csv; script **chưa chạy mô phỏng trên máy sinh viên**.
- Đã kiểm tra trước: `python3 -m py_compile` đạt; tám ID hợp lệ; phép tính buffer cho tám kịch bản cho 8333; thử hàm `audit()` trên CSV **thực tế** của G2 `loss-50` (20s, p=0.001, 25 random drops) sau khi thay tham số audit tương ứng đạt. Đây là kiểm thử logic audit của script H4, **không phải dữ liệu H4**.
- Giới hạn: NS-3 thay testbed Linux; chưa SURGE cross traffic và Limited Slow Start; chỉ hai thuật toán; một seed/case; chưa có biến thiên thống kê. Bài báo có nhiều mức p và thuật toán hơn. Phải công bố những khác biệt này khi đối chiếu, không tuyên bố tái hiện hoàn toàn.
- Thời hạn đã thống nhất trước 00:00 ngày **22/11/2026**. Sau H4 ưu tiên I: kiểm toán tổng thể/đối chiếu paper; J: báo cáo; K: nộp source và dữ liệu phù hợp; L: email + LMS. H5 chưa ưu tiên. Không đưa kết quả chưa chạy vào báo cáo.

**Mốc cuối bản 11:** A–G4 và H1–H3 có minh chứng hoàn thành, H4 chỉ mới thiết kế, I–L chưa hoàn thành. Mọi số liệu thực nghiệm chỉ được lấy từ CSV gốc đã kiểm toán.


---

## 19. H4 – Xác nhận chạy mô phỏng và kiểm toán độc lập (20/11/2026) [ĐÃ XÁC NHẬN]

**Cập nhật trạng thái so với mục 18:** Các mục H4 ghi “dự kiến/chưa chạy” trong bản v11 phản ánh thời điểm lập v11; hiện đã được thay thế bởi kết quả H4 thực tế dưới đây. **Không thay thế/ghi đè dữ liệu H1, H2, H3.**

### 19.1. Nguồn dữ liệu và môi trường thực tế

- File người thực hiện gửi: `step-H4-random-loss.tar.gz`, SHA-256 `37b571e28993fcf9cb6b072fc0dd124675d39c2312e989d18db28b6239fb4f42` (giữ file gốc để đối chiếu).
- `environment.json`: ns-3.44, commit `43dce6710b8df69685e3479c1d33a571dda714ea`, `git_status` trống, `profile=optimized`, tối đa 3 tiến trình.
- SHA-256 `simulation/yeah-experiment.cc` là `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`, **giống H1/H2/H3**, không sửa thư viện `TcpYeah`. SHA-256 script `run_H4.py` là `c77cb78d9ab921a4994e778586473a1bf587e4b4e9bba75d3faf1313f6138c74`.
- Kết quả mô phỏng đã được thực thi trên WSL và lưu trong `results/raw/experiments/h4/`. **Bộ script phân tích sau kiểm toán chưa được sinh viên chạy lại trên WSL** tại thời điểm lập bản v12.

### 19.2. Cấu hình đo (từ manifest + config + summary)

- Hai luồng cùng thuật toán YeAH hoặc NewReno, 500 Mbps bottleneck, RTT1=RTT2=200 ms, buffer ratio 1 (8333 packets), 600 giây/lượt, không đổi access links 1 Gbps.
- Bốn xác suất lỗi cấu hình trên `RateErrorModel(ERROR_UNIT_PACKET)` tại interface nhận bottleneck: `1e-8`, `1e-6`, `1e-5`, `1e-4`; `seed=1`, `run=1`; MSS 1448 byte; `flow2Start=0`, `flow2Stop=600`; `initialCwnd=10`; một lần chạy mỗi cấu hình.
- Đây là mẫu khảo sát rút gọn Figure 5; **không phải** phép tái hiện toàn bộ testbed Linux, chưa có SURGE/limited slow start.

### 19.3. Kiểm toán dữ liệu độc lập [8/8 PASS]

- Có đúng 8 `config.json`, `status.json`, `run.log`, `summary.csv`, `timeseries.csv` khớp manifest và `batch_status.json`.
- Tám lượt đều `status=PASS`, returncode=0, số mẫu mỗi CSV là **60001** với chu kỳ **0,01 giây**; thời điểm chạy từ 0 tới 600 giây.
- SHA-256 của `summary.csv`/`timeseries.csv` khớp trạng thái lưu khi chạy; source/runner khớp mã nguồn hiện hành.
- Các bộ đếm nhận byte, byte truyền bottleneck, mất gói do tràn, mất gói khác, mất gói ngẫu nhiên đều không giảm. Queue nằm trong [0, 8333].
- Tính lại độc lập goodput từng luồng, goodput tổng, goodput/capacity, `wire_utilization`, trung bình queue, queue/buffer, xác suất overflow và Jain; tất cả khớp `summary.csv` trong sai số làm tròn.
- `random_drops` và `bottleneck_drops` cuối của timeseries khớp summary, `other_drops=0` trong tám kịch bản. `wire_packets` là bộ đếm C++ cuối, không có cột từng bước tương đương trong timeseries để kiểm chứng độc lập chi tiết.
- Kết quả thực nghiệm H4 mới có **một lượt chạy mỗi cặp TCP và p**; chưa có thống kê giữa nhiều seed.

### 19.4. Kết quả thực tế H4 (0–600 s) [ĐÃ XÁC NHẬN]

| p cấu hình | TCP | Goodput tổng (Mbps) | Wire utilization (%) | Queue/Buffer (%) | Overflow drops | Random drops | Jain |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1e-08 | YeAH | 469.6020 | 97.4231 | 0.60371 | 228 | 0 | 0.807426 |
| 1e-08 | NewReno | 479.6931 | 99.5166 | 49.81251 | 8337 | 0 | 0.999210 |
| 1e-06 | YeAH | 120.2695 | 24.9510 | 0.11937 | 228 | 7 | 0.944093 |
| 1e-06 | NewReno | 175.2744 | 36.3622 | 2.74824 | 8332 | 9 | 0.998742 |
| 1e-05 | YeAH | 47.3729 | 9.8280 | 0.11849 | 228 | 21 | 0.913193 |
| 1e-05 | NewReno | 51.4839 | 10.6809 | 0.16539 | 8332 | 22 | 0.968149 |
| 1e-04 | YeAH | 13.2948 | 2.7584 | 0.01829 | 0 | 76 | 0.974642 |
| 1e-04 | NewReno | 11.9254 | 2.4743 | 0.01488 | 0 | 65 | 0.988971 |

Các bảng gốc và bảng tính lại: `results/raw/experiments/h4/*/{summary.csv,timeseries.csv}` → `results/summary/h4/h4_summary_verified.csv`, `t4_loss_comparison.csv`, `t4_time_windows.csv`.

### 19.5. Nhận xét sơ bộ và những giới hạn [CHƯA PHẢI KẾT LUẬN PAPER]

- Khi tăng `p`, goodput và wire utilization giảm mạnh ở cả hai thuật toán. Tại `1e-8`, chỉ số này lần lượt gần 97,42% (YeAH) và 99,52% (NewReno), còn tại `1e-4` khoảng 2,76% (YeAH) và 2,47% (NewReno).
- NewReno có goodput cao hơn ở 3 mức lỗi `1e-8`, `1e-6`, `1e-5`; tại `1e-4`, YeAH cao hơn nhưng chỉ trong **một lần chạy**. Không kết luận ý nghĩa thống kê hoặc thuật toán nào vượt trội chung.
- Tại `1e-8`, **0 random drops quan sát được ở cả hai trường hợp**, dù cấu hình `p=1e-8`; đây là kết quả có thể xảy ra với mẫu hữu hạn, không đồng nghĩa tỷ lệ lỗi cấu hình bị đặt bằng 0.
- Các `overflow_drops` **không phải** `random_drops`: ví dụ `p=1e-8` YeAH có 228 queue drops và 0 random drops, NewReno có 8337 queue drops và 0 random drops. Không cộng/đánh đồng khi so sánh xác suất lỗi của Error Model.
- Jain, queue và wire utilization tính cho toàn bộ 600 giây; các chỉ số có thể biến đổi theo thời gian. CSV `t4_time_windows.csv` bổ sung phép đo 0–300 và 300–600 giây.
- Dữ liệu H4 có thể kiểm chứng **nhất quán nội bộ**; chưa kiểm chứng sự tương đương định nghĩa đo của Linux testbed/NS-3 và chưa đối chiếu định lượng với Figure 5 gốc.
- Không sửa dữ liệu để phù hợp xu hướng mong muốn; các đường trong hình là nối bốn điểm p thực sự đã chạy, trục p logarithmic.

### 19.6. Bộ phân tích và đầu ra [ĐÃ THỬ ĐỘC LẬP; WSL CHỜ XÁC NHẬN]

- `scripts/analyze_H4.py` chỉ **đọc** H4 raw, kiểm tra manifest/config/status, hash source và CSV, đọc toàn bộ trace và tính lại các chỉ số.
- Đã chạy script trên bản giải nén độc lập trong môi trường kiểm tra: **8/8 AUDIT PASS**.
- Kết quả `results/summary/h4/`: `h4_summary_verified.csv`, `t4_loss_comparison.csv`, `t4_time_windows.csv`, `h4_audit.json`.
- Kết quả `results/figures/h4/`: 4 biểu đồ (`t4_loss_wire_utilization`, `t4_loss_goodput`, `t4_loss_queue_normalized`, `t4_loss_random_drops`), mỗi hình có PNG 300 DPI và SVG.
- Chưa nhận log `VERIFIED H4: 8/8` từ Ubuntu của sinh viên ở thời điểm ghi nhật ký v12.

### 19.7. Quyết định tiến độ

- H4: mô phỏng và kiểm toán độc lập **hoàn thành**; sinh viên cần chạy `python3 scripts/analyze_H4.py` để xác nhận tái tạo phân tích tại máy.
- **Khóa đề xuất bộ dữ liệu H1–H4 gồm 32 lượt 600 giây** (mỗi cấu hình một lượt); không mở thêm H5 để dành thời gian xác minh toàn bộ, trích thông số paper và viết báo cáo trước deadline.
- **Bước I (chưa thực hiện):** đối chiếu định nghĩa và số liệu paper, chuẩn hóa bảng xuyên H1–H4, rà soát giới hạn theo seed và testbed. **Bước J/K/L (chưa thực hiện):** viết báo cáo, đóng gói source/README/dữ liệu và nộp qua hai kênh.
- Giữ nguyên dữ liệu raw, `run_H*.py` và các script `analyze_H*.py`. Không tuyên bố tái hiện đầy đủ paper hay có thống kê ý nghĩa nhiều lượt.

**Bước tiếp theo:** tái chạy `analyze_H4.py` trên WSL và gửi kết quả terminal; sau đó thực hiện I → J → K → L.


---

## 20. Xác nhận H4 trên WSL và kiểm toán tổng thể I1 (20/11/2026) [ĐÃ XÁC NHẬN]

**Cập nhật so với v12:** Sinh viên đã chạy `python3 scripts/analyze_H4.py` trên WSL và gửi ảnh terminal ghi `VERIFIED H4: 8/8, source and hashes match, metrics recomputed`. Sinh viên mở thành công thư mục `results/figures/h4/`, thấy 4 PNG và 4 SVG.

**Nguồn I1:** Sinh viên đã gửi `step-I1-analysis.tar.gz`, SHA-256 `191de574a2dc7171d929e29c73663de41047c718617128bf763adf5cfacf2e3e`, chứa source C++, các script chạy/phân tích, bốn bộ bảng tổng hợp và hình được tạo trên WSL. Các gói raw H1–H4 đã được gửi ở các bước trước, sử dụng để kiểm chứng lại.

**Kiểm toán độc lập:** Giải nén riêng bốn gói raw, sao chép source và script từ gói I1, thực hiện lần lượt `analyze_H1.py` đến `analyze_H4.py`. Kết quả **8/8 PASS cho mỗi nhóm**, 32 lượt (mỗi lượt 600 giây, 60.001 dòng), tổng 1.920.032 mẫu. **Toàn bộ 12 bảng CSV phân tích tái tạo trùng từng byte** với gói I1. Hash 64 file CSV gốc (32 summary + 32 timeseries) khớp status ghi khi chạy. SHA-256 mã nguồn: `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`, commit NS-3.44: `43dce6710b8df69685e3479c1d33a571dda714ea`.

**Kiểm tra lại source và độ đo:** Bốn script phân tích chạy từ raw và tính lại goodput, link utilization, queue và Jain; các số liệu phù hợp trong giới hạn làm tròn. Bộ script `scripts/audit_I1.py` được tạo để người thực hiện kiểm toán ngang toàn bộ 32 lượt ở WSL và xuất `results/summary/i1/i1_master_summary.csv`. Đã thử thành công trên bản sao dữ liệu độc lập; **chưa có log chạy trên máy sinh viên**.

**Hình:** Kiểm đếm 20 PNG + 20 SVG. Kết quả render không trùng byte với các file ảnh ở bản phân tích trước đây (kích thước có khác biệt nhỏ), có thể do phiên bản/font Matplotlib; do đó tuyệt đối không nhận định ảnh có hash giống nhau. Tính đúng đắn của dữ liệu vẽ được chứng minh bằng mã script đã chạy lại và CSV đầu vào/đầu ra đã kiểm toán.

**Khác biệt paper đã quan sát cần đưa vào I2:** Table I paper gốc ở trang in 40 báo không quan sát thấy overflow cho YeAH ở RTT 15/60/240 ms; H1 NS-3 ghi lần lượt 412 / 1.968 / 6.581 lần. Reno tương ứng 736 / 2.508 / 10.003 lần. Không so số đếm trực tiếp với xác suất trong paper. Bước I2 sẽ tính xác suất theo mẫu số của source NS-3 và xác định giới hạn so sánh. Paper gốc chạy Linux với SURGE/limited slow start và ≥3 lượt/điểm, còn thực nghiệm NS-3 của chúng ta có một lượt/điểm, không có SURGE hoặc limited slow start.

**Trạng thái cuối bản 13:** A–G4, H1–H4 và I1 hoàn thành trong phạm vi kiểm toán. I2 (so sánh paper), J (báo cáo), K (đóng gói), L (nộp hai kênh) chưa thực hiện. Tiếp tục không thay đổi raw và không tạo số liệu không có nguồn.

---

## 21. I1 – Sinh viên xác nhận chạy lại kiểm toán trên WSL [ĐÃ XÁC NHẬN]

Ngày 20/11/2026, sinh viên cung cấp log terminal:

```text
VERIFIED I1: 32/32; raw hashes and metrics match; 20 PNG + 20 SVG
OUTPUT: /home/hung/projects/YeAH-TCP-NPE/results/summary/i1
```

**Trạng thái:** I1 đã hoàn thành cả kiểm toán độc lập trên bản sao gốc lẫn việc chạy lại script trên WSL của sinh viên. 32 lượt chạy H1–H4 và 12 bảng tổng hợp, 20 PNG + 20 SVG vẫn giữ nguyên. Không yêu cầu chạy lại mô phỏng.

## 22. I2 – Chuẩn bị công cụ đối chiếu với paper [CHƯA XÁC NHẬN TRÊN WSL]

### 22.1. Nguồn tham chiếu đã đọc trực tiếp

- PDF gốc `4-YeAH_TCP.pdf` (SHA-256 `7ebc75ce34aa58ff40e8c6a8eff4783d8a4403aece3a50d7912458c834228b4f`).
- Baiocchi, Castellani, Vacirca, *YeAH-TCP: Yet Another Highspeed TCP*, PFLDnet 2007, Table I trang in 40 (PDF trang 4), Fig 1 trang in 39, Fig 3 trang in 40, Fig 5–7 trang in 41.
- Table I: Reno xác suất tràn: RTT 15 ms = 0.0000057686, 60 ms = 0.0000050669, 240 ms = 0.0000009400. Dấu `–` của YeAH cho cả ba RTT có nghĩa **không quan sát được gói tràn**, không được biến thành số xác suất 0 chính xác.
- Paper nói rõ mô hình vật lý Linux 2.6.16.2, đường bottleneck C=500 Mbps, access 1 Gbps, packet data 1500 byte, phương pháp đo 600 s và trung bình ít nhất ba lần đo. Testbed được mô tả có SURGE web traffic trung bình 4 Mbps và Limited Slow Start; mô tả không đủ để xác nhận chính xác tất cả lưu lượng phụ hiện diện trong mọi hình.

### 22.2. Công cụ được chuẩn bị

- `scripts/compare_I2.py` so sánh `results/summary/i1/i1_master_summary.csv` với `refs/paper_table_I_2007.csv`, khóa bằng SHA-256 của source C++, bảng I1 và bảng paper.
- Script đã được **thực thi và cho PASS trên bản sao độc lập của I1 master** (32 dòng), tạo sáu kết quả `results/summary/i2/` và tài liệu phân tích `docs/I2_doi_chieu_paper_generated.md`.
- **Chưa có log chạy I2 trên WSL của sinh viên**, chưa chốt I2 chính thức và chưa viết báo cáo hoàn chỉnh.

### 22.3. Khác biệt đã xuất hiện từ đối chiếu tự động [KẾT QUẢ SƠ BỘ CÓ CĂN CỨ]

- Table I: ở NS-3, YeAH có overflow 412 (RTT15), 1968 (RTT60), 6581 (RTT240), khác việc *không thấy gói tràn* ở paper; NewReno lần lượt 736, 2508, 10003. Các xác suất NS-3 lấy từ công thức thực sự trong source `overflow/(accepted+overflow)`, không khẳng định cùng mẫu số với paper.
- Figure 3: YeAH có queue/buffer thấp hơn NewReno tại ba RTT đo được trong H1; cần diễn giải trong giới hạn các lượt chạy thực tế.
- Figure 6: tỷ lệ queue/buffer của YeAH trong H2 tăng theo bốn mức buffer từ 12,5% tới 100% BDP, khác lời mô tả xu hướng giảm trong paper. Không sửa giá trị để làm khớp paper.
- Figure 7: YeAH có Jain cao hơn NewReno tại tỷ số RTT 2/3/4 trong H3, nhưng không đồng nghĩa chứng minh RTT fairness tổng quát và mới một lần chạy/cấu hình.
- Figure 5: tại bốn mức p đo được, YeAH vượt NewReno về wire utilization chỉ ở p=1e-4. Các đường được paper vẽ không có bảng số chính xác trong phần văn bản nên chưa đối chiếu giá trị điểm-một-điểm định lượng.
- Source mô phỏng sử dụng MSS=1448, không mô phỏng SURGE/limited slow start; Linux testbed và ns-3 không hoàn toàn đồng nhất; chỉ một run=1/seed=1 mỗi cấu hình. Chưa có khoảng tin cậy thống kê.

**Bước tiếp theo:** sinh viên chạy `python3 scripts/compare_I2.py` từ `I2_comparison_package.zip` và gửi log. Nếu đạt, khóa kết quả đối chiếu rồi chuyển sang J: viết báo cáo theo sáu yêu cầu của giảng viên, K: nộp source/README và dữ liệu chọn lọc, L: nộp email và LMS trước 00:00 22/11/2026.


---

## 23. I2 – Xác nhận đối chiếu trên WSL và J1 – Bản thảo Word [20/11/2026]

### 23.1. I2 đã được người thực hiện xác nhận [ĐÃ XÁC NHẬN]

Người thực hiện cung cấp log terminal thực tế:

```text
VERIFIED I2: 32 I1 records linked; Table I 6 published comparisons; Figs 3/5/6/7 measured points derived
OUTPUT: /home/hung/projects/YeAH-TCP-NPE/results/summary/i2
NOTES: /home/hung/projects/YeAH-TCP-NPE/docs/I2_doi_chieu_paper_generated.md
```

Điều này xác nhận **bộ so sánh I2 chạy thành công trên Ubuntu WSL**. Mốc I2 được đóng trong phạm vi kiểm toán liên kết 32 lượt từ I1, bảng Table I (6 trường hợp so sánh: Reno có ba xác suất công bố chính xác, YeAH có ba dấu “–”) và các điểm đo đã có ở Figure 3/5/6/7. Không suy ra số liệu số chính xác từ nét đồ thị paper.

### 23.2. J1 – Tạo báo cáo Word bản nháp [ĐÃ TẠO; CHƯA CHỐT]

- Bản thảo `report/Bao_cao_YeAH_TCP_BAN_NHAP_J1.docx` đã được sinh bằng `scripts/generate_report_J1.py` từ bảng I1, I2 và 8 biểu đồ H1–H4 thực tế, không tự tạo số đo.
- Script kiểm tra nguồn `simulation/yeah-experiment.cc` trùng hash của toàn bộ 32 lượt (`460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`), bảo toàn 32 kịch bản × 60001 mẫu và kiểm tra I2 → I1 bằng hash summary trước khi xuất báo cáo.
- Báo cáo có sáu nội dung theo đề bài, 10 bảng và 8 hình từ script phân tích, tách rõ kết quả NS-3, giá trị Table I paper, dấu không ghi nhận overflow, các giới hạn định nghĩa và chỉ một seed/run.
- Thông tin cá nhân trên bìa vẫn để `[BỔ SUNG]`; bản thảo chưa được người thực hiện đọc và duyệt, chưa phải hồ sơ nộp cuối cùng.
- Chưa tạo PDF nộp, chưa đóng gói source/dữ liệu/README bản cuối; chưa nộp email và LMS.

**Hành động kế tiếp:** người thực hiện xem Word bản nháp J1, kiểm tra tên đề tài, điền bìa, kiểm tra trực quan các bảng/hình và phản hồi. Sau đó hoàn thiện bản báo cáo cuối, chuẩn bị README, gói nguồn và hồ sơ nộp. Không sửa raw H1–H4.


---

# Bổ sung v16 – K0 (21/11/2026): khóa gói rà soát trước J2

- Đầu vào: `YeAH-TCP-NPE-K0-review.tar.gz`, do người thực hiện gửi; bản kiểm tra giải nén riêng, không thay đổi gói gốc.
- SHA-256 gói K0: `cabe85d4c2acf5c7f4a433e2e4c975daf13a764c4cad3d0ce79f8812945ded19`.
- SHA-256 C++: `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`.
- Đối chiếu 44 mục file/gói H1, H2, H3, H4 (176 lượt đối chiếu, bao gồm bản sao source lặp): không có sai khác so với các gói raw đã gửi.
- Chạy `python3 scripts/audit_I1.py --project /mnt/data/K0_review`: 32/32 PASS, 64 hash raw, 20 PNG + 20 SVG; master I1 SHA-256 `3f7b0aa9f07d5b69770825decb35cee641b5ce1a77f0f52bca68407c6936400b`.
- Sáu script analyze_H1–H4, audit_I1 và compare_I2 trùng bytes script trong các gói phân tích trước đây.
- Thiếu `refs/paper_table_I_2007.csv` trong K0 (lệnh tar không bao gồm refs); `compare_I2.py` trực tiếp báo Missing input. Đã bổ sung đúng bytes từ I2_comparison_package.zip trong bản sao kiểm tra, chạy I2 thành công, không đổi các đầu ra. Giá trị Reno Table I đã đối chiếu văn bản PDF: 0.0000057686, 0.0000050669, 0.0000009400; dấu gạch ngang YeAH nghĩa là không quan sát mất gói trong thực nghiệm paper.
- Thiếu `scripts/generate_report_J1.py`, README_J1.md; report/ và configs/ rỗng trong archive. Cấu hình thực tế nằm trong manifest.json/config.json của raw H1–H4. Bổ sung script/README nguyên bản từ J1_report_reproducibility.zip vào bản sao kiểm tra. Đây không phải thay đổi mô phỏng.
- Chạy lại analyze_H1–H4 độc lập: từng nhóm 8/8 PASS. 18 CSV tổng hợp (12 H1–H4, 1 I1, 5 I2) và các file kiểm toán giữ nguyên SHA-256 so với K0 ban đầu. Lần gọi audit_I1 bổ sung sau tái tạo bốn nhóm bị timeout của môi trường kiểm tra, nhưng lần audit_I1 đầy đủ trước đó đã PASS, master và các file tổng hợp không đổi. Không tuyên bố tái chạy lần audit bổ sung hoàn tất.
- Chạy lại generate_report_J1.py từ bản K0 đã bổ sung: sinh Word, 32 trường hợp, 1.920.032 mẫu; nội dung đoạn văn và 10 bảng trùng khớp J1 đã cung cấp, 8 hình nhúng ở mỗi bản. Không yêu cầu ảnh hoặc DOCX trùng hash nhị phân giữa môi trường; chưa kiểm tra đồng nhất pixel ở lần K0 này. Không dùng bản Word tái tạo làm bản nộp.
- Các file `:Zone.Identifier` trong docs là metadata phụ; loại khỏi gói nộp sau cùng, không xóa dữ liệu gốc. README cuối, requirements, bìa/mục lục và bản PDF chưa hoàn thiện.
- K0 đạt yêu cầu về dữ liệu chính thức và đủ căn cứ bắt đầu J2; file bổ sung cần đưa vào project, chưa được xác nhận trên WSL. Không mở rộng thí nghiệm. J2 rà soát nhận định, công thức, đối chiếu paper; không đổi dữ liệu raw và mã nguồn C++ đã khóa.


## Bản 17 — K0 xác nhận trên WSL; J2.1 rà soát khoa học

- Minh chứng người dùng: `VERIFIED I2: 32 I1 records linked; Table I 6 published comparisons; Figs 3/5/6/7 measured points derived`; `REPORT: /home/hung/projects/YeAH-TCP-NPE/report/Bao_cao_YeAH_TCP_BAN_NHAP_J1.docx`; `SOURCE_SHA256: 460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`; `SCENARIOS: 32 TOTAL_SAMPLES: 1920032`. Xác nhận bổ sung K0 thành công.
- Đã đọc trực tiếp 4-YeAH_TCP.pdf, Section I–III (tr. 37–39 in trên paper), Word J1 và K0/docs/tcp-yeah-source-review.txt, simulation/yeah-experiment.cc.
- Phần 1: giữ nguyên nội dung nền; sửa mục tiêu 2 theo paper (áp lực mạng không lớn hơn Reno); nêu rõ mục tiêu thiết kế không phải kết quả chứng minh.
- Phần 2: bổ sung điều kiện Fast Q<Qmax và L<1/phi; công thức (1), đơn vị, Q theo luồng; quy tắc giảm tải trước mất gói, countReno/countFast, công thức giảm cwnd khi ba ACK trùng lặp. Phân biệt Slow Mode và Slow Start.
- Đối chiếu implementation: tcp-yeah.cc dòng 33–72 (default), 138–155 (RTT), 197–250 (Fast/Slow, m_cntRtt>2, Q ép uint32_t), 252–259 (giới hạn giảm, ssthresh=cwnd mới), 266–287 (reset m_renoCount=2), 310–337 (bytesInFlight và Rho); tcp-yeah.h dòng 158 (uint32_t m_phy). Phép chia nguyên và dấu so sánh tại biên khác paper; chưa chứng minh tác động đến hiệu năng. Không sửa upstream.
- Tạo scripts/generate_report_J2_1.py từ J1, chạy trên bản sao K0, xuất Bao_cao_YeAH_TCP_J2_1.docx. Kiểm tra nội dung đoạn văn từ phần 3 trở đi, 9 bảng còn lại, 8 file ảnh nhúng: trùng với J1 tái tạo trên cùng đầu vào K0. Ảnh nhúng trong J1 ban đầu có thể khác hash nhị phân so với hình xuất trên WSL; không tuyên bố trùng byte giữa các môi trường.
- Không sửa CSV gốc, mã mô phỏng hay số liệu; phần 3–6 chưa được rà soát khoa học J2.2/J2.3. Bìa/mục lục/phụ lục hướng dẫn sẽ hoàn thiện J3.
- Trạng thái: J2.1 đã rà soát và tạo bản nháp riêng trong môi trường kiểm tra; chờ người dùng tạo lại trên WSL. Câu lệnh: `python3 scripts/generate_report_J2_1.py`.


---

## Bản 18 — J2.1 xác nhận trên WSL, J2.2 rà soát mô hình/độ đo/kiểm chứng (21/11/2026)

### Xác nhận từ WSL [ĐÃ XÁC NHẬN]

Người thực hiện đã chạy `python3 scripts/generate_report_J2_1.py`, terminal trả về:

```
REPORT: /home/hung/projects/YeAH-TCP-NPE/report/Bao_cao_YeAH_TCP_J2_1.docx
SOURCE_SHA256: 460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969
SCENARIOS: 32 TOTAL_SAMPLES: 1920032
```

J2.1 được xác nhận tạo thành công trên WSL. Đây là log sinh tài liệu, không thay thế bài kiểm toán khoa học phần 3–4.

### Căn cứ đối chiếu J2.2 [ĐÃ KIỂM TRA TRÊN BẢN SAO K0]

- Mở chính bản Word `Bao_cao_YeAH_TCP_J2_1.docx` và `simulation/yeah-experiment.cc` khớp hash khóa `460600ee...5969`, kèm toàn bộ 32 `summary.csv` và `timeseries.csv` và bảng master I1.
- Source dòng 137–148: seed/run, công thức buffer, kích thước socket 64 MiB, MSS/initial cwnd/initial ssthresh. Dòng 149–152: WindowScaling/Timestamp/SACK/Delayed ACK; dòng 154–177: bốn node, access 1 Gbps, bottleneck 500 Mbps, trễ danh định và DropTail. Dòng 182–214: cấu hình qdisc, trace queue/PhyTxBegin, Error Model tại receiver. Dòng 216–257: thời gian đo, BulkSend/PacketSink, mẫu và công thức tổng hợp.
- 32 file summary.csv có `queue_samples=60000` nhưng mỗi timeseries.csv có 60001 mẫu (mốc cuối chỉ để ghi bộ đếm), không phải lỗi dữ liệu. 32/32 `max_wire_packet_bytes=1502`, trong khi MSS = 1448 và MTU được đặt 1500. Byte tại `PhyTxBegin` không được đồng nhất với payload nhận tại PacketSink hoặc byte vật lý hoàn chỉnh có preamble.
- `tests/tcp-yeah-unit-test.log` báo 1/1 **test suite** PASS; không dùng kết quả upstream unit test để khẳng định thực nghiệm trùng paper. G1/G2/G3/G4 và H1–H4 có minh chứng độc lập trong các gói đã kiểm toán.
- T0: ứng dụng luồng thứ hai bắt đầu tại t = 60 s, ngừng ứng dụng tại 400 s tính từ mốc đo, nhưng dữ liệu đang trong buffer có thể được nhận sau đó. Jain tính trên 600 s không đánh giá chính xác fairness trong thời gian hai luồng cùng hoạt động.

### Nội dung thay đổi [ĐÃ TẠO BẢN J2.2 TRONG MÔI TRƯỜNG KIỂM TRA]

- Bổ sung chi tiết Topology và RTT mục tiêu, giới hạn queue access/bottleneck.
- Viết rõ nguồn từng bộ đếm: goodput từ PacketSink, utilization từ PhyTxBegin, queue từ DropTail, drop tại queue/RateErrorModel, Jain từ goodput của đúng cửa sổ đo.
- Phân biệt 60.001 mẫu CSV với 60.000 mẫu tính queue mean; phân biệt queue cực đại lấy mẫu với cực đại tuyệt đối.
- Mô tả minh bạch buffer TCP 64 MiB, initial ssthresh UINT32_MAX, MSS 1448, timestamp/SACK/window scale; mô hình không tái hiện SURGE và Limited Slow Start.
- Làm rõ khả năng chứng minh của upstream unit test và các bước G; ghi nhận một lần chạy mỗi cấu hình và chưa có kiểm định thống kê.

### Kiểm tra không làm đổi kết quả [ĐÃ THỰC HIỆN]

- Script `scripts/generate_report_J2_2.py` đọc Word J2.1 đã có, kiểm tra SHA-256 của source, 32 ID master I1 và hash của 64 CSV raw, kiểm tra cấu hình MSS/cwnd/seed/run/duration cùng 60000 queue samples và 1502 max frame bytes, rồi chỉ sửa văn bản phần 3–4.
- Đã chạy thành công trên bản sao K0: source hash đúng, 32 trường hợp và 1.920.032 mẫu. Tất cả 10 bảng và cả 8 ảnh nhúng trùng chính xác với Word J2.1. Nội dung phần 1–2 và phần 5–6 được giữ nguyên.
- Bản DOCX J2.2 đã được render thành 13 trang và kiểm tra bố cục; vẫn là **bản rà soát**, chưa phải bản nộp cuối. Chưa cập nhật mục lục có số trang hoặc thông tin bìa.
- **Chưa có log chạy `generate_report_J2_2.py` trên WSL của sinh viên.** Không tuyên bố đã xác nhận mốc đó trước khi nhận log.

### Trạng thái và bước kế tiếp

Dữ liệu mô phỏng gốc được bảo toàn, không sửa upstream NS-3.44. J2.2 sẵn sàng tái tạo trên WSL. Sau khi nhận log, tiến hành J2.3 rà soát phần 5–6 và hoàn thiện nộp bài; không mở rộng thí nghiệm nếu không bắt buộc.

---

## J2.3 – Rà soát kết quả thực nghiệm và đối chiếu paper (21/11/2026)

**Đầu vào:** báo cáo J2.2, 32 lượt raw H1–H4 đã khóa, I1 master, I2 Table I, paper YeAH-TCP 2007 và mã C++ SHA-256 `460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969`.

**Phương pháp:** dùng `scripts/generate_report_J2_3.py` kiểm tra hash 64 CSV raw, liên kết I2 với I1, kiểm tra lại các con số và chiều so sánh xuất hiện trong phần nhận xét rồi chỉnh 12 đoạn diễn giải của phần 5–6. Không sửa raw, bảng, ảnh, source C++ hoặc nội dung phần 1–4.

**Kết quả kiểm tra trên bản sao dữ liệu:** `J2.3 VERIFIED: 12 science revisions, 10 tables and 8 images unchanged; 64 raw CSV hashes match`.

**Điểm khoa học cần giữ nguyên:**
- RTT 15 ms: queue YeAH vẫn chiếm ~70,99% buffer, mặc dù thấp hơn NewReno; không gọi là hàng đợi tuyệt đối nhỏ.
- RTT 240 ms: queue trung bình lấy mẫu thấp nhưng overflow vẫn cao; chưa suy diễn nguyên nhân khi chưa phân tích theo sự kiện.
- T2: queue/buffer YeAH tăng theo 4 mức beta quan sát, ngược xu hướng nêu ở Figure 6 paper; giữ nguyên số liệu.
- T3: Jain theo toàn kỳ và theo cửa sổ 300–600 giây có thể khác thứ hạng; một run nên không có kiểm định thống kê.
- T4: 0 random drop quan sát ở p=10^-8 không phải xác suất lỗi thật bằng 0.
- Table I: dấu “–” nghĩa không phát hiện overflow trên testbed paper, không phải tỷ lệ bằng 0; không so như phép đo thống kê đồng nhất.

**Bố cục:** render DOCX J2.3 thành 13 trang; bỏ trang trắng do đoạn page-break dư trước T3 (không sửa dữ liệu).

**Trạng thái:** J2.3 đã rà soát trên bản sao dữ liệu trong môi trường kiểm tra; **chờ xác nhận tạo lại Word bằng script trên WSL**. Chưa là báo cáo cuối vì còn bìa, mục lục, README và gói mã nguồn nộp cuối.


---

## Bổ sung v20 – 21/11/2026: xác nhận J2.3 trên WSL và chuẩn bị J3

**Dữ liệu do người thực hiện gửi từ terminal (đã quan sát):**

```
REPORT: /home/hung/projects/YeAH-TCP-NPE/report/Bao_cao_YeAH_TCP_J2_3.docx
SOURCE_SHA256: 460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969
SCENARIOS: 32 TOTAL_SAMPLES: 1920032
J2.3 VERIFIED: 12 science revisions, 10 tables and 8 images unchanged; 64 raw CSV hashes match
SCOPE: sections 5-6 revised; sections 1-4 and references/appendix unchanged
```

**Xác nhận:** Bước J2.3 được tạo thành công và báo cáo kiểm chứng đạt trên WSL của người thực hiện; không có yêu cầu chạy lại H1–H4.

**Chuẩn bị bước J3:** Script `scripts/finalize_report_J3.py` đã được chạy kiểm thử trên bản sao project K0 và bản J2.3 hiện có; xác nhận 32 kịch bản, 64 hash raw CSV, giữ nguyên phần nội dung khoa học, 10 bảng, 8 hình. Bản nháp trình bày đã xuất thử thành 14 trang trên môi trường kiểm tra, có trang bìa riêng và mục lục 8 mục với trường số trang `PAGEREF`.

**Chưa được xác nhận:** Thông tin sinh viên, MSSV, lớp, giảng viên; bản Word J3 trên WSL người thực hiện; tính tương thích số trang trong Microsoft Word của người thực hiện; bản PDF cuối; sự hoàn thiện hồ sơ source + README; việc nộp. Không dùng bản nháp J3 làm bản nộp cho đến khi hoàn thành các đầu mục này.

**Giới hạn:** J3 là chỉnh sửa hình thức; các diễn giải và nội dung khoa học đã rà soát J2.3 được giữ nguyên. Không ghi nhận thêm lượt mô phỏng hoặc kết quả mới.
