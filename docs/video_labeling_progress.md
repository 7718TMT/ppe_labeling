# Kế hoạch tối ưu video inference và labeling

Ngày lập kế hoạch: 2026-08-25. Tài liệu này chỉ mô tả công việc cần làm; chưa
thay đổi hành vi xử lý hiện tại.

## Cập nhật triển khai — 2026-08-25

- Hoàn thành phần observability trực tiếp: worker log stage start/finish, thời
  lượng, canonical frame/s, resolution, track count và resolved device.
- Hoàn thành P1: canonicalization decode tuần tự theo mapping, không còn
  seek-per-output-frame.
- Hoàn thành phần P2 không làm thay đổi quality profile: `INFERENCE_DEVICE`
  được truyền vào `YOLO.track`.
- Có benchmark riêng cho canonical stage:
  `uv run python -m backend.scripts.benchmark_canonicalization <video.mp4>`.
- P2 quality-profile benchmarking và P3 PPE/Sign background-job API/UI vẫn là
  công việc độc lập, chưa triển khai trong thay đổi này.

## Phát hiện đã xác nhận

- Video Behavior đang chạy `canonicalize` trước Pose, feature, và model
  inference. Với video `cong-truoc.mp4` 1080p H.264 dài 280.1 giây (6,722
  frame canonical), job vẫn ở `canonicalize` sau hơn 20 phút.
- `VideoWorker._canonicalize` gọi `cv2.VideoCapture.set(CAP_PROP_POS_FRAMES,
  ...)` gần như ở mỗi frame. Seek lặp lại trên H.264 làm decoder quay về
  keyframe nhiều lần, nên phần lớn thời gian là chờ decode/I/O thay vì dùng
  CPU/GPU.
- Pose hiện gọi `YOLO.track` mà không truyền device đã resolve từ
  `INFERENCE_DEVICE`. Tracker còn bật external ReID và sparse optical flow;
  đây là chi phí có chủ đích cần đo trước khi thay đổi chất lượng tracking.
- PPE/Sign không sử dụng canonicalize, Pose, hay SQLite video worker. Với
  video, chúng xử lý đồng bộ trong request: decode tuần tự -> YOLO từng frame
  -> vẽ box -> encode MP4 tạm bằng OpenCV -> encode H.264 lần nữa bằng FFmpeg.
  Vì batch một frame và có decode/encode xen kẽ, GPU vẫn có thể thấp.

## Phạm vi và nguyên tắc

- Giữ nguyên canonical timeline 24 FPS, mapping frame, output API, và kết quả
  inference về mặt ngữ nghĩa trừ khi một thay đổi được ghi rõ và có migration.
- Không tăng `VIDEO_WORKER_CONCURRENCY` để chữa một video chậm. Concurrency chỉ
  tăng throughput của nhiều video và có thể làm tranh chấp GPU/CPU.
- Giữ các artifact theo kiểu atomic write/replace; job fail không được công bố
  file canonical hoặc result dở dang.
- Tách benchmark theo stage: upload, canonicalize, pose_track, features, model,
  PPE/Sign decode+detect, PPE/Sign encode. Không dùng CPU/GPU utilization đơn
  thuần làm tiêu chí thành công.

## Kế hoạch triển khai

### P0 — Đo baseline và observability

1. Thêm log/metric thời lượng, tổng frame, frame/giây, input resolution và
   resolved device cho từng job stage. Ghi mốc thời gian khi stage bắt đầu/kết
   thúc; không log mỗi frame.
2. Tạo benchmark script hoặc test integration dùng clip fixture nhỏ và một clip
   representative 1080p, đo riêng canonicalize/Pose/encode.
3. Kiểm tra vận hành: chỉ chạy một launcher/worker mong muốn, và ghi rõ lệnh
   start/stop. Hiện máy local đang có hai API và hai video-worker process; cần
   tránh benchmark trong trạng thái này.

**Nghiệm thu:** có thể trả lời chính xác stage nào chiếm thời gian và FPS của
stage đó từ log/job history.

