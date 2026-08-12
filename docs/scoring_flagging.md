# Scoring và Flagging

## Phạm vi tài liệu

Tai liệu này mô tả cách scoring và flagging nên được hiểu trong luồng `ride` hiện tại.

Tập trung vào 3 việc:

- hệ thống chấm điểm trên đơn vị nào
- hệ thống đưa kết quả ra dashboard theo cách nào
- người đọc cần hiểu các con số ra sao để tránh hiểu sai

Tai liệu này theo hướng graph-first của bài toán `Driver-Customer Ghost-Trip Collusion`.

## Kết luận nhanh

Nếu cần bạn tóm tắt cho non-tech, hệ thống đang hoạt động như sau:

1. Tìm cặp `tài xế - khách hàng` lặp lại bất thường
2. Chấm điểm độ bất thường của chính cặp đó
3. Kiểm tra xem cặp đó có nằm trong cụm đáng nghi không
4. Tổng hợp điểm để xếp thứ tự review
5. Đưa các `order` liên quan ra để con người xem

Vi vậy, scoring nên được hiểu thành 3 lớp:

1. `pair_core_score`
2. `network_support_score`
3. `priority_score`

## Cập nhật implementation

Pipeline hiện tại đã được siết lại theo hướng giảm false positive và giảm noise:

- đã sửa cách tính `min_gap_min` để luôn sort đúng trước khi tính khoảng cách thời gian
- không còn chấp nhận `min_gap_min` âm làm bằng chứng cho `SUPERFAST_GAP`
- shortlist suspicious pair mặc định chặt hơn trước
- network support tiếp tục chỉ đóng vai trò bổ sung


## 1. Đơn vị scoring chính

Đơn vị scoring trung tâm là `pair`:

- `driver_id`
- `customer_id`

Lý do:

- bài toán gian lận này thể hiện ở mối quan hệ lặp lại giữa hai bên
- nếu chấm điểm thẳng ở cấp order, rất dễ nhiều noise và khó thấy mẫu lặp
- pair scoring giúp gom các chuyến xe rời rạc thành một câu chuyện để điều tra

Cách nói ngắn gọn cho non-tech:

- hệ thống không hỏi "order này có gian lận không?"
- hệ thống hỏi "cặp tài xế - khách hàng này có hành vi bất thường không?"

## 2. 3 lớp điểm trong luồng mới

### 2.1. `pair_core_score`

Đây là điểm quan trọng nhất.

Nó trả lời:

- nếu chỉ nhìn riêng cặp này, cặp có bất thường không?

Trong luồng hiện tại, điểm này được xây chủ yếu từ:

- `volume_score`
- `concentration_score`

Có thể hiểu đơn giản:

- `volume_score`: cặp này lặp lại nhiều hơn bình thường hay không
- `concentration_score`: hai bên có "dính" vào nhau quá mức bình thường hay không

### 2.2. `network_support_score`

Đây là điểm bổ sung.

  Trả lời:

- cặp này có nằm trong một cụm đáng nghi rộng hơn hay không?

Sau khi có danh sách suspicious pair, hệ thống mới build suspicious graph và chạy `WCC`.

Từ đó mới có các thông tin như:

- `component_id`
- `component_size`
- `linked_pair_count`
- số loại shared entities hỗ trợ

Cần giữ cách hiểu nhất quán:

- network support giúp mở rộng điều tra
- network support không thay thế pair evidence

### 2.3. `priority_score`

Đây là điểm cuối cùng để sắp thứ tự review.

  Trả lời:

- case nào nên được mở ra xem trước?

Nếu giải thích bằng ngôn ngữ business:

- `pair_core_score` = mức độ đáng nghi của cặp
- `network_support_score` = mức độ có được bối cảnh xung quanh củng cố hay không
- `priority_score` = thứ tự cần xem trước trên dashboard

## 3. Pair nào mới được đưa vào shortlist

Trong logic hiện tại, một pair được shortlist khi:

- đạt mức tối thiểu về số chuyến
- và có repeated-pair evidence mạnh hoặc ghost signal mạnh

Mặc định implementation hiện tại ưu tiên:

- `n_trips >= 4`
- và một trong hai nhóm sau:
  - repeated-pair mạnh:
    - `is_extreme_volume = True`
    - `pair_share_driver >= 0.4` hoặc `pair_share_customer >= 0.6`
    - `concentration_score >= 0.85` hoặc `pair_core_score >= 50`
  - ghost signal mạnh:
    - `ghost_rate >= 0.5`

