# Báo Cáo Rà Soát `property` / `relationship` Cho Dữ Liệu `ride` Và `food`

## Phạm vi rà soát

Tài liệu này được viết lại sau khi đối chiếu trực tiếp với implementation hiện tại của project.

Mục tiêu của báo cáo là mô tả đúng phần đang được thực thi trong project hiện tại, không dựa trên schema kỳ vọng hay định hướng tương lai.

## Kết luận nhanh

Project hiện tại đang dùng mô hình `Order` làm node trung tâm cho cả `food` và `ride`.

- Các trường mang tính metric, trạng thái, thời gian và một phần taxonomy dịch vụ đang được giữ trên node `Order` dưới dạng `property`.
- Các thực thể dùng chung giữa nhiều order đang được tách ra thành node riêng và nối bằng `relationship`.
- Một số trường hiện được lưu đồng thời theo cả hai cách:
  - vừa là `property` trên `Order`
  - vừa là `relationship` sang node chuẩn hóa

Điều này đang xảy ra với các nhóm như:

- `cancel_by`
- `cancel_description`
- `service_name`
- `service_type`
- `sub_vertical_name`
- `travel_mode`
- `channel_type`

Nói cách khác, implementation hiện tại không tách hoàn toàn theo kiểu “chỉ property” hoặc “chỉ relationship”, mà đang dùng mô hình lai để vừa tiện filter/dashboard, vừa tiện graph traversal.

## 1. Những gì đang là `property` trên node `Order`

Theo `ORDER_PROPERTY_SPECS` trong `scripts/import_ride_daily_to_neo4j.py`, node `Order` hiện giữ các nhóm thuộc tính sau.

### 1.1. Định danh và thời gian

- `order_id`
- `domain`
- `order_time`
- `completed_at`
- `order_hour`
- `order_weekday`

Ghi chú:

- `order_time_local_tz` và `complete_time_local_tz` được chuẩn hóa sang định dạng `YYYY-MM-DDTHH:MM:SS` trước khi ghi ra file import.

### 1.2. Trạng thái và cờ nghiệp vụ

- `status`
- `cancel_by`
- `cancel_description`
- `is_now_order`
- `is_schedule_order`
- `is_completed`
- `is_cancelled`
- `has_promotion`
- `has_dropoff_fail`

### 1.3. Taxonomy dịch vụ

- `service_name`
- `service_type`
- `sub_vertical_name`
- `vertical_name`
- `travel_mode`
- `channel_type`
- `food_dispatch_type`

Điểm quan trọng:

- `vertical_name` hiện chỉ là `property`, chưa được tách thành node/relationship.
- Các trường còn lại trong nhóm taxonomy có mặt cả ở `property` lẫn `relationship`.

### 1.4. Metric tài chính và vận hành

- `declared_km`
- `actual_km`
- `km_diff`
- `intrip_time_second`
- `lead_time_second`
- `gmv`
- `commission`
- `net_income`
- `discount`
- `delivery_discount`
- `food_gmv`
- `food_total_paid`
- `food_total_item_quantity`

### 1.5. Rating

- `rate_by_customer`
- `rate_by_driver`

## 2. Những gì đang được tách thành node riêng

Từ `HEADERS` và phần ghi node output, project hiện đang tạo các node sau:

