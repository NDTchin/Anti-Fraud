# BÁO CÁO ĐÁNH GIÁ KẾT QUẢ DRIVER–CUSTOMER GHOST-TRIP COLLUSION

**Ngày đánh giá:** 06/08/2026  
**Nguồn dữ liệu:** `2026-08-06T04-09_export.csv`  
**Số lượng pair được đánh giá:** 1.226 cặp Driver–Customer  

---

## 1. Mục tiêu báo cáo

Báo cáo này đánh giá kết quả hiện tại của pipeline phát hiện `Driver–Customer Ghost-Trip Collusion`, tập trung vào:

- các phần đã được triển khai tốt;
- các tín hiệu đang tạo ra giá trị;
- các điểm còn hạn chế trong pair scoring, graph construction và decision layer;
- nguyên nhân có thể gây false positive hoặc làm giảm khả năng phân loại;
- thứ tự ưu tiên cải thiện trong các phiên bản tiếp theo.

Pipeline hiện tại có thể hiểu ngắn gọn như sau:

```text
Completed Ride Orders
        ↓
Driver–Customer Pair Features
        ↓
Weighted Edge Volume Score
        ↓
Bipartite Concentration Score
        ↓
Pair Core Score
        ↓
Suspicious Pair Graph
        ↓
WCC / Network Metrics
        ↓
Investigation Priority
```

---

## 2. Tóm tắt dữ liệu kết quả

### 2.1 Thống kê tổng quan

| Chỉ số | Trung bình | Trung vị | P90 | Lớn nhất |
|---|---:|---:|---:|---:|
| Số chuyến mỗi pair | 17,33 | 16 | 24 | 102 |
| Mức độ tập trung | 0,546 | 0,553 | 0,804 | 1,000 |
| Điểm pair core | 45,57 | 44,02 | 58,15 | 94,04 |
| Điểm liên kết | 77,73 | 80,67 | 80,67 | 85,67 |
| Điểm ưu tiên | 55,29 | 54,11 | 63,85 | 94,04 |
| Cấp liên kết | 84,38 | 71 | 165 | 320 |
| Kích thước nhóm | 1.608,06 | 1.612 | 1.612 | 1.612 |

### 2.2 Phân phối tỷ lệ không di chuyển

| Nhóm tỷ lệ không di chuyển | Số pair |
|---|---:|
| Bằng 0% | 795 |
| Trên 0% đến 10% | 216 |
| Trên 10% đến 30% | 124 |
| Trên 30% đến 80% | 54 |
| Trên 80% đến 100% | 37 |

### 2.3 Phân phối nhãn ưu tiên

Toàn bộ **1.226 pair** đều đang có cùng một nhãn:

```text
Cần theo dõi
```

Điều này cho thấy decision layer hiện chưa phân tầng được mức độ ưu tiên điều tra.

---

# 3. Những phần đã làm tốt

## 3.1 Chọn đúng đơn vị phân tích là Driver–Customer pair

Pipeline đang phân tích theo grain:

```text
(driver_id, customer_id, time_window)
```

Đây là lựa chọn đúng với bản chất collusion, vì tín hiệu quan trọng không nằm riêng trên Driver, Customer hay từng Order, mà nằm trên quan hệ lặp lại giữa hai bên.

Các feature như:

- `trip_count`;
- `pair_share_driver`;
- `pair_share_customer`;
- tỷ lệ không di chuyển;
- điểm pair core;

đều có ý nghĩa rõ ràng khi đặt trên một Driver–Customer edge.

### Nhận xét

Đây là nền tảng đúng và nên tiếp tục giữ nguyên. Không nên quay lại cách chỉ chấm điểm từng order riêng lẻ cho case collusion.

---

## 3.2 Weighted Edge Outlier đã bắt được các pair volume lớn

Kết quả có các pair với:

```text
102 chuyến
70 chuyến
67 chuyến
65 chuyến
48 chuyến
```

Điều này cho thấy volume scoring đã nhận diện được phần đuôi của phân phối và đưa các pair lặp bất thường vào tập điều tra.