Điều quan trọng ở đây:

- pair phải có lý do đáng nghi từ thân trước
- hệ thống không nên đưa một pair vào shortlist chỉ vì nó đứng trong một cụm

## 4. Các signal enrichment đang đóng vai trò gì

Trong luồng mới, các signal sau vẫn rất hữu ích:

- `ghost_rate`
- `min_gap_min`
- `dominant_route_share`
- route template reuse

Vai trò của chúng đã rõ ràng hơn:

- tăng precision
- tăng explainability
- giúp ưu tiên review trong cùng một cụm

Không nên coi là trung tâm kiến trúc scoring.

Operational note:

- `ghost_rate` vẫn đủ mạnh để đưa pair vào shortlist trong một số trường hợp
- điều này phù hợp vì bài toán đang là `ghost-trip collusion`
- tuy nhiên, trong cách giải thích cho business, pair evidence vẫn phải là nền

## 5. Risk tier và flagging cần được đọc ra sao

`risk_tier` là nhãn ưu tiên review, không phải kết luận fraud.

Trong implementation hiện tại, order-level output đang dùng các mức:

- `IMMEDIATE_REVIEW`
- `HIGH_RISK`
- `MONITOR`
- `LOW_PRIORITY`

Nên diễn giải như sau:

- `IMMEDIATE_REVIEW`: case nên mở ra xem ngay
- `HIGH_RISK`: đáng nghi rõ, nhưng có thể cân đối chiều thêm
- `MONITOR`: cần theo dõi tiếp
- `LOW_PRIORITY`: chưa cần xử lý trước

Lưu ý thêm:

- `high_confidence` không còn được bắt chỉ vì một gap nhỏ đơn lẻ
- `SUPERFAST_GAP` chỉ hợp lệ khi gap không âm, đủ số trip, và có ghost support tối thiểu

## 6. Output nào mới là output cần đọc

Về mặt nghiệp vụ, pipeline hiện tại cần ít nhất 3 output chính:

- `pair_summary`
- `pair_reasons`
- `flagged_orders`

Y nghĩa:

- `pair_summary`: bảng trung tâm để chấm điểm và rank
- `pair_reasons`: nơi giải thích tại sao pair bị đưa vào shortlist
- `flagged_orders`: danh sách order để đội vận hành mở ra xem

Trong implementation hiện tại, dashboard đọc trực tiếp:

- `flagged_orders.parquet`
- `kbc_pair_summary.csv`
- `kbc_pair_reasons.csv`

Nếu cần giải thích ngắn gọn cho người mới:

- muốn hiểu tại sao hệ thống flag, xem `pair_reasons`
- muốn xem case nào quan trọng nhất, xem `pair_summary`
- muốn đối chiếu nghiệp vụ, xem `flagged_orders`

## 7. Cách đọc KPI cho đúng

Đây là điểm rất dễ bị hiểu sai.

Cần tách rõ:

- `flag rows`
- `unique flagged orders`

Vì:

- một order có thể trùng nhiều `reason_code`
- một order có thể xuất hiện nhiều dòng trong bảng flag

Vì vậy:

- `flag rows` phản ánh số dòng bảng cảnh báo
- `unique flagged orders` mới phản ánh số order duy nhất bị đưa ra review

## 8. Thứ tự ưu tiên để giải thích với business

Nếu cần trình bày cho đội non-tech, nên đi theo thứ tự:

1. Hệ thống tìm cặp đáng nghi, không tìm từng order riêng lẻ
2. Hệ thống chấm điểm mức độ bất thường của cặp đó
3. Hệ thống xem cặp đó có nằm trong cụm đáng nghi không
4. Hệ thống đưa các order liên quan ra để con người kiểm tra

Thứ tự này dễ hiểu hơn và đúng với luồng mới hơn cách nói theo tên thuật toán.

## 9. Final recommendation

Mọi tài liệu và dashboard note liên quan đến `ride` nên đồng bộ 4 thông điệp:

- pair là đơn vị phát hiện
- network là bằng chứng hỗ trợ
- order là cấp materialize để review
- score dùng để xếp thứ tự review, không phải kết luận fraud


