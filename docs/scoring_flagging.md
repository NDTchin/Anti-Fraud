# Báo Cáo Chấm Điểm Và Gắn Cờ Hiện Tại Của Project

## Phạm vi tài liệu

Tài liệu này mô tả trạng thái chấm điểm và gắn cờ hiện tại của project sau khi đã áp dụng thêm graph support cho `ride` vào Tuesday, July 28, 2026.

Phần được xác nhận trực tiếp từ source code hiện có trong repo nằm chủ yếu tại:

- `src/algorithms/ride_collusion_graph.py`
- `src/rules/ride_kbc_rules.py`
- `src/scoring/ride_collusion_scoring.py`
- `scripts/build_task3_daily_outputs.py`
- `tests/test_ride_collusion_rules.py`
- `src/dashboard/app.py`
- `src/dashboard/kbc_daily_dashboard.py`

## Kết luận nhanh

Ở thời điểm hiện tại, pipeline chấm điểm rõ ràng và hoàn chỉnh nhất trong repo là pipeline `ride` cho rule:

- `REPEATED_CUSTOMER_DRIVER`

Pipeline này hiện đã đi theo mô hình 3 lớp:

1. rule-based pair scoring
2. graph-based pair support scoring
3. order-level flagging

Nói ngắn gọn:

- phát hiện ở level `driver_id - customer_id`
- chấm điểm nền bằng rule
- nâng điểm bằng graph support
- materialize kết quả xuống `flagged_orders`

## 1. Kiến trúc scoring hiện tại cho `ride`

### 1.1. Đơn vị phân tích chính

Đơn vị phân tích trung tâm là cặp:

- `driver_id`
- `customer_id`

Đây là lựa chọn hợp lý vì pattern collusion trong `ride` hiện đang tập trung vào:

- repeated pair
- ghost trip
- superfast turnaround
- route loop

### 1.2. Đơn vị gắn cờ đầu ra

Sau khi một pair bị xem là nghi vấn, toàn bộ order của pair đó trong cửa sổ phân tích sẽ được đưa vào:

- `flagged_orders.parquet`

Vì vậy:

- scoring diễn ra ở cấp `pair`
- review list được xuất ở cấp `order`

## 2. Thuật toán phát hiện pair nghi vấn

Phần này nằm ở [ride_collusion_graph.py](/D:/VSF/src/algorithms/ride_collusion_graph.py).

### 2.1. Lọc active orders

Project giữ lại các order:

- có `driver_id`
- có `customer_id`
- có `order_time_local_tz`
- không bị hủy, tức `is_cancelled = 0`

Sau đó tạo thêm:

- `is_ghost = (avg_kmh == 0)`
- `route_key = pickup_address -> last_dropoff_address`

### 2.2. Gom theo pair

Project group theo:

- `driver_id`
- `customer_id`

và tính các tín hiệu:

- `n_trips`
- `n_ghost`
- `ghost_rate`
- `min_gap_min`
- `avg_gmv`
- `total_gmv`
- `total_discount`
- `active_days`
- `latest_order_date`
- `pair_share_driver`
- `pair_share_customer`
- `dominant_route_key`
- `dominant_route_share`

### 2.3. Shortlist theo quantile

Project tính:

- `trip_threshold = quantile(0.9999)` của `n_trips`

và chỉ giữ:

- các pair có `n_trips > trip_threshold`

Đây là bước shortlist đầu tiên để giảm nhiễu.

## 3. Rule-based scoring hiện tại

Phần này nằm ở:

- [ride_kbc_rules.py](/D:/VSF/src/rules/ride_kbc_rules.py)
- [ride_collusion_scoring.py](/D:/VSF/src/scoring/ride_collusion_scoring.py)

### 3.1. Các reason code hiện tại

Project hiện đang gắn các lý do:

- `KB-C_EXTREME_VOLUME`
- `KB-C_HIGH_GHOST_RATE`
- `KB-C_SUPERFAST_GAP`
- `KB-C_TIGHT_PAIR_SHARE`
- `KB-C_ROUTE_LOOP`

### 3.2. High-confidence logic

Project hiện gắn:

- `high_confidence = (ghost_rate > 0.3) OR (min_gap_min < 5)`