### P1 — Sửa canonicalization của Video Labeling và Behavior

1. Thay vòng lặp random seek bằng decode tuần tự một lần:
   - vì `canonical_frame_mapping` tăng đơn điệu, đọc source frame liên tiếp đến
     `original_frame` yêu cầu;
   - ghi cùng frame source nhiều lần nếu mapping yêu cầu duplicate;
   - không gọi `capture.set` trong loop hot path.
2. Giữ progress, pause/cancel checks, file tạm và `os.replace` như hiện tại.
3. Cân nhắc FFmpeg canonicalization chỉ sau khi implementation tuần tự có
   benchmark. Nếu dùng FFmpeg phải chứng minh output mapping khớp rule
   `canonical_frame_mapping`, không chỉ khớp duration.
4. Thêm test cho input 30→24 FPS, input dưới 24 FPS có duplicate frame, và lỗi
   decode giữa chừng không làm lộ output partial.

**Nghiệm thu:** frame count/mapping không đổi; không còn seek-per-frame; clip
1080p baseline nhanh hơn rõ rệt, với báo cáo thời gian trước/sau trên cùng máy.

### P2 — Làm rõ và tối ưu Pose/Tracking có kiểm soát

1. Truyền resolved inference device vào `VideoWorker` và `YOLO.track`.
2. Log device thực tế và xác minh bằng CUDA availability/model execution; fail
   hoặc cảnh báo rõ khi cấu hình yêu cầu CUDA nhưng không dùng được.
3. Đưa `imgsz`, ReID và `gmc_method` thành các cấu hình versioned của project
   hoặc profile, giữ mặc định chất lượng hiện tại.
4. Benchmark ít nhất hai profile: current dedicated ReID và profile nhanh hơn.
   So sánh ID switches, track coverage, keypoint confidence, event output và
   tốc độ trước khi đổi default.
5. Chỉ thử batch/stream optimization nếu Ultralytics tracker giữ đúng ID qua
   frames; không batch mù quáng làm mất `persist=True` semantics.

**Nghiệm thu:** CUDA được dùng khi `INFERENCE_DEVICE=cuda:*` hợp lệ; profile
nhanh chỉ được bật khi quality benchmark đạt ngưỡng đã thống nhất.

### P3 — PPE/Sign video inference

1. Giữ image inference synchronous như hiện tại. Với video, tách xử lý nặng ra
   background job có trạng thái/progress để HTTP upload không bị giữ đến hết
   video; thiết kế endpoint/status và UI polling/SSE trước khi implement.
2. Bỏ double encode nếu benchmark xác nhận: pipe rendered BGR frames vào một
   FFmpeg H.264 process thay vì OpenCV `mp4v` rồi FFmpeg encode lại. Bảo toàn
   audio optional và browser-compatible MP4.
3. Thêm progress theo frame, cancellation/cleanup, và giới hạn số video job
   đồng thời để không tranh GPU với pose worker.
4. Benchmark detector theo `imgsz`, nhưng không tự giảm resolution/default
   confidence nếu chưa kiểm tra mAP/recall PPE và Sign.

**Nghiệm thu:** upload trả về sau khi persist source và tạo job; result chỉ
xuất hiện khi complete; output vẫn có audio (nếu input có), box đúng, và phát
được trên browser.

### P4 — Vận hành, regression và rollout

1. Chạy unit/integration tests liên quan, video smoke test trên GPU và CPU,
   kiểm tra artifact cleanup khi cancel/fail.
2. So sánh before/after bằng cùng video 1080p; lưu thời gian stage và FPS vào
   tài liệu release/operations.
3. Rollout P1 trước, đo lại; sau đó P2 và P3 là thay đổi độc lập. Không gộp
   toàn bộ tối ưu vào một PR nếu không thể phân biệt regression.

## Thứ tự đề xuất cho prompt triển khai tiếp theo

1. P0 instrumentation tối thiểu + P1 sequential canonicalization và tests.
2. Xác minh benchmark, rồi P2 device propagation.
3. Thiết kế API/background job PPE/Sign trước khi bắt đầu P3.
