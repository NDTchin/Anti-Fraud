# Report: Top 3 Graph Algorithms For Driver-Customer Ghost-Trip Collusion

## Purpose

Tài liệu này tập trung vào 3 graph algorithms phù hợp nhất để triển khai nhanh và đúng trọng tâm cho bài toán:

- `Driver-Customer Ghost-Trip Collusion`

Ba thuật toán được chọn:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Mục tiêu của báo cáo:

- giải thích chi tiết từng thuật toán
- nêu rõ vai trò của từng thuật toán trong bài toán
- đề xuất cách kết hợp chúng thành một pipeline gọn, hiệu quả, và dễ triển khai

Ngày lập tài liệu: `2026-08-04`

## 1. Executive Summary

Nếu chỉ được chọn 3 graph algorithms để giải bài toán `Driver-Customer Ghost-Trip Collusion`, thì đây là bộ tốt nhất để đi cùng nhau:

1. `Weighted edge outlier detection`
   - tìm cặp `driver-customer` có số chuyến lặp lại bất thường
2. `Bipartite concentration scoring`
   - đo mức độ pair chiếm activity của driver và customer
3. `WCC`
   - gom các pair nghi ngờ thành case groups hoặc suspicious components

Lý do bộ này phù hợp:

- bám sát bản chất collusion trên edge `Driver-Customer`
- đủ mạnh để phát hiện pair bất thường
- đủ thực dụng để mở rộng từ pair sang network
- không đòi hỏi graph mining quá nặng ngay từ đầu

## 2. Problem Framing

### 2.1 Bài toán thực sự là gì

Trong `Driver-Customer Ghost-Trip Collusion`, hành vi nghi ngờ thường có các đặc điểm:

- cùng một driver và customer lặp lại nhiều lần
- cặp đó chiếm tỷ trọng bất thường trong lịch sử của cả hai đầu
- có thể xuất hiện thêm dấu hiệu vận hành phi thực tế hoặc ghost signal
- nhiều pair nghi ngờ có thể nối với nhau thành một network lớn hơn

### 2.2 Tại sao phải dùng graph thinking

Bài toán này không nên nhìn thuần theo từng order riêng lẻ.

Đơn vị phân tích đúng hơn là:

- edge giữa `Driver` và `Customer`

Vì vậy graph giúp trả lời 3 câu hỏi rất quan trọng:

1. pair nào bất thường về tần suất
2. pair nào bất thường về mức độ khóa cứng giữa hai đầu
3. các pair nghi ngờ có liên hệ thành cụm hay không

## 3. Algorithm 1: Weighted Edge Outlier Detection

## 3.1 Mục tiêu

Phát hiện các cặp `driver-customer` có số lượng trip cao bất thường trong cùng time window.

## 3.2 Ý tưởng

Ta xây pair graph hai phía:

- node trái: `Driver`
- node phải: `Customer`
- edge: một pair `driver-customer`
- edge weight: `trip_count`

Nếu một edge có trọng số lớn hơn phần lớn các edge còn lại, edge đó có thể là tín hiệu collusion.

## 3.3 Input

- `driver_id`
- `customer_id`
- `trip_count`
- phân phối `trip_count` của toàn bộ pairs trong cùng time window

## 3.4 Output

- `volume_score`
- hoặc cờ `is_extreme_volume`

## 3.5 Vai trò trong bài toán

Đây là first-pass detector tốt nhất để tìm:

- cặp lặp lại nhiều bất thường

Nó không kết luận chắc chắn gian lận, nhưng rất hiệu quả để khoanh vùng.

## 3.6 Điểm mạnh

- đơn giản
- chạy nhanh
- dễ scale
- dễ explain

## 3.7 Điểm yếu

- dễ bỏ sót case nhỏ nhưng rất bất thường
- nếu dùng một mình sẽ tạo false positive cho các pair hợp lệ nhưng volume cao
- phụ thuộc vào time window

## 3.8 Khi nào nên dùng

Nên dùng ở:

- lớp phát hiện ban đầu
- lớp tạo seed suspicious pairs

## 4. Algorithm 2: Bipartite Concentration Scoring

## 4.1 Mục tiêu

Đo mức độ một pair chiếm activity của driver và customer.

## 4.2 Ý tưởng

Collusion thật thường không chỉ là “đi nhiều”.

Nó còn là:

- customer gần như chỉ đi với một driver
- hoặc driver dành phần lớn chuyến cho một customer

Vì vậy cần đo:

- `pair_share_driver = pair_trip_count / total_driver_trip_count`
- `pair_share_customer = pair_trip_count / total_customer_trip_count`

## 4.3 Input

- `pair_trip_count`
- `driver_trip_count`
- `customer_trip_count`

## 4.4 Output

- `concentration_score`

## 4.5 Vai trò trong bài toán

Đây là thuật toán phản ánh đúng bản chất collusion nhất.