Số chuyến trung vị chỉ là 16, trong khi P99 khoảng 40,75 chuyến. Vì vậy các pair từ 60 đến hơn 100 chuyến thực sự nằm rất xa phần hoạt động thông thường của tập kết quả.

### Điểm tích cực

- dễ giải thích cho analyst;
- dễ kiểm tra lại bằng SQL hoặc Cypher;
- phù hợp làm detector ban đầu;
- có khả năng scale tốt;
- không phụ thuộc model phức tạp.

---

## 3.3 Bipartite Concentration phản ánh được quan hệ phụ thuộc hai chiều

`Mức độ tập trung` hiện có:

- trung vị khoảng `0,553`;
- P90 khoảng `0,804`;
- giá trị lớn nhất bằng `1,000`.

Điều này chứng minh hệ thống đã phân biệt được:

- pair chỉ có volume cao;
- pair mà Driver và Customer cùng phụ thuộc mạnh vào nhau.

Một số pair có concentration rất cao:

```text
41 chuyến, concentration = 0,9762
36 chuyến, concentration = 0,9474
10 chuyến, concentration = 1,0000
```

### Điểm tích cực

- sát với bản chất “khóa cứng” của collusion;
- giảm nhiễu từ tài xế chỉ đơn giản là hoạt động nhiều;
- dễ tạo reason code;
- dễ giải thích với investigator.

Việc dùng giá trị tối thiểu giữa `pair_share_driver` và `pair_share_customer` là một lựa chọn bảo thủ, phù hợp khi muốn yêu cầu cả hai phía cùng có mức phụ thuộc cao.

---

## 3.4 Pair core score đang tạo được thứ hạng tương đối rõ

`Diem pair core` trải từ:

```text
23,67 đến 94,04
```

và có độ phân tán tốt hơn `Diem lien ket`.

Điểm pair core có tương quan mạnh với cả:

- số chuyến;
- mức độ tập trung.

Điều này đúng với logic hiện tại vì pair core được xây từ volume và concentration.

### Nhận xét

Ở giai đoạn MVP, pair core hiện là thành phần scoring mạnh nhất và ổn định nhất. Nó phù hợp để dùng làm:

- pair ranking;
- seed selection;
- feature điều tra;
- baseline để so sánh các phiên bản scoring sau.

---

## 3.5 Hệ thống đã tìm ra nhiều case có pattern Ghost-Trip đáng chú ý

Có **91 pair** có tỷ lệ không di chuyển trên 30%, trong đó **37 pair** trên 80%.

Một số case nổi bật:

| Số chuyến | Concentration | Tỷ lệ không di chuyển | Giá trị trung bình |
|---:|---:|---:|---:|
| 102 | 0,5667 | 100% | 15.049 |
| 70 | 0,3889 | 100% | 15.943 |
| 67 | 0,6321 | 100% | 16.806 |
| 65 | 0,6989 | 90,8% | 44.154 |
| 41 | 0,4940 | 100% | 35.146 |
| 38 | 0,3040 | 100% | 13.605 |

Những case này có sự kết hợp đáng chú ý giữa:

- số chuyến cao;
- tỷ lệ không di chuyển rất cao;
- giá trị chuyến trung bình thấp.

### Nhận xét Anti-Fraud

Đây là pattern phù hợp với giả thuyết trip farming hoặc ghost-trip:

```text
Nhiều chuyến
+
ít hoặc không di chuyển
+
giá trị trung bình thấp
+
lặp lại trên cùng pair
```

Những case này nên được ưu tiên manual review.

---

## 3.6 Dữ liệu đầu ra đã đủ nền tảng cho explainability

File hiện tại đã có các trường:

- mã tài xế;
- mã khách hàng;
- số chuyến;
- mức độ tập trung;
- điểm pair core;
- điểm liên kết;
- điểm ưu tiên;
- cấp liên kết;
- kích thước nhóm;
- tỷ lệ không di chuyển;
- giá trị trung bình.