- `Order`
- `Customer`
- `Driver`
- `Merchant`
- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`
- `CancelActor`
- `CancelReason`
- `DropoffFailActor`
- `DropoffFailCode`
- `RideService`
- `ServiceType`
- `SubVertical`
- `TravelMode`
- `ChannelType`

Ghi chú:

- `Merchant` chủ yếu có ý nghĩa cho `food`, nhưng importer vẫn hỗ trợ thống nhất trong một pipeline.
- Các node taxonomy của ride hiện không chỉ dành riêng cho `ride`; importer vẫn ghi chúng nếu cột nguồn có dữ liệu.

## 3. Những `relationship` đang thực sự được tạo

Project hiện đang ghi các file relationship sau:

- `PLACED`
- `SERVED`
- `FROM_MERCHANT`
- `PICKUP_AT`
- `DROPOFF_AT`
- `PAID_BY`
- `USED_PROMO`
- `IN_CAMPAIGN`
- `CANCELLED_BY`
- `HAS_CANCEL_REASON`
- `DROPOFF_FAILED_BY`
- `HAS_DROPOFF_FAIL_CODE`
- `USES_SERVICE`
- `USES_SERVICE_TYPE`
- `USES_SUB_VERTICAL`
- `USES_TRAVEL_MODE`
- `USES_CHANNEL_TYPE`

Hướng nối hiện tại:

- `(:Customer)-[:PLACED]->(:Order)`
- `(:Driver)-[:SERVED]->(:Order)`
- `(:Order)-[:FROM_MERCHANT]->(:Merchant)`
- `(:Order)-[:PICKUP_AT]->(:Address)`
- `(:Order)-[:DROPOFF_AT]->(:Address)`
- `(:Order)-[:PAID_BY]->(:PaymentMethod)`
- `(:Order)-[:USED_PROMO]->(:PromotionCode)`
- `(:PromotionCode)-[:IN_CAMPAIGN]->(:PromotionCampaign)`
- `(:Order)-[:CANCELLED_BY]->(:CancelActor)`
- `(:Order)-[:HAS_CANCEL_REASON]->(:CancelReason)`
- `(:Order)-[:DROPOFF_FAILED_BY]->(:DropoffFailActor)`
- `(:Order)-[:HAS_DROPOFF_FAIL_CODE]->(:DropoffFailCode)`
- `(:Order)-[:USES_SERVICE]->(:RideService)`
- `(:Order)-[:USES_SERVICE_TYPE]->(:ServiceType)`
- `(:Order)-[:USES_SUB_VERTICAL]->(:SubVertical)`
- `(:Order)-[:USES_TRAVEL_MODE]->(:TravelMode)`
- `(:Order)-[:USES_CHANNEL_TYPE]->(:ChannelType)`

## 4. Các nhóm dữ liệu đang dùng mô hình lai

Đây là phần khác biệt quan trọng nhất so với cách hiểu “property hoặc relationship”.

### 4.1. Nhóm cancel

Hiện tại:

- `cancel_by` nằm trên `Order.status context` dưới dạng property
- đồng thời tạo node `CancelActor` và quan hệ `CANCELLED_BY`

- `cancel_description` nằm trên `Order`
- đồng thời tạo node `CancelReason` và quan hệ `HAS_CANCEL_REASON`

Ý nghĩa:

- thuận tiện cho dashboard và export vì vẫn đọc được ngay trên `Order`
- vẫn có thể group/traverse theo actor hoặc reason trong graph

### 4.2. Nhóm service taxonomy

Các trường sau đều đang xuất hiện ở cả hai lớp:

- `service_name`
- `service_type`
- `sub_vertical_name`
- `travel_mode`
- `channel_type`

Hiện trạng này phù hợp với mục tiêu:

- `property` để lọc nhanh, hiển thị, làm feature
- `relationship` để gom cụm hoặc phân tích shared structure

### 4.3. Khác biệt trong cùng nhóm taxonomy

`vertical_name` là ngoại lệ:

- hiện chỉ được giữ trên `Order`
- chưa có node `Vertical` hay quan hệ kiểu `USES_VERTICAL`

Nếu sau này cần graph analysis theo `vertical_name`, đây là phần chưa được triển khai.

## 5. Những gì không nằm trên `Order` trong implementation hiện tại

Một số field quan trọng đang được tách sang node/relationship và không được giữ lại trên node `Order` trong output import:

- `customer_id`
- `driver_id`
- `merchant_id`
- `payment_method`
- `promotion_code`
- `promotion_campaign_code`
- `food_dropoff_fail_by`
- `food_dropoff_fail_code`
- thông tin địa chỉ pickup/dropoff dạng raw

Điểm này quan trọng vì note cũ dễ tạo cảm giác rằng một số field có thể vừa giữ trên `Order` vừa không. Với implementation hiện tại thì:

- các field trên được dùng để tạo node/relationship
- nhưng không nằm trong danh sách `ORDER_FIELDS`
- nên không trở thành property của node `Order` sau bước import này

## 6. Khác biệt giữa `food` và `ride` trong implementation hiện tại

### 6.1. Nhóm thiên về `food`

Thường chỉ có dữ liệu thực tế cho:

- `merchant_id`
- `food_dispatch_type`
- `food_gmv`
- `food_total_paid`
- `food_total_item_quantity`
- `food_dropoff_fail_by`
- `food_dropoff_fail_code`

Tương ứng, `food` là domain hưởng lợi rõ nhất từ:

- `FROM_MERCHANT`
- `DROPOFF_FAILED_BY`
- `HAS_DROPOFF_FAIL_CODE`

### 6.2. Nhóm thiên về `ride`

Thường gắn mạnh với:

- `declared_km`
- `actual_km`
- `km_diff`
- `intrip_time_second`
- `travel_mode`
- `service_name`
- `service_type`
- `sub_vertical_name`
- `channel_type`

Tương ứng, `ride` là domain hưởng lợi rõ nhất từ:

- `USES_SERVICE`
- `USES_SERVICE_TYPE`
- `USES_SUB_VERTICAL`
- `USES_TRAVEL_MODE`
- `USES_CHANNEL_TYPE`

### 6.3. Phần chung giữa hai domain

Cả `food` và `ride` đang dùng chung các cấu phần cốt lõi:

- `Order`
- `Customer`
- `Driver`
- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`
- `PLACED`
- `SERVED`
- `PICKUP_AT`
- `DROPOFF_AT`
- `PAID_BY`
- `USED_PROMO`
- `IN_CAMPAIGN`

