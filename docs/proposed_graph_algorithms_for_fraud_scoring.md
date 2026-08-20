# Graph Algorithms Đang Được Chọn Cho Hướng Đi Mới Của Project

## Phạm vi tài liệu

Tài liệu này mô tả bộ graph algorithms đang được chọn cho hướng đi mới của project, tập trung vào bài toán:

- `Driver-Customer Ghost-Trip Collusion`

Nguồn định hướng gốc:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

## Kết luận nhanh

Project nên tập trung vào 3 graph algorithms cốt lõi:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Ba thành phần này tương ứng với 3 câu hỏi chính:

1. Pair nào lặp lại bất thường?
2. Pair nào thật sự có tính collusion cao?
3. Các pair nghi ngờ có kết nối thành network để mở case điều tra hay không?

## 1. Đơn vị phân tích trung tâm

Đơn vị phân tích chính không phải từng order riêng lẻ, mà là pair:

- `driver_id`
- `customer_id`

Mỗi pair được xem là một cạnh có trọng số trong đồ thị hai phía:

- bên trái: `Driver`
- bên phải: `Customer`
- trọng số cạnh: `trip_count`

Đây là abstraction dùng nhất cho bài toán ghost-trip collusion vì hành vi gian lận thường tập trung vào quan hệ lặp lại giữa hai đầu.

## 2. Bộ 3 thuật toán cốt lõi

## 2.1. Weighted edge outlier detection

Mục tiêu:

- tìm các pair có `trip_count` nằm ở phần dưới của phân phối toàn bộ pairs trong cùng time window

Vai trò:

- first-pass detector
- tạo seed suspicious pairs
- dễ giải thích và dễ scale

Đây là lớp phát hiện đầu tiên, nhưng không nên dùng một mình để kết luận collusion.

## 2.2. Bipartite concentration scoring

Mục tiêu:

- đo xem một pair có chiếm tỉ trọng bất thường trên cả hai đầu hay không

Feature cốt lõi:

- `pair_share_driver = pair_trip_count / total_driver_trip_count`
- `pair_share_customer = pair_trip_count / total_customer_trip_count`

Vai trò:

- refinement layer cho suspicious pairs
- giảm false positive từ volume tuyệt đối
- bắt đúng bản chất "khóa cứng" giữa driver và customer

## 2.3. WCC

Mục tiêu:

- gom các pair nghi ngờ thanh `component` de phuc vu dieu tra

WCC được chạy trên suspicious graph, nối các suspicious pairs qua shared entities nhu:

- shared driver
- shared customer
- shared address
- shared payment
- shared promo

Vai trò:

- chuyển từ pair detection sang network investigation
- tạo `component_id`, `component_size`, danh sách member, và độ ưu tiên mở case

## 3. Pipeline nên được xem là chuẩn

Pipeline graph-first được ưu tiên trong hướng mới:

1. Build pair table theo time window
2. Tính `trip_count`, `driver_trip_count`, `customer_trip_count`
3. Tính `pair_share_driver`, `pair_share_customer`
4. Chạy `weighted edge outlier detection`
5. Chạy `bipartite concentration scoring`
6. Tạo suspicious pair list
7. Build suspicious graph từ shared entities
8. Chạy `WCC`
9. Rank pair và rank component để analyst review

## 4. Các signal nên được xem là enrichment, không phải graph core

Các signal sau vẫn hữu ích, nhưng trong hướng mới chúng không phải bộ 3 graph algorithms cốt lõi:

- `ghost_rate` tu `avg_kmh = 0`
- `min_gap_min` hoặc superfast repeat gap
- `dominant_route_share`
- route reuse templates
- script similarity

Nên xem chúng là:

- `operational fraud signals`
- `business enrichment`
- `precision boosters`

Không nên để các signal này chi phối kiến trúc graph core của project.

## 5. Những gì không còn là ưu tiên giai đoạn đầu

Ở giai đoạn MVP và hướng làm lại project, không nên đặt các thuật toán sau làm trung tâm:

- `Louvain`
- `k-core`
- `node similarity` tổng quát
- ring scoring phức tạp

Lý do:

- khó explain hơn
- cần graph phong phú hơn mới phát huy tác dụng
- không sát bài toán repeated pair bằng bộ 3 cốt lõi

## 6. Cách định vị tài liệu này so với implementation

Tai liệu này là `target architecture note`, không phải báo cáo "as-is".

Nếu implementation hiện tại có thêm:

- ghost rules
- fast-gap rules
- route-loop rules
- blended risk score

thì nên hiểu đó là phần di sản hoặc enrichment. Hướng mới cần được mô tả và đánh giá theo logic:

- core graph pipeline trước
- enrichment sau

## 7. Final recommendation

Nếu cần chốt bộ graph algorithms để build lại project theo hướng gọn, đúng trọng tâm, để bàn giao và để explain, thì bộ cần chốt là:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Đây là bộ khung graph chính. Mỗi signal khác nên được gán vào như lớp hỗ trợ sau khi bộ khung này ổn định.
