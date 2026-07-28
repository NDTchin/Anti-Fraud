# Phân Tích Cách Chia `note`, `relationship`, `property` Cho Dữ Liệu `ride` Và `food`

## Mục tiêu

Tài liệu này mô tả cách tách dữ liệu giữa:

- `property`: thuộc tính lưu trực tiếp trên node, chủ yếu là `Order`
- `relationship`: liên kết giữa `Order` và các thực thể dùng lại nhiều lần
- `note`: phần ghi chú phân tích, dùng để giải thích khác biệt mô hình giữa `ride` và `food`

Mục tiêu chính là giữ graph dễ đọc, tránh lặp dữ liệu, và thuận tiện cho các bài toán fraud detection trên Neo4j.

## Nguyên tắc chung

### 1. Đưa vào `property` khi giá trị gắn chặt với một order

Một trường nên là `property` nếu:

- chỉ có ý nghĩa trong phạm vi một order
- ít được dùng để nối nhiều order với nhau
- thường được dùng để filter, sort, scoring, dashboard
- giá trị biến động theo từng order

Ví dụ:

- `gmv`
- `discount`
- `food_total_paid`
- `declared_km`
- `actual_km`
- `lead_time_second`
- `is_completed`
- `is_cancelled`
- `order_time`
- `order_hour`

Các trường này hiện phù hợp để đặt trên node `Order`.

### 2. Đưa vào `relationship` khi giá trị là một thực thể dùng chung

Một trường nên tách thành node riêng và nối qua `relationship` nếu:

- nhiều order có thể cùng tham chiếu tới một giá trị
- giá trị đó là tín hiệu để nối cụm nghi vấn
- cần đếm mức độ dùng chung giữa nhiều customer, driver, order
- cần truy vấn theo pattern graph thay vì chỉ lọc theo cột

Ví dụ:

- `customer_id` -> `(:Customer)-[:PLACED]->(:Order)`
- `driver_id` -> `(:Driver)-[:SERVED]->(:Order)`
- `merchant_id` -> `(:Order)-[:FROM_MERCHANT]->(:Merchant)`
- `payment_method` -> `(:Order)-[:PAID_BY]->(:PaymentMethod)`
- `promotion_code` -> `(:Order)-[:USED_PROMO]->(:PromotionCode)`
- `promotion_campaign_code` -> `(:PromotionCode)-[:IN_CAMPAIGN]->(:PromotionCampaign)`
- địa chỉ pickup/dropoff -> `(:Order)-[:PICKUP_AT|DROPOFF_AT]->(:Address)`

Đây là nhóm tín hiệu mạnh để tìm shared entities, collusion ring, promo abuse, account farming.

### 3. Giữ `note` cho phần giải thích nghiệp vụ, không dùng thay cho schema

`note` không nên là nơi chứa dữ liệu lõi để phân tích graph.

`note` chỉ nên dùng cho:

- giải thích vì sao một field được đặt ở `property` hay `relationship`
- mô tả field nào chỉ có ở `food` hoặc chỉ có ở `ride`
- ghi lại giả định mapping khi raw data chưa đồng nhất
- nêu các rủi ro false positive hoặc data quality

Nếu một thông tin cần dùng để query, score, detect hoặc visualize nhiều lần thì không nên chỉ nằm trong `note`.

## Cách chia theo thực thể hiện tại

## `Order` làm node trung tâm

Node `Order` nên là trung tâm của cả hai domain vì:

- mọi hành vi fraud cuối cùng vẫn quy về một giao dịch
- dễ giữ chung một pattern cho `food` và `ride`
- tiện mở rộng dashboard và feature engineering

Các `property` đang hợp lý trên `Order`:

- định danh và thời gian: `order_id`, `domain`, `order_time`, `completed_at`, `order_hour`, `order_weekday`
- trạng thái: `status`, `is_completed`, `is_cancelled`, `cancel_by`, `cancel_description`
- tiền: `gmv`, `commission`, `net_income`, `discount`, `delivery_discount`
- food-specific metric: `food_gmv`, `food_total_paid`, `food_total_item_quantity`, `food_dispatch_type`
- ride-specific metric: `declared_km`, `actual_km`, `km_diff`, `intrip_time_second`
- ngữ cảnh đơn hàng: `is_now_order`, `is_schedule_order`, `has_promotion`, `has_dropoff_fail`
- phân loại dịch vụ: `service_name`, `service_type`, `sub_vertical_name`, `vertical_name`, `travel_mode`, `channel_type`
- rating: `rate_by_customer`, `rate_by_driver`

## Nhóm `relationship` dùng chung cho cả hai domain

Các quan hệ chung nên giữ thống nhất giữa `ride` và `food`:

| Relationship | Ý nghĩa |
|---|---|
| `PLACED` | customer tạo order |
| `SERVED` | driver phục vụ order |
| `PICKUP_AT` | điểm lấy hàng hoặc đón khách |
| `DROPOFF_AT` | điểm giao hàng hoặc trả khách |
| `PAID_BY` | phương thức thanh toán |
| `USED_PROMO` | mã khuyến mãi được dùng |
| `IN_CAMPAIGN` | promo code thuộc campaign nào |
| `CANCELLED_BY` | actor gây hủy |
| `HAS_CANCEL_REASON` | lý do hủy |