Nếu `pair_share_customer` và `pair_share_driver` đều cao, pair đó có tính “khóa cứng” rất mạnh.

## 4.6 Điểm mạnh

- sát bản chất thông đồng
- ít bị nhiễu hơn volume tuyệt đối
- rất tốt để giảm false positives từ bước edge outlier

## 4.7 Điểm yếu

- vẫn có thể bắt nhầm các pair hợp lệ nhưng usage tập trung
- cần kết hợp thêm signal vận hành hoặc ghost signal để tăng precision

## 4.8 Khi nào nên dùng

Nên dùng ở:

- lớp scoring sau khi đã có pair features
- lớp refinement cho suspicious pairs

## 5. Algorithm 3: WCC

## 5.1 Mục tiêu

Gom các pair nghi ngờ thành các connected components để tạo case groups.

## 5.2 Ý tưởng

Sau khi đã có danh sách pair nghi ngờ, có thể xây suspicious graph bằng cách nối các pair này qua shared entities như:

- shared customer
- shared driver
- shared address
- shared payment
- shared promo

`WCC` sẽ tìm các thành phần liên thông trong graph đó.

## 5.3 Input

- suspicious pairs
- các liên kết shared-entity giữa chúng

## 5.4 Output

- `component_id`
- danh sách member trong từng component
- kích thước từng component

## 5.5 Vai trò trong bài toán

Đây là bước chuyển từ:

- phát hiện pair riêng lẻ

sang:

- điều tra network hoặc case cluster

## 5.6 Điểm mạnh

- đơn giản
- dễ explain cho investigator
- rất hợp cho anti-fraud ops

## 5.7 Điểm yếu

- không phải detector đầu tiên
- chất lượng phụ thuộc vào cách xây suspicious graph
- có thể gom rộng quá nếu shared-entity rules quá lỏng

## 5.8 Khi nào nên dùng

Nên dùng:

- sau khi đã có seed suspicious pairs
- sau bước pair scoring

## 6. Tại Sao 3 Thuật Toán Này Kết Hợp Tốt

Ba thuật toán này giải quyết ba lớp vấn đề khác nhau:

### 6.1 Weighted edge outlier detection

Trả lời:

- pair nào lặp nhiều bất thường

### 6.2 Bipartite concentration scoring

Trả lời:

- pair nào có tính collusion cao thật sự

### 6.3 WCC

Trả lời:

- các pair nghi ngờ đó có liên kết thành cụm để điều tra không

Nói ngắn gọn:

- `edge outlier` giúp tìm
- `concentration scoring` giúp xác nhận
- `WCC` giúp tổ chức điều tra

## 7. Recommended Combined Pipeline

## Stage 1. Build pair table

Mỗi dòng là một pair `driver-customer` trong time window.

Feature tối thiểu:

- `trip_count`
- `driver_trip_count`
- `customer_trip_count`
- `pair_share_driver`
- `pair_share_customer`

## Stage 2. Run weighted edge outlier detection

Kết quả:

- tìm các pair có `trip_count` nằm ở tail của phân phối
- tạo `volume_score` hoặc `is_extreme_volume`

Mục tiêu:

- tạo danh sách pair nghi ngờ ban đầu

## Stage 3. Run bipartite concentration scoring

Kết quả:

- tạo `concentration_score`

Mục tiêu:

- loại bớt pair volume cao nhưng không thật sự có tính collusion
- nâng hạng các pair volume vừa nhưng rất tập trung

## Stage 4. Create suspicious pair list

Một pair nên thành suspicious pair nếu:

- `volume_score` cao
- hoặc `concentration_score` cao
- hoặc cả hai

Nếu cần đơn giản, có thể dùng rule:

- `trip_count` nằm trên ngưỡng tail
- và `pair_share_customer` hoặc `pair_share_driver` vượt ngưỡng

## Stage 5. Build suspicious graph

Nodes hoặc edges trong suspicious graph được nối nếu chúng chia sẻ:

- cùng customer
- cùng driver
- cùng address
- cùng payment
- cùng promo

Đây là graph đầu vào cho `WCC`.

## Stage 6. Run WCC

Kết quả:

- gom suspicious pairs thành `component_id`
- tạo case groups để review

## Stage 7. Rank case groups

Ưu tiên điều tra theo:

- component size
- tổng số suspicious pairs
- tổng trip count
- tổng discount hoặc GMV nếu có

## 8. Practical Fraud Rules Based On These 3 Algorithms

## Rule 1. Extreme repeated pair

### Dựa trên

- `Weighted edge outlier detection`

### Logic

Flag nếu:

- `trip_count` của pair nằm trên ngưỡng tail

### Ý nghĩa

Pair lặp nhiều bất thường.

## Rule 2. Tight pair domination

### Dựa trên

- `Bipartite concentration scoring`

### Logic

Flag nếu:

- `pair_share_driver` cao
- và `pair_share_customer` cao