Đây là một nền tảng tốt để tạo:

- dashboard;
- case list;
- investigation queue;
- Cypher visualization;
- evidence report.

---

# 4. Những phần cần cải thiện

## 4.1 WCC đang tạo ra một giant component

Đây là vấn đề nghiêm trọng nhất trong kết quả hiện tại.

Trong 1.226 pair:

- **1.223 pair** có `Kích thước nhóm = 1.612`;
- chỉ **3 pair** có kích thước nhóm bằng 1.

Điều này có nghĩa gần như toàn bộ suspicious graph đã bị nối thành một component duy nhất.

```text
1.223 pair nghi ngờ
        ↓
Một giant component có 1.612 thành viên
```

### Tác động

WCC gần như không còn khả năng:

- tách case;
- phát hiện ring riêng biệt;
- hỗ trợ analyst điều tra theo cụm;
- phân biệt network mạnh và network yếu.

Một component 1.612 node không nên được diễn giải là một fraud ring duy nhất.

### Nguyên nhân có thể

Graph có thể đang nối pair qua các entity quá phổ biến:

- shared promo;
- shared address công cộng;
- payment method chung;
- route key quá rộng;
- Driver hoặc Customer có degree rất lớn;
- entity chỉ cần xuất hiện một lần đã đủ tạo edge.

### Cải thiện đề xuất

Trước WCC cần bổ sung:

```text
Hub filtering
Rarity weighting
Minimum shared-evidence support
Edge thresholding
```

Ví dụ:

\[
rarity(e)=\log\left(\frac{N}{1+degree(e)}\right)
\]

Chỉ nên tạo edge giữa hai pair khi:

- cùng dùng entity đủ hiếm;
- có ít nhất 2 bằng chứng hỗ trợ;
- edge weight vượt threshold;
- entity không nằm trong danh sách hub toàn hệ thống.

---

## 4.2 Điểm liên kết đang bị dồn vào một số mức gần cố định

Phần lớn `Diem lien ket` tập trung tại:

| Điểm liên kết | Số pair |
|---:|---:|
| 70,67 | 80 |
| 75,67 | 460 |
| 80,67 | 626 |
| 85,67 | 38 |

Hơn 90% pair nằm trong khoảng rất hẹp từ 75,67 đến 80,67.

### Tác động

`Diem lien ket` hiện không đủ khả năng phân biệt:

- pair nằm ở trung tâm network;
- pair chỉ bị nối gián tiếp;
- pair có nhiều evidence hiếm;
- pair bị nối do hub phổ biến.

### Nguyên nhân có thể

- giant component làm phần lớn pair nhận cùng bonus;
- score được tính theo các bậc rời rạc;
- component size có trọng số quá lớn;
- degree thô được dùng thay cho weighted suspicious degree.

### Cải thiện đề xuất

Thay vì dựa nhiều vào component size, nên dùng:

```text
suspicious_degree
weighted_suspicious_degree
rare_shared_entity_count
high_risk_neighbor_ratio
average_neighbor_pair_score
local_density
```

Ví dụ:

\[
high\_risk\_neighbor\_ratio=
\frac{\#\text{high-risk neighbors}}
{\#\text{all suspicious neighbors}}
\]

và:

\[
neighbor\_risk=
\frac{\sum pair\_score_j \times edge\_weight_{ij}}
{\sum edge\_weight_{ij}}
\]

---

## 4.3 Điểm ưu tiên gần như bị pair core chi phối hoàn toàn

Tương quan giữa:

```text
Diem pair core và Diem uu tien ≈ 0,984
```

Trong khi tương quan giữa:

```text
Diem lien ket và Diem uu tien ≈ 0,120
```

Điều này cho thấy graph score hiện gần như không thay đổi thứ hạng pair.

### Nhận xét

Nếu mục tiêu của pipeline là chứng minh graph giúp tăng giá trị điều tra, kết quả hiện tại chưa thể hiện được điều đó.

### Cải thiện đề xuất

Tách rõ:

```text
pair_risk_score
network_risk_score
business_impact_score
investigation_priority_score
```

Ví dụ:

\[
priority=
0.65\times pair\_risk+
0.20\times network\_risk+
0.15\times impact
\]

Chỉ nên áp dụng trọng số network sau khi graph đã xử lý giant component và hub.

---

## 4.4 Toàn bộ case đều cùng nhãn “Cần theo dõi”

File có score ưu tiên từ:

```text
38,21 đến 94,04
```

nhưng toàn bộ 1.226 pair đều được gắn:

```text
Cần theo dõi
```

### Tác động

Analyst không biết:

- case nào cần mở ngay;
- case nào chỉ cần theo dõi;
- case nào có thể bỏ qua;
- case nào có evidence ghost mạnh.

### Cải thiện đề xuất

Tạo nhiều tier:

```text
Priority >= 80:
Điều tra ngay

65 <= Priority < 80:
Rủi ro cao

50 <= Priority < 65:
Cần theo dõi

Priority < 50:
Theo dõi thấp
```

Ngoài threshold điểm, nên có hard override:

```text
ghost_rate >= 0.8
AND n_trips >= 10
→ High confidence
```

hoặc:

```text
pair_core >= 70
AND concentration >= 0.8
→ High priority
```

---

## 4.5 Ghost signal gần như chưa ảnh hưởng đến ranking

Tỷ lệ không di chuyển có nhiều case rất mạnh, nhưng tương quan với `Diem uu tien` chỉ khoảng:

```text
0,019
```

Nghĩa là ghost evidence gần như không đóng góp vào priority ranking.

### Tác động

Tên bài toán là `Ghost-Trip Collusion`, nhưng ranking hiện chủ yếu phản ánh:

```text
Volume + Concentration
```

chưa phản ánh đúng:

```text
Ghost evidence + Operational anomaly
```

### Cải thiện đề xuất

Tạo riêng:

```text
suspected_ghost_score
```

Ví dụ:

\[
ghost\_score=
ghost\_rate
\times coverage\_factor
\times support\_factor
\]

Sau đó có thể dùng:

\[
fraud\_risk=
0.40\times pair\_core+
0.30\times ghost\_score+
0.20\times temporal\_score+
0.10\times network\_score
\]

Nếu chưa có temporal score, có thể tạm dùng:

\[
fraud\_risk=
0.55\times pair\_core+
0.30\times ghost\_score+
0.15\times network\_score
\]

Không nên gọi `avg_kmh = 0` trực tiếp là ghost trip chắc chắn. Nên sử dụng tên:

```text
suspected_ghost_rate
zero_speed_completed_rate
```

cho đến khi có analyst confirmation hoặc ground truth.

---

## 4.6 Concentration cao ở sample nhỏ vẫn có nguy cơ bị đánh giá quá mạnh

Có **64 pair** thỏa:

```text
Số chuyến <= 10
và concentration >= 0,75
```

Một số pair có:

```text
7 chuyến, concentration = 1,0
8 chuyến, concentration = 1,0
9 chuyến, concentration = 1,0
10 chuyến, concentration = 1,0
```

Những pair này đáng chú ý, nhưng không nên được đánh đồng với:

```text
30/30 chuyến
40/40 chuyến
```

### Cải thiện đề xuất

Thêm support factor:

\[
support\_factor=
\min\left(
1,
\frac{\log(1+n\_trips)}
{\log(1+K)}
\right)
\]

Sau đó:

\[
adjusted\_concentration=
raw\_concentration\times support\_factor
\]

Nên lưu cả:

```text
raw_concentration
support_factor
adjusted_concentration
```

để vừa scoring tốt vừa explain được.

---

## 4.7 Volume threshold nên được tính theo cohort

Hiện kết quả đang trộn nhiều pattern hoạt động có thể khác nhau.

Một ngưỡng global có thể làm:

- service phổ biến kéo threshold lên;
- service ít chuyến bị đánh giá lệch;
- airport hoặc scheduled trip bị xem như outlier;
- khác biệt vùng miền bị bỏ qua.

### Cải thiện đề xuất

Tính volume percentile theo cohort:

```text
service_type
province / region
scheduled vs on-demand
analysis window
driver activity bucket
```

Output nên lưu:

```text
volume_cohort
trip_count_percentile
cohort_trip_threshold
volume_score
```

---

## 4.8 Pattern “nhiều chuyến nhưng giá trị thấp” chưa được dùng đủ

Tương quan giữa:

```text
Số chuyến và Giá trị trung bình ≈ -0,394
```

Điều này cho thấy pair nhiều chuyến thường có giá trị chuyến thấp hơn.

Một số pair có:

```text
102 chuyến, giá trị trung bình 15.049
70 chuyến, giá trị trung bình 15.943
67 chuyến, giá trị trung bình 16.806
38 chuyến, giá trị trung bình 13.605
```

Trong khi giá trị trung bình toàn tập khoảng:

```text
188.200
```

### Nhận xét Anti-Fraud

Pattern này có thể phản ánh:

```text
High frequency
+
Low value
+
High ghost evidence
```

đây là một tín hiệu farming đáng chú ý.

### Cải thiện đề xuất

Bổ sung:

```text
avg_gmv_percentile_by_service
low_value_trip_ratio
median_gmv
high_frequency_low_value_score
```

Ví dụ:

\[
farming\_intensity=
volume\_score\times(1-avg\_gmv\_percentile)
\]

---

# 5. Các nhóm case nên ưu tiên manual review

## Nhóm A — Volume rất cao và tỷ lệ không di chuyển 100%

Ví dụ:

```text
102 chuyến
concentration = 0,5667
ghost rate = 100%
avg value = 15.049
```

Đây là case có bằng chứng mạnh vì hội tụ:

- volume cực cao;
- không di chuyển;
- giá trị thấp;
- lặp trên cùng pair.

---

## Nhóm B — Volume cao, concentration khá và ghost rate rất cao

Ví dụ:

```text
67 chuyến
concentration = 0,6321
ghost rate = 100%
avg value = 16.806
```

```text
65 chuyến
concentration = 0,6989
ghost rate = 90,8%
avg value = 44.154
```

Nhóm này nên được ưu tiên kiểm tra:

- timeline;
- operational gap;
- pickup/dropoff;
- actual distance;
- payment;
- discount;
- route pattern.

---

## Nhóm C — Concentration cực cao nhưng ghost rate bằng 0

Ví dụ:

```text
41 chuyến
concentration = 0,9762
ghost rate = 0%
```

Nhóm này có thể là:

- collusion không tạo zero-speed signal;
- usage hợp lệ nhưng rất tập trung;
- customer doanh nghiệp;
- scheduled ride;
- ghost definition chưa bao phủ đủ.

Không nên kết luận fraud chỉ từ concentration. Cần kiểm tra thêm temporal, route và business context.

---

# 6. Kiến trúc cải thiện đề xuất

```text
1. Data contract và quality checks
   ↓
2. Pair feature table
   ↓
3. Volume score theo cohort
   ↓
4. Raw concentration
   ↓
5. Support-adjusted concentration
   ↓
6. Suspected ghost score
   ↓
7. Temporal anomaly score
   ↓
8. Low-value farming score
   ↓
9. Composite pair risk
   ↓
10. Seed suspicious pairs
   ↓
11. Hub-aware graph expansion
   ↓
12. WCC
   ↓
13. Component validation
   ↓
14. Network risk score
   ↓
15. Investigation priority tiers
```

---

# 7. Đề xuất công thức scoring phiên bản tiếp theo

## 7.1 Pair collusion score

\[
pair\_collusion=
0.45\times volume\_score+
0.55\times adjusted\_concentration
\]

Concentration được ưu tiên nhẹ hơn volume vì gần với bản chất collusion hơn.

## 7.2 Ghost-trip evidence score

\[
ghost\_evidence=
0.50\times suspected\_ghost\_rate+
0.30\times temporal\_score+
0.20\times low\_value\_farming\_score
\]

## 7.3 Final fraud risk

\[
fraud\_risk=
0.55\times pair\_collusion+
0.30\times ghost\_evidence+
0.15\times network\_risk
\]

## 7.4 Investigation priority

\[
priority=
0.80\times fraud\_risk+
0.20\times business\_impact
\]

Các trọng số trên là baseline khởi đầu, cần được hiệu chỉnh bằng analyst review.

---

# 8. Output nên bổ sung

## 8.1 Pair-level output

```text
pair_id
driver_id
customer_id
window_start
window_end
trip_count
trip_count_percentile
volume_score
pair_share_driver
pair_share_customer
raw_concentration
support_factor
adjusted_concentration
suspected_ghost_rate
temporal_score
low_value_farming_score
pair_collusion_score
fraud_risk_score
impact_score
priority_score
risk_tier
reason_codes
```

## 8.2 Component-level output

```text
component_id
driver_count
customer_count
pair_count
high_risk_pair_count
high_risk_pair_ratio
average_pair_score
maximum_pair_score
rare_shared_entity_count
weighted_internal_edge_sum
component_density
network_risk_score
component_risk_tier
```

## 8.3 Evidence-level output

```text
case_id
pair_id
order_id
evidence_type
observed_value
expected_value
threshold
score_contribution
event_time
data_quality_level
description
```

---

# 9. Thứ tự ưu tiên cải thiện

## Ưu tiên 1 — Sửa graph construction và giant component

Đây là vấn đề cần sửa trước tiên vì WCC hiện chưa phân cụm hiệu quả.

Thực hiện:

- hub filtering;
- rarity weighting;
- edge thresholding;
- component-size monitoring;
- shared-evidence minimum support.

---

## Ưu tiên 2 — Đưa ghost evidence vào scoring

Ghost signal hiện có giá trị lớn nhưng gần như chưa ảnh hưởng ranking.

Thực hiện:

- tạo `suspected_ghost_score`;
- thêm coverage factor;
- thêm support factor;
- thêm hard override cho ghost rate rất cao.

---

## Ưu tiên 3 — Chia priority thành nhiều tier

Không nên để toàn bộ 1.226 pair cùng nhãn.

Tạo:

- Immediate Review;
- High Risk;
- Monitor;
- Low Priority.

---

## Ưu tiên 4 — Điều chỉnh concentration theo support

Giảm false positive từ pair có concentration 100% nhưng chỉ có ít chuyến.

---

## Ưu tiên 5 — Tính volume score theo cohort

Giảm bias giữa service, vùng và activity profile.

---

## Ưu tiên 6 — Thêm temporal và low-value pattern

Tăng precision cho đúng giả thuyết Ghost-Trip Collusion.

---

# 10. Kết luận

Pipeline hiện tại đã làm tốt phần cốt lõi:

```text
Pair-first analysis
+
Volume anomaly
+
Mutual concentration
+
Explainable pair scoring
```

Đây là một baseline tốt và đã tìm ra nhiều case đáng kiểm tra, đặc biệt là các pair có:

```text
Volume cao
+
Tỷ lệ không di chuyển cao
+
Giá trị trung bình thấp
```

Tuy nhiên, ba hạn chế lớn nhất hiện nay là:

1. **WCC tạo giant component**, làm mất khả năng phân cụm.
2. **Ghost evidence chưa ảnh hưởng đáng kể đến priority ranking**.
3. **Toàn bộ case cùng một nhãn ưu tiên**, khiến output chưa dùng tốt cho Anti-Fraud Ops.

Vì vậy, phiên bản tiếp theo chưa cần ưu tiên thêm nhiều thuật toán graph mới. Việc quan trọng hơn là:

```text
Sửa graph construction
+
Hiệu chỉnh score
+
Tách risk tier
+
Tăng explainability
```

Sau khi hoàn thiện các phần này, WCC và các thuật toán như Pair Similarity hoặc Leiden mới có thể tạo thêm giá trị thực sự cho quá trình phát hiện fraud ring và điều tra network.
