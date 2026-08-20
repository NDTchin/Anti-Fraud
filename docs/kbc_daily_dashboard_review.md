# Review Dashboard `kbc_daily_dashboard.py`

Tài liệu này đánh giá dashboard trong [kbc_daily_dashboard.py](/D:/VSF/src/dashboard/kbc_daily_dashboard.py) theo logic `ride` mới nhất, với mục tiêu:

- người vận hành đọc được
- analyst đọc đúng ý nghĩa số liệu
- dashboard không vô tình truyền tải thông điệp sai về mức độ flag

## Dashboard này đang dùng để làm gì?

Nếu bỏ qua chi tiết kỹ thuật, dashboard này được dùng để trả lời 3 câu hỏi:

1. Hôm nay cặp `tài xế - khách hàng` nào cần xem trước?
2. Hệ thống đang nghi họ vì lý do gì?
3. Có những `order` nào cần mở ra để đối chiếu nghiệp vụ?

Với logic mới, cần nhớ:

- hệ thống phát hiện ở cấp `pair`
- dashboard cho phép drill xuống cấp `order`
- network chỉ là tăng bổ sung để mở rộng điều tra

## Phạm vi đánh giá

Dashboard hiện tại đọc chủ yếu từ:

- [flagged_orders.parquet](/D:/VSF/reports/task3/flagged_orders.parquet)
- [kbc_pair_summary.csv](/D:/VSF/reports/task3/kbc_pair_summary.csv)
- [kbc_pair_reasons.csv](/D:/VSF/reports/task3/kbc_pair_reasons.csv)

Cần đọc dashboard với 2 lưu ý cơ bản:

- đây là tập đã bị flag, không phải toàn bộ order universe
- một order có thể xuất hiện nhiều dòng nếu trùng nhiều `reason_code`

## Tóm tắt điều hành

Dashboard hiện tại đã có nền tảng tốt cho việc theo dõi fraud hàng ngày:

- có KPI tổng quan
- có bảng pair-level
- có đường xuống order-level
- có thông tin về rule, risk tier, service, province

Tuy vậy, để đồng bộ với luồng `ride` mới, dashboard notes và cách trình bày nên sửa theo 5 hướng:

1. Tách rõ `flag rows` và `unique flagged orders`
2. Đổi language từ "hệ thống bắt fraud" sang "hệ thống tìm case đáng nghi"
3. Làm rõ pair evidence là trung tâm
4. Giữ network dùng vai trò bổ sung
5. Giảm khả năng lộ logic nhạy cảm cho role không cần biết quá sâu

## Góc nhìn 1: Người dùng cuối

### Điểm tốt

- Dashboard có bố cục để theo dõi nhanh tình hình trong ngày
- Người dùng có thể đi từ KPI tổng quan xuống case cụ thể
- Các trường business rule, risk tier, service và province hữu ích cho vận hành

### Điểm cần sửa

- KPI tổng đơn rất dễ bị hiểu nhầm thành tổng đơn của hệ thống
- Nếu không tách `flag rows` và `unique orders`, người đọc sẽ sai ngay từ con số đầu tiên
- Nếu vẫn dùng language cũ, dashboard có thể tạo cảm giác hệ thống đang flag quá rộng, trong khi logic mới đã được siết lại

### Khuyến nghị

- Đổi tên KPI thành:
  - `Flag Rows`
  - `Unique Flagged Orders`
- Thêm ghi chú ngắn gọn KPI:
  - `Một order có thể trùng nhiều reason_code`
- Nếu có cho hiện note tổng quan, nên ghi rõ:
  - `Hệ thống ưu tiên cấp tài xế - khách hàng đáng nghi, sau đó mới đưa order ra review`

## Góc nhìn 2: Data Analyst

### Điểm tốt

- Đã có dữ liệu ở 3 cấp để analyst làm việc:
  - pair
  - pair reason
  - order
- Đã có 3 lớp điểm rõ ràng:
  - `pair_core_score`
  - `network_support_score`
  - `priority_score`

### Điểm cần sửa

- Dashboard review cũ dễ analyst đọc nhầm `flag rows` thành `unique orders`
- Nếu analyst vẫn hiểu `SUPERFAST_GAP` theo logic cũ, sẽ đánh giá quá mạnh temporal evidence
- Chưa nhấn mạnh đủ rằng network support là tăng hỗ trợ, không phải bộ detector đầu tiên

### Khuyến nghị

- Ở phần notes hoặc data dictionary, ghi rõ:
  - `pair` là đơn vị phát hiện
  - `order` là đơn vị materialize để review
  - `component` là đơn vị mở rộng điều tra
- Nếu hiện top reasons, nên ghi kèm định nghĩa operational mới:
  - `SUPERFAST_GAP` chỉ hợp lệ khi gap không âm, đủ số trip, và có ghost support tối thiểu
- Nếu hiện `high_confidence`, nên ghi rõ label này đã được siết lại

## Góc nhìn 3: Anti-fraud / Security

### Dashboard đang lộ những gì

Nếu không phân quyền phù hợp, dashboard có thể lộ quá nhiều chi tiết như:

- `reason_code`
- `priority_score`
- `ghost_rate`
- `component_id`
- `linked_pair_count`
- `supporting_signal_count`

### Rủi ro nghiệp vụ

- Người xấu có thể học ngược hệ thống đang để ý tới đâu
- Họ có thể đoán được threshold và pattern cần tránh
- Việc lộ quá nhiều chi tiết temporal / network có thể giảm hiệu quả anti-fraud

### Khuyến nghị

- Tách role view:
  - executive view
  - analyst view
  - investigator view
- Mặc định chỉ show business-rule level cho role thông thường
- Ẩn hoặc mask `reason_code`, `priority_score`, `component_id` nếu role không đủ quyền

## Component-level review nên được diễn giải thế nào

Pipeline hiện tại đã dùng `WCC`, nên dashboard có thể tận dụng `component` để mở rộng điều tra.

Những thông điệp cần giữ rất rõ:

- component giúp tìm nhóm liên quan
- component không phải bằng chứng kết luận độc lập

Nếu bổ sung thêm card / table, nên ưu tiên:

- `Largest WCC Component`
- top components theo `component_size`
- top components theo `avg` hoặc `max priority_score`
- chi tiết component:
  - số driver
  - số customer
  - số pair
  - số order
  - top business rule
  - top service

## P0 cần update trong docs và dashboard notes

- Tách rõ `flag rows` và `unique flagged orders`
- Thêm ghi chú rằng một order có thể trùng nhiều `reason_code`
- Cập nhật mô tả `SUPERFAST_GAP` theo logic mới
- Cập nhật mô tả `high_confidence` theo logic mới
- Cập nhật thông điệp rằng pair evidence là trung tâm, network evidence là hỗ trợ

## P1 nên làm tiếp

- Thêm insight card `Highest-Risk Component`
- Thêm breakdown theo `business_rule_label` và `risk_tier`
- Thêm data notes về phạm vi dữ liệu và ý nghĩa từng metric
- Thêm benchmark trước/sau khi siết logic cho các ngày spike lớn

## Kết luận

Dashboard hiện tại vẫn là nền tảng tốt cho bài toán `ride`, nhưng cách viết docs và note đi kèm cần đổi sang ngôn ngữ để business và vận hành dễ hiểu hơn.

Thông điệp chốt cần giữ đồng bộ:

- hệ thống tìm cặp đáng nghi trước
- hệ thống giải thích lý do sau
- con người review order cuối cùng