Đây là lớp severity nhị phân ban đầu.

### 3.3. Rule score nền

Hiện tại project đã tách rõ:

- `rule_score_base`
- `rule_score`

Trong đó:

- `rule_score_base` là điểm từ rule trước khi thêm graph support
- `rule_score` hiện được dùng làm điểm cuối cùng sau khi đã rescore

### 3.4. Công thức `rule_score_base`

Project tính 5 thành phần strength:

- `trip_strength`
- `ghost_strength`
- `fast_gap_strength`
- `share_strength`
- `route_strength`

và dùng công thức:

```python
score = 100 * (
    0.35 * trip_strength
    + 0.25 * ghost_strength
    + 0.20 * fast_gap_strength
    + 0.10 * share_strength
    + 0.10 * route_strength
)
```

Ý nghĩa:

- volume cực trị là tín hiệu mạnh nhất
- sau đó là ghost-rate
- tiếp theo là superfast gap
- share và route đóng vai trò bổ trợ

## 4. Graph algorithm đã được áp dụng cho `ride`

Phần này là thay đổi quan trọng nhất đã được triển khai.

### 4.1. Shared-entity concentration

Project hiện đã thêm graph support dựa trên shared entities của các pair nghi vấn:

- `payment_method`
- `promotion_code`
- `pickup_address`
- `last_dropoff_address`
- `route_key`

Mỗi loại shared entity được dùng để nối pair với pair khác nếu:

- cùng tham chiếu tới một entity giống nhau
- entity đó không quá phổ biến

Hiện tại đang có các ngưỡng mặc định:

- `payment_max_degree = 150`
- `promo_max_degree = 200`
- `address_max_degree = 50`
- `route_max_degree = 50`

### 4.2. Graph component grouping

Sau khi nối các pair qua shared entities, project build một graph pair-level và chạy:

- `connected_components()` bằng `networkx`

Về mặt ý tưởng, đây là bước cluster baseline tương đương với grouping kiểu `WCC` trên suspicious pair graph.

Mỗi pair hiện có thêm:

- `component_id`
- `component_size`
- `component_edge_count`
- `component_density`

### 4.3. Pair-level graph support metrics

Project hiện tính thêm các feature graph sau:

- `shared_payment_count`
- `shared_promo_count`
- `shared_pickup_count`
- `shared_dropoff_count`
- `shared_route_count`
- `supporting_signal_count`
- `linked_pair_count`
- `component_size`
- `component_density`

### 4.4. Graph risk score

Từ các feature trên, project sinh:

- `graph_risk_score`

Điểm này được tạo từ tổ hợp:

- số pair liên kết
- số loại tín hiệu shared support
- kích thước component
- mật độ component

Hiện tại công thức đang thiên về:

- `linked_pair_count`
- `supporting_signal_count`

nhiều hơn là density thuần túy.

## 5. Final scoring hiện tại

Sau khi có `rule_score_base` và `graph_risk_score`, project tạo:

- `final_risk_score`

Logic hiện tại là:

- trước hết blend `rule_score_base` với `graph_risk_score`
- sau đó bảo đảm `final_risk_score` không thấp hơn `rule_score_base`

Điều này có nghĩa:

- graph support chỉ nâng hoặc giữ nguyên điểm nền
- graph support không kéo điểm của một pair đang đã mạnh theo rule xuống thấp hơn

Cuối cùng:

- `rule_score = final_risk_score`

để dashboard và report dùng ngay điểm mới.

## 6. Risk tier hiện tại

Project hiện không còn map `risk_tier` chỉ bằng `high_confidence` như trước.

Hiện tại:

- `HIGH` nếu `high_confidence = True` và `final_risk_score >= 75`
- `MEDIUM` nếu `final_risk_score >= 60`
- còn lại là `WATCHLIST`

Điều này làm `risk_tier` phản ánh tốt hơn cả:

- mức độ mạnh của rule
- mức độ được graph support

## 7. Cách gắn cờ order hiện tại

Phần này vẫn nằm ở [ride_collusion_scoring.py](/D:/VSF/src/scoring/ride_collusion_scoring.py).

### 7.1. Materialize từ pair xuống order