## 7. Chuẩn hóa địa chỉ đang được làm như thế nào

Địa chỉ không được giữ nguyên như một ID nguồn mà đang được chuẩn hóa theo quy trình:

1. Chuẩn hóa Unicode bằng `NFKC`
2. `casefold`
3. trim khoảng trắng
4. co cụm khoảng trắng lặp
5. ghép `province | district | address`
6. băm SHA-1 để tạo `address_key`

Ý nghĩa:

- cùng một địa chỉ viết khác format vẫn có thể map về cùng một `Address`
- graph giảm trùng node địa chỉ

Lưu ý:

- nếu thiếu text địa chỉ gốc thì sẽ không tạo `Address` node/relationship

## 8. Data quality check đang có thật trong code

Phần này cần tách bạch với mong muốn nghiệp vụ.

Hiện tại `quality_report()` mới kiểm tra 4 điều:

- thiếu `order_id`
- thiếu `customer_id`
- thiếu `order_time_local_tz`
- trùng `order_id`

Vì vậy:

- các kiểm tra như numeric invalid, empty shared signal, missing anomaly score, missing rule field
- hiện chưa có trong importer này

Nếu tài liệu muốn mô tả “đang chạy trong project”, thì không nên ghi các check đó như thể đã được thực thi.

## 9. Những điểm tài liệu cũ cần chỉnh lại

Sau khi đối chiếu code, các điểm sau cần sửa trong cách mô tả:

### 9.1. Không nên mô tả `note` như một thành phần schema đang được triển khai

Trong code hiện tại:

- không có cấu trúc lưu `modeling_note`, `domain_note`, `quality_note`
- `note` chỉ nên được hiểu là tài liệu giải thích, không phải output dữ liệu của importer

### 9.2. Không nên ghi các entity chưa có implementation như thể đã tồn tại

Hiện chưa thấy importer này tạo:

- `Rule`
- `ModelScore`
- `FLAGGED_BY`
- `SCORED_BY`

Các entity đó có thể thuộc lớp enrichment/storytelling khác, nhưng không phải phần import order graph cơ sở hiện tại.

### 9.3. Cần nêu rõ mô hình lai thay vì chia cứng

Thực tế hiện tại là:

- có nhóm “chỉ property”
- có nhóm “chỉ relationship”
- có nhóm “property + relationship song song”

Đây là mô tả đúng hơn so với phân loại nhị phân đơn giản.

## 10. Kết luận cuối cùng

Nếu bám đúng implementation hiện tại của project, có thể chốt như sau:

- `Order` là node trung tâm cho cả `food` và `ride`
- metric, thời gian, trạng thái và một phần taxonomy đang nằm trên `Order` dưới dạng `property`
- customer, driver, merchant, promo, payment, address và nhiều shared entity khác đang được tách sang node riêng
- một số nhóm quan trọng như cancel và service taxonomy đang được lưu theo mô hình lai: vừa property vừa relationship
- `note` hiện chỉ nên là tài liệu mô tả quyết định modeling, không phải thành phần dữ liệu của pipeline import

Vì vậy, báo cáo đúng với trạng thái project hiện tại không nên viết theo hướng “nên làm gì” là chính, mà nên ghi rõ:

- phần nào đã triển khai
- phần nào đang là giả định
- phần nào vẫn chưa có trong importer hiện tại