### Ý nghĩa

Pair có tính khóa cứng giữa hai đầu.

## Rule 3. Extreme repeated and dominated pair

### Dựa trên

- kết hợp `Weighted edge outlier detection`
- và `Bipartite concentration scoring`

### Logic

Flag pair ưu tiên cao nếu:

- `trip_count` cao bất thường
- đồng thời concentration cao

### Ý nghĩa

Đây là rule pair-level mạnh nhất trong bộ 3 thuật toán.

## Rule 4. Suspicious component

### Dựa trên

- `WCC`

### Logic

Flag component nếu:

- có từ nhiều suspicious pairs trở lên
- hoặc có shared entities đậm đặc

### Ý nghĩa

Không chỉ là pair gian lận đơn lẻ, mà là một cụm đáng mở case điều tra.

## 9. Why This Works Well For Ghost-Trip Collusion

Bộ 3 thuật toán này hợp với bài toán vì:

- collusion thường bắt đầu từ một pair lặp nhiều
- cặp collusion thật thường có tính tập trung cao
- nhiều pair collusion có thể liên hệ với nhau qua shared infrastructure

Đây là cách tiếp cận đúng theo anti-fraud practice:

1. phát hiện bất thường trên edge
2. xác minh tính collusion của edge
3. gom thành cluster điều tra

## 10. What This 3-Algorithm Set Does Not Cover

Bộ 3 này chưa xử lý đầy đủ:

- temporal anomaly
- ghost density từ `avg_kmh = 0`
- route reuse scoring
- fraud script similarity

Điều đó có nghĩa:

- đây là bộ `graph core`
- nhưng vẫn nên kết hợp với các fraud signals khác ở lớp scoring nghiệp vụ

## 11. Recommended MVP

Nếu cần triển khai nhanh:

1. tính `trip_count`
2. tính `pair_share_driver`
3. tính `pair_share_customer`
4. chạy `weighted edge outlier detection`
5. chạy `bipartite concentration scoring`
6. tạo suspicious pairs
7. build suspicious graph
8. chạy `WCC`
9. xuất `pair list` và `component list`

## 12. Final Recommendation

Nếu phải chốt đúng 3 graph algorithms tốt nhất để áp dụng cho bài toán `Driver-Customer Ghost-Trip Collusion`, thì nên chọn:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Đây là bộ:

- đúng trọng tâm nhất
- dễ triển khai nhất
- dễ explain nhất
- có khả năng mở rộng tốt nhất từ pair detection sang network investigation

## 13. Final Conclusion

Ba thuật toán này không giải quyết toàn bộ fraud problem một mình, nhưng chúng tạo ra bộ khung graph mạnh nhất để bắt đầu:

- `Weighted edge outlier detection` tìm pair lặp bất thường
- `Bipartite concentration scoring` xác nhận tính collusion
- `WCC` gom thành case groups để điều tra

Đối với trạng thái hiện tại của project, đây là bộ 3 hợp lý nhất để đầu tư trước.
## 14. Current Implementation Notes

The current implementation in this repo still follows the same 3 algorithms, but adds anti-noise controls so the output is safer on real production-like data.

### 14.1 Weighted Edge Outlier Detection

Current implementation details:

- `volume_score` remains cohort-based
- `trip_threshold` still comes from the tail of pair `trip_count`
- high volume is used as seed evidence, not final proof of fraud

### 14.2 Bipartite Concentration Scoring

Current implementation details:

- `raw_concentration = min(pair_share_driver, pair_share_customer)`
- `expected_share_driver = 1 / (driver_unique_customers + 1)`
- `expected_share_customer = 1 / (customer_unique_drivers + 1)`
- `expected_concentration = min(expected_share_driver, expected_share_customer)`
- `concentration_gap = max(0, (raw_concentration - expected_concentration) / (1 - expected_concentration))`
- `concentration_score = concentration_gap * support_factor`

Operational note:

- the score now reflects how much a pair exceeds its expected baseline
- this reduces false positives from pairs that only look concentrated because both sides have low diversity

### 14.3 WCC And Shared-Entity Graph

Current implementation details:

- WCC is still used to create suspicious components
- shared-entity edges are filtered before entering WCC
- generic hub-like values are removed before they can inflate a component
- single weak overlaps no longer create support edges by default
- shared entities also need temporal proximity to remain connected

Examples of current graph controls:

- ignore generic payment values such as `cash`
- ignore empty or default addresses such as `(0.000000, 0.000000)`
- require either:
  - at least `2` distinct signal types with enough total weight
  - or a stronger repeated single-signal pattern

### 14.4 Final Scoring Guidance

Current ranking intent:

- ghost-like behavior should dominate the top of the queue
- pair concentration should confirm collusion strength
- shared-entity network should support, not overpower, the pair decision
- business impact should affect investigation priority, not fraud plausibility by itself
