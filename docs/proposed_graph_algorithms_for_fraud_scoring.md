# Graph Algorithm Đang Dùng Hiện Tại Cho Bài Toán Fraud

## Phạm vi tài liệu

Tài liệu này chỉ mô tả các graph algorithm đang thực sự được dùng hiện tại trong project cho bài toán `ride` sau khi đã rescore vào Tuesday, July 28, 2026.

Tài liệu này không mô tả:

- roadmap phát triển tiếp
- thuật toán chưa triển khai
- đề xuất tương lai

Phần được xác nhận trực tiếp từ source code hiện có trong repo nằm chủ yếu tại:

- `src/algorithms/ride_collusion_graph.py`
- `src/rules/ride_kbc_rules.py`
- `src/scoring/ride_collusion_scoring.py`
- `scripts/build_task3_daily_outputs.py`
- `tests/test_ride_collusion_rules.py`

## 1. Kết luận nhanh

Hiện tại, các graph algorithm đang được dùng thật cho `ride` gồm 3 lớp chính:

1. weighted bipartite edge outlier
2. temporal và concentration scoring trên edge
3. shared-entity graph support + component grouping

Nói cách khác, project hiện chưa dùng các graph algorithm community nâng cao như:

- `Weighted Node Similarity`
- `k-core`
- `Louvain`

Phần đang chạy thật hiện tại là graph scoring xoay quanh pair `driver_id - customer_id` và suspicious pair graph.

## 2. Đồ thị đang được dùng

Đơn vị graph trung tâm hiện tại là pair:

- `driver_id`
- `customer_id`

Về mặt ý tưởng, pair này là một cạnh có trọng số trong đồ thị hai phía:

- phía 1: `Driver`
- phía 2: `Customer`

Trọng số chính của cạnh là:

- `n_trips`

Ngoài ra mỗi cạnh còn có thêm ngữ cảnh:

- ghost behavior
- time gap
- route reuse
- payment reuse
- promo reuse
- pickup/dropoff reuse

## 3. Weighted Bipartite Edge Outlier

Đây là graph algorithm nền đầu tiên đang dùng thật trong project.

### Cách chạy

Từ tất cả active orders:

- group theo `driver_id`, `customer_id`
- tính `n_trips`
- tính phân phối toàn cục của `n_trips`
- lấy ngưỡng `trip_threshold = quantile(0.9999)`
- chỉ giữ các pair có `n_trips > trip_threshold`

### Ý nghĩa

Đây là cách phát hiện các cạnh quá nặng trong đồ thị `Driver - Customer`.

Nó phù hợp vì:

- collusion kiểu repeated pair thường dồn vào rất ít cặp
- edge weight là tín hiệu mạnh và dễ giải thích nhất

## 4. Endpoint Concentration Scoring

Đây là lớp graph scoring thứ hai đang dùng thật trong project.

### Cách chạy

Với mỗi pair, project tính:

- `pair_share_driver = n_trips / driver_trip_count`
- `pair_share_customer = n_trips / customer_trip_count`

### Ý nghĩa

Đây là cách đo xem một cạnh có “độc chiếm” activity của hai đầu mút hay không.

Nếu:

- một driver gần như chủ yếu phục vụ một customer
- và customer đó cũng chủ yếu đi với driver đó

thì pair này đáng ngờ hơn.

### Vai trò trong scoring

Tín hiệu này hiện được dùng:

- trong `KB-C_TIGHT_PAIR_SHARE`
- trong `rule_score_base`

## 5. Temporal Edge Anomaly

Đây là lớp graph-temporal scoring đang dùng thật trong project.

### Cách chạy

Project sort order theo thời gian trên cùng một pair, sau đó tính:

- `min_gap_min`

Đồng thời project xác định:

- `is_ghost = (avg_kmh == 0)`
- `n_ghost`
- `ghost_rate`

### Ý nghĩa

Đây là dạng anomaly detection trên lịch sử thời gian của cùng một cạnh.

Nó giúp phát hiện:

- hai chuyến quá sát nhau
- nhiều chuyến không di chuyển

### Vai trò trong scoring

Tín hiệu này hiện được dùng:

- trong `KB-C_HIGH_GHOST_RATE`
- trong `KB-C_SUPERFAST_GAP`
- trong `high_confidence`
- trong `rule_score_base`

## 6. Route Reuse Concentration

Đây là một graph-context signal đang dùng thật.

### Cách chạy

Project tạo:

- `route_key = pickup_address -> last_dropoff_address`

Sau đó trên mỗi pair tính:

- route xuất hiện nhiều nhất
- `dominant_route_share`

### Ý nghĩa

Nếu cùng một pair lặp lại cùng một tuyến quá nhiều lần, đây là dấu hiệu của:

- route loop
- template hành vi lặp lại

### Vai trò trong scoring

Tín hiệu này hiện được dùng:

- trong `KB-C_ROUTE_LOOP`
- trong `rule_score_base`

## 7. Shared-Entity Concentration

Đây là lớp graph support mới đã được áp dụng thật cho `ride`.

### Thực thể dùng để nối pair với pair

Project hiện nối các pair nghi vấn qua:

- `payment_method`
- `promotion_code`
- `pickup_address`
- `last_dropoff_address`
- `route_key`

### Điều kiện nối

Một shared entity chỉ được dùng để nối pair nếu:

- có ít nhất 2 pair cùng dùng
- không vượt quá ngưỡng phổ biến cho loại entity đó

Các ngưỡng mặc định hiện tại:

- `payment_max_degree = 150`
- `promo_max_degree = 200`
- `address_max_degree = 50`
- `route_max_degree = 50`

### Ý nghĩa

Đây là cách thêm graph support để biết pair nghi vấn có:

- đứng một mình
- hay nằm trong vùng có shared behavior với nhiều pair khác

## 8. Component Grouping Bằng Connected Components

Đây là bước cluster baseline đang dùng thật.

### Cách chạy

Sau khi build suspicious pair graph từ shared entities, project dùng:

- `networkx.connected_components`

để gom pair thành component.

Mỗi pair hiện có thêm:

- `component_id`
- `component_size`
- `component_edge_count`
- `component_density`

### Ý nghĩa

Đây là cách gom các pair có liên hệ graph vào cùng một cụm nghi vấn.

Về mặt ý tưởng, nó tương đương với một bước grouping kiểu:

- connected-component baseline

trên suspicious pair graph.

## 9. Graph Support Metrics Đang Dùng

Từ suspicious pair graph, project hiện tính thêm các metric:

- `shared_payment_count`
- `shared_promo_count`
- `shared_pickup_count`
- `shared_dropoff_count`
- `shared_route_count`
- `supporting_signal_count`
- `linked_pair_count`
- `component_size`
- `component_density`

Các metric này cho biết:

- pair được bao nhiêu loại tín hiệu graph support
- pair đang nối với bao nhiêu pair khác
- pair đang nằm trong component lớn hay nhỏ
- component đó dày hay loãng

## 10. Graph Risk Score Đang Dùng

Từ các metric graph trên, project hiện sinh:

- `graph_risk_score`

Điểm này đang được tính từ tổ hợp:

- `linked_pair_count`
- `supporting_signal_count`
- `component_size`
- `component_density`

Về bản chất:

- đây là graph-level support score cho pair

Nó không thay thế rule score nền, mà bổ sung context graph để rescore.

## 11. Cách Graph Algorithm Gắn Vào Scoring

Hiện tại project đã có 3 lớp điểm:

- `rule_score_base`
- `graph_risk_score`
- `final_risk_score`

### `rule_score_base`

Điểm nền từ:

- edge outlier
- pair concentration
- temporal anomaly
- route reuse

### `graph_risk_score`

Điểm support từ:

- shared-entity graph
- connected component context

### `final_risk_score`

Điểm cuối cùng sau khi blend hai lớp trên, với quy tắc:

- không thấp hơn `rule_score_base`

Điều này có nghĩa:

- graph algorithm hiện tại chỉ nâng hoặc giữ nguyên mức độ nghi ngờ

## 12. Cách Graph Algorithm Gắn Vào Flagging

Sau khi pair có điểm cuối, project materialize kết quả xuống order.

Mỗi order hiện có thể nhận thêm:

- `graph_risk_score`
- `final_risk_score`
- `linked_pair_count`
- `supporting_signal_count`
- `component_id`
- `component_size`
- `component_density`

Nhờ vậy, analyst có thể thấy:

- không chỉ pair đó mạnh theo rule
- mà còn pair đó có nằm trong cluster đáng ngờ hay không

## 13. Những thuật toán hiện không nằm trong scope hiện tại

Để tránh hiểu nhầm, các thuật toán sau hiện chưa nằm trong logic đang chạy thật của repo:

- `Weighted Node Similarity`
- `k-core`
- `Louvain`
- ring density scoring riêng

Vì vậy không nên mô tả chúng như thể đang được dùng trong pipeline hiện tại.

## 14. Kết luận

Các graph algorithm đang dùng hiện tại cho bài toán `ride` của project là:

- weighted bipartite edge outlier
- endpoint concentration scoring
- temporal edge anomaly
- route reuse concentration
- shared-entity concentration
- connected-components baseline trên suspicious pair graph

Những thuật toán này hiện đã được gắn trực tiếp vào:

- `rule_score_base`
- `graph_risk_score`
- `final_risk_score`
- `flagged_orders`

Nói ngắn gọn, project hiện đang dùng graph theo cách:

- bắt đầu từ pair bất thường
- thêm support từ shared entities
- gom pair thành component
- rồi dùng context đó để chấm điểm lại và gắn cờ order