Lợi ích của nhóm quan hệ chung:

- thống nhất cách viết query liên domain
- tái sử dụng rule và dashboard
- giảm số lượng schema đặc thù không cần thiết

## Nhóm `relationship` đặc thù `food`

`food` có thêm thực thể merchant và lỗi giao đồ ăn:

| Relationship | Ý nghĩa |
|---|---|
| `FROM_MERCHANT` | order đến từ merchant nào |
| `DROPOFF_FAILED_BY` | actor gây lỗi giao đồ ăn |
| `HAS_DROPOFF_FAIL_CODE` | mã lỗi giao đồ ăn |

Khuyến nghị:

- `merchant_id` nên là node riêng vì có tính share rất mạnh giữa nhiều order
- `food_dropoff_fail_by` và `food_dropoff_fail_code` nên là node riêng nếu team muốn truy vết cụm issue hoặc abuse theo loại lỗi

## Nhóm `relationship` đặc thù `ride`

`ride` có thêm nhóm phân loại dịch vụ:

| Relationship | Ý nghĩa |
|---|---|
| `USES_SERVICE` | order dùng service nào |
| `USES_SERVICE_TYPE` | thuộc loại service nào |
| `USES_SUB_VERTICAL` | thuộc sub-vertical nào |
| `USES_TRAVEL_MODE` | travel mode nào |
| `USES_CHANNEL_TYPE` | order đi qua channel nào |

Khuyến nghị:

- vẫn có thể giữ các field này trên `Order` để filter nhanh
- đồng thời tạo node + relationship nếu muốn phân tích mật độ dùng chung và cấu trúc cụm theo loại dịch vụ

Nói cách khác, đây là nhóm dữ liệu có thể xuất hiện ở cả `property` lẫn `relationship` mà không mâu thuẫn, vì hai mục đích khác nhau:

- `property`: phục vụ dashboard, export, scoring
- `relationship`: phục vụ graph traversal và pattern detection

## Khi nào không nên tách ra node riêng

Không nên tách ra node riêng nếu field:

- cardinality quá cao và gần như 1-1 với order
- ít giá trị phân tích dùng chung
- chỉ phục vụ hiển thị chi tiết
- làm graph phình lớn nhưng ít giá trị kết nối

Ví dụ thường nên giữ ở `property`:

- `gmv`
- `net_income`
- `lead_time_second`
- `intrip_time_second`
- `rate_by_customer`
- `rate_by_driver`

## Gợi ý sử dụng `note`

Nếu cần thêm cột hoặc tài liệu `note`, nên chia thành 3 nhóm:

| Nhóm note | Nội dung |
|---|---|
| `modeling_note` | lý do chọn property hay relationship |
| `domain_note` | field chỉ áp dụng cho ride hoặc food |
| `quality_note` | thiếu dữ liệu, null rate cao, mapping còn giả định |

Ví dụ:

| Field | Kiểu lưu | Note |
|---|---|---|
| `merchant_id` | `relationship` | Chỉ áp dụng cho `food`, là shared entity mạnh để gom cụm merchant abuse |
| `actual_km` | `property` | Chỉ áp dụng cho `ride`, chủ yếu dùng tính feature chứ không tạo shared graph entity |
| `promotion_code` | `relationship` | Dùng chung nhiều order, rất quan trọng cho promo abuse |
| `cancel_description` | `relationship` + `property` | Có thể giữ text trên order để đọc nhanh, đồng thời nối sang `CancelReason` để thống kê |

## Đề xuất thực hành cho dự án này

### Nên giữ làm `property`

- toàn bộ metric số học theo order
- cờ boolean theo trạng thái order
- timestamp và time bucket
- các field cần hiển thị trực tiếp trên dashboard

### Nên giữ làm `relationship`

- customer
- driver
- merchant
- payment method
- promotion code
- promotion campaign
- address pickup/dropoff
- cancel actor
- cancel reason
- dropoff fail actor/code
- service taxonomy của ride khi cần graph analysis

### Nên giữ làm `note`

- giải thích business meaning của field
- khác biệt coverage giữa `food` và `ride`
- giả định chuẩn hóa dữ liệu
- cảnh báo field đang null nhiều hoặc chưa ổn định

## Kết luận

Với dữ liệu `ride` và `food`, cách chia hợp lý nhất là:

- dùng `Order` làm node trung tâm
- giữ các metric và trạng thái theo giao dịch ở `property`
- tách các thực thể dùng chung, có khả năng nối nhiều order, sang `relationship`
- dùng `note` để giải thích quyết định mô hình và khác biệt domain, không dùng `note` thay cho dữ liệu phân tích

Cách chia này vừa bám sát importer hiện tại, vừa hỗ trợ tốt cho fraud graph, dashboard, và mở rộng schema sau này.
