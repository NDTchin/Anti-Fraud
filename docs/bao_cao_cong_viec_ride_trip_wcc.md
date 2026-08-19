# Báo cáo ngắn gọn cho bài toán ride - trip

## 1. Cấu trúc trình bày

Phần việc được chia thành 2 case:

1. `Case 1: Pair-level detection`
   - tìm ra các cặp `driver - customer` đáng nghi
2. `Case 2: Network-level investigation with WCC`
   - mở rộng điều tra từ từng cặp đáng nghi sang cụm có liên kết

## 2. Case 1: Pair-level detection

### 2.1. Mục tiêu

Mục tiêu của case 1 là tìm ra các cặp `driver_id - customer_id` có dấu hiệu đáng nghi để đưa vào shortlist review.

Đơn vị phát hiện chính là:

- `pair_key = driver_id || customer_id`

Lý do chọn `pair`:

- bài toán collusion nằm ở quan hệ giữa tài xế và khách hàng
- nhìn từng `order` thì quá rời rạc
- nhìn riêng từng `driver` hoặc `customer` thì mất tín hiệu quan hệ hai chiều

### 2.2. Thuật toán và cách dùng

Case 1 chủ yếu dùng 2 nhóm thuật toán chính:

1. `Weighted Edge Outlier Detection`
   - dùng để phát hiện pair có số chuyến lặp lại cao bất thường
   - ý tưởng là so sánh volume của pair với mặt bằng chung trong cùng time window
   - đầu ra chính:
     - `volume_score`
     - `is_extreme_volume`

2. `Bipartite Concentration Scoring`
   - dùng để đo mức độ pair chiếm activity của cả driver và customer
   - mục tiêu là tìm các cặp không chỉ đi nhiều, mà còn phụ thuộc bất thường vào nhau
   - đầu ra chính:
     - `pair_share_driver`
     - `pair_share_customer`
     - `concentration_score`

Ngoài ra, hệ thống còn dùng thêm các tín hiệu hành vi để bổ sung cho pair scoring:

- `ghost_rate`
- `min_gap_min`
- `temporal_score`
- `dominant_route_share`
- `route_score`

### 2.3. Key, field, feature dùng để nhận diện

Các field/key gốc được dùng để tạo pair-level features gồm:

- `driver_id`
- `customer_id`
- `order_id`
- `created_at` hoặc timestamp tương đương
- thông tin route như `pickup_address`, `last_dropoff_address`, `route_key`
- các tín hiệu ghost-trip đã được materialize từ dữ liệu nguồn

Các feature chính để nhận diện pair đáng nghi:

1. `n_trips`
   - tổng số chuyến của pair
2. `volume_score`
   - pair có volume bất thường hay không
3. `pair_share_driver`
   - pair chiếm bao nhiêu phần trăm activity của driver
4. `pair_share_customer`
   - pair chiếm bao nhiêu phần trăm activity của customer
5. `concentration_score`
   - mức độ phụ thuộc hai chiều của pair
6. `ghost_rate`
   - tỷ lệ chuyến có tín hiệu ghost
7. `min_gap_min`
   - khoảng cách thời gian ngắn nhất giữa các chuyến
8. `temporal_score`
   - mức độ bất thường về nhịp chạy
9. `dominant_route_share`
   - mức độ lặp route

### 2.4. Kết quả đầu ra

Case 1 cho ra:

- danh sách `suspicious pairs`
- `reason_code` cho từng pair
- các điểm như:
  - `pair_core_score`
  - `suspected_ghost_score`
  - `pair_risk_score`
- danh sách `flagged_orders` để analyst drill xuống xác minh

Tóm lại, case 1 trả lời 3 câu hỏi:

- cặp nào đáng nghi
- đáng nghi vì lý do gì
- nên review cặp nào trước

## 3. Case 2: Network-level investigation with WCC

### 3.1. WCC là gì

`WCC` là `Weakly Connected Components`.

Trong ngữ cảnh bài toán này:

- mỗi `node` là một suspicious pair
- mỗi `edge` là một liên kết đủ mạnh giữa hai pair
- `WCC` dùng để tìm các nhóm pair liên thông với nhau trực tiếp hoặc gián tiếp

Ví dụ:

- pair A nối với pair B
- pair B nối với pair C

thì A, B, C sẽ nằm trong cùng một `component` dù A không nối trực tiếp với C.

### 3.2. WCC dùng để làm gì

WCC được dùng để:

1. gom các suspicious pairs thành từng cụm điều tra
2. tìm xem một pair có nằm trong network nghi ngờ hay không
3. tạo thêm network evidence để tăng chất lượng prioritization

Điểm quan trọng:

- `WCC` không phải detector đầu tiên
- `WCC` chỉ chạy sau khi case 1 đã tìm ra suspicious pairs
- giá trị của `WCC` là mở rộng điều tra từ level cặp sang level mạng lưới

### 3.3. WCC dùng như nào

Pipeline của case 2 đi theo các bước:

1. lấy danh sách suspicious pairs từ case 1 làm node
2. tìm shared entities giữa các pair
3. sinh candidate edges
4. lọc các edge đủ mạnh
5. chạy `WCC` để gom thành các `component`
6. sinh network features cho từng pair và từng component

Nói ngắn gọn:

- case 1 tạo node
- graph construction tạo edge
- `WCC` gom node và edge thành các cụm liên thông

### 3.4. Dùng cái gì, field gì để nối các pair

Các shared entities chính dùng để tạo edge giữa hai pair:

- `payment_method`
- `promotion_code`
- `pickup_address`
- `last_dropoff_address`
- `route_key`

Ngoài việc trùng shared entity, hệ thống còn nhìn thêm:

- độ phổ biến của entity
- độ gần nhau về thời gian sử dụng entity

Điều này có nghĩa là:

- không phải cứ trùng field là nối ngay
- entity càng hiếm thì tín hiệu càng mạnh
- hai pair dùng entity càng gần nhau về thời gian thì edge càng đáng tin hơn

### 3.5. Field và feature chính của WCC

Các field đầu vào chính:

- `pair_key`
- `payment_method`
- `promotion_code`
- `pickup_address`
- `last_dropoff_address`
- `route_key`
- `first_order_date`
- `last_order_date`

Các feature/network metrics chính được sinh ra:

1. `linked_pair_count`
   - pair này nối trực tiếp với bao nhiêu pair khác
2. `supporting_signal_count`
   - pair này được hỗ trợ bởi bao nhiêu loại tín hiệu network
3. `component_size`
   - cụm có bao nhiêu pair
4. `component_edge_count`
   - cụm có bao nhiêu edge
5. `component_density`
   - độ chặt của cụm

### 3.6. Kết quả đầu ra của WCC

WCC cho ra 2 lớp kết quả:

1. `Component-level output`
   - `component_id`
   - `component_size`
   - `component_edge_count`
   - `component_density`

2. `Pair-level network output`
   - `linked_pair_count`
   - `supporting_signal_count`
   - `network_support_score`
   - `network_risk_score`

Các output này được dùng tiếp để:

- bổ sung ngữ cảnh điều tra cho analyst
- tăng ưu tiên cho những case có dấu hiệu hoạt động theo mạng

## 4. Kết luận ngắn gọn

Toàn bộ hướng làm được tóm lại như sau:

1. `Case 1: Pair-level detection`
   - dùng các thuật toán pair scoring để tìm ra cặp `driver - customer` đáng nghi
   - dựa trên volume, concentration, ghost signal, temporal pattern và route pattern

2. `Case 2: Network-level investigation with WCC`
   - dùng graph và `WCC` để tìm các liên kết giữa suspicious pairs
   - dựa trên shared entities như payment, promo, pickup, dropoff, route
   - đầu ra là các `component` và các network features để hỗ trợ review

Nếu nói trong một câu:

Case 1 giúp tìm ra pair đáng nghi, còn case 2 dùng `WCC` để trả lời xem các pair đáng nghi đó có đang nằm trong cùng một mạng lưới phối hợp hay không.