Sau khi pair bị flag, project join ngược với `active_orders` theo:

- `driver_id`
- `customer_id`

Mỗi order được gắn thêm:

- `rule_name`
- `reason_code`
- `flag_reason`
- `supporting_signal`
- `rule_score_base`
- `graph_risk_score`
- `final_risk_score`
- `risk_tier`
- `linked_pair_count`
- `supporting_signal_count`
- `component_id`
- `component_size`
- `component_density`

### 7.2. Một order có thể có nhiều dòng flag

Do một pair có thể thỏa nhiều `reason_code`, một `order_id` có thể xuất hiện nhiều dòng trong `flagged_orders`.

Vì vậy:

- `flagged_rows` không bằng số order duy nhất
- dashboard phải dùng `nunique()` hoặc `drop_duplicates(["order_id", "rule_name"])`

### 7.3. Evidence JSON

Project hiện đã mở rộng `evidence_json` để chứa thêm graph context như:

- `graph_risk_score`
- `linked_pair_count`
- `supporting_signal_count`
- `component_id`
- `component_size`
- `component_density`

Điều này giúp analyst không chỉ thấy tín hiệu rule, mà còn thấy pair đó có nằm trong cluster đáng ngờ hay không.

## 8. Đầu ra hiện tại của pipeline `ride`

Script build là:

- [scripts/build_task3_daily_outputs.py](/D:/VSF/scripts/build_task3_daily_outputs.py)

Script này hiện:

1. build pair stats
2. chấm `rule_score_base`
3. enrich graph features
4. sinh `graph_risk_score`
5. sinh `final_risk_score`
6. gắn cờ order
7. ghi report ra `reports/task3`

Các output chính hiện tại:

- `flagged_orders.parquet`
- `kbc_pair_summary.csv`
- `kbc_pair_reasons.csv`
- `daily_rule_summary.csv`
- `priority_recommendations.csv`
- `rule_model_comparison.csv`
- `quality_report.csv`
- `known_case_evaluation.csv`

## 9. Kết quả build `ride` sau khi rescore

Theo lần build lại trên Tuesday, July 28, 2026:

- active ride orders: `4,767,940`
- extreme trip threshold: `12.0`
- candidate pairs: `371`
- flagged order rows: `11,000`
- known-pair hit rate: `100%`

Một số chỉ số mới từ `kbc_pair_summary.csv`:

- `graph_risk_score` mean khoảng `76.10`
- `final_risk_score` mean khoảng `41.80`
- `component_size` median khoảng `359`
- `linked_pair_count` mean khoảng `64.20`
- `supporting_signal_count` mean khoảng `3.12`

Phân bố `risk_tier` mới trong `flagged_orders.parquet`:

- `HIGH`: `144`
- `MEDIUM`: `742`
- `WATCHLIST`: `10,114`

## 10. Cách hiểu đúng giữa score và flag

### 10.1. `rule_score_base`

Đây là điểm nền từ pair behavior.

Nó trả lời:

- pair này có bất thường mạnh theo logic KBC hay không

### 10.2. `graph_risk_score`

Đây là điểm support từ neighborhood graph.

Nó trả lời:

- pair này có được củng cố bởi shared payment, shared promo, shared address, shared route, và component suspicious hay không

### 10.3. `final_risk_score`

Đây là điểm ưu tiên review cuối cùng.

Nó trả lời:

- nên xếp pair này ở mức ưu tiên nào khi điều tra

### 10.4. `flagged_orders`

Đây không phải kết luận fraud, mà là shortlist điều tra.

## 11. Kết luận

Trạng thái hiện tại của project có thể chốt như sau:

- `ride` đã không còn chỉ là rule scoring thuần nữa
- project hiện đã thêm một lớp graph support thật sự vào pair scoring
- điểm cuối cùng hiện là `final_risk_score`, không còn chỉ là `rule_score` nền
- `risk_tier` hiện phản ánh cả rule strength lẫn graph support
- các graph algorithm đang thực sự dùng trong nhánh `ride` hiện tại là:
  - weighted edge outlier
  - endpoint concentration
  - temporal edge anomaly
  - route reuse scoring
  - shared-entity concentration
  - component grouping kiểu connected-components baseline
