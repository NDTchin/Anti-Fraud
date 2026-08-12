# Fraud Rules

## Mục đích tài liệu

Tai liệu này giải thích bộ fraud rules hiện tại cho bài toán `ride` theo cách:

- đổi vận hành đọc được
- business đọc được
- product đọc được
- data team vẫn đối chiếu được với code

Tai liệu nay không có mục tiêu mô tả tất cả công thức kỹ thuật. Mục tiêu chính là giúp người đọc trả lời 4 câu hỏi:

1. Hệ thống đang tìm mẫu gian lận nào?
2. Hệ thống dựa vào bằng chứng nào để gọi là đáng nghi?
3. Kết quả đang được đưa ra dashboard theo đơn vị nào?
4. Người đọc cần hiểu các cảnh báo này ra sao để tránh hiểu sai?

## Cách hiểu tổng quan

Hệ thống đi theo thứ tự:

1. Đọc dữ liệu chuyến xe `ride`
2. Gom theo cặp `tài xế - khách hàng`
3. Tìm các cặp lặp lại bất thường
4. Kiểm tra thêm dấu hiệu đơn ảo, quay đầu nhanh, route lặp, và cụm liên kết
5. Sinh lý do cảnh báo
6. Đưa các `order` liên quan ra để con người review

Nói cách khác:

- `pair` là nơi hệ thống ra quyết định
- `order` là nơi con người mở ra để kiểm tra

## Nguyên tắc cần nhớ

- Đây là bộ luật phát hiện dấu hiệu đáng nghi, không phải bộ luật kết luận fraud 100%.
- Một cặp có thể trùng nhiều bằng chứng cùng lúc.
- Score được dùng để sắp xếp thứ tự review, không thay thế xác minh nghiệp vụ.
- Pair evidence là trung tâm; network evidence là hỗ trợ.
- Nếu một order xuất hiện nhiều dòng trong report, điều đó có thể chỉ có nghĩa order đó trùng nhiều lý do.

## 4 nhóm fraud rule nghiệp vụ

Hệ thống hiện tại sinh ra nhiều `reason_code` kỹ thuật. Để dễ đọc, chúng được gom thành 4 nhóm rule nghiệp vụ.

### 1. Cặp lặp lại và phụ thuộc bất thường

Hệ thống đang nói gì:

- tài xế và khách hàng này đi với nhau qua nhiều lần
- và hai bên phụ thuộc vào nhau cao hơn hành vi thông thường

Nên hiểu như người vận hành:

- đây là dấu hiệu "hai bên cứ gặp lại nhau rất thường xuyên"
- nó cho thấy quan hệ này không giống đa số cặp thông thường

Bằng chứng kỹ thuật thường đi kèm:

- `KB-C_EXTREME_VOLUME`
- `KB-C_TIGHT_PAIR_SHARE`

Các chỉ số hay gặp:

- `n_trips`
- `pair_share_driver`
- `pair_share_customer`
- `concentration_score`
- `pair_core_score`

Không nên hiểu sai:

- rule này chưa khẳng định đây là đơn ảo
- nó mới cho thấy cặp này có cấu trúc giao dịch rất đáng nghi

### 2. Dấu hiệu đơn ảo hoặc quay đầu bất thường

Hệ thống đang nói gì:

- cặp này có nhiều chuyến giống hành vi tạo chuyến không tự nhiên
- hoặc tạo các chuyến sát nhau quá mức bình thường

Nên hiểu như người vận hành:

- đây là nhóm rule mạnh nhất về mặt nghiệp vụ
- vì nó gần hơn với hành vi "tạo chuyến để ăn khuyến mãi / tạo doanh số" thay vì đi chuyển thật

Bằng chứng kỹ thuật thường đi kèm:

- `KB-C_HIGH_GHOST_RATE`
- `KB-C_SUPERFAST_GAP`

Các chỉ số hay gặp:

- `ghost_rate`
- `n_ghost`
- `min_gap_min`
- `suspected_ghost_score`
- `high_confidence`

Không nên hiểu sai:

- `min_gap_min` nhỏ một mình chưa đủ để kết luận
- logic mới chỉ xem `SUPERFAST_GAP` hợp lệ khi gap không âm, đủ số trip, và có thêm hỗ trợ từ ghost signal

### 3. Mẫu farming theo tuyến

Hệ thống đang nói gì:

- cặp này lặp đi lặp lại một kiểu tuyến đường với tần suất rất cao
- mẫu lặp lại giống script hoặc farming hơn là đi chuyển tự nhiên

Bằng chứng kỹ thuật thường đi kèm:

- `KB-C_ROUTE_LOOP`

Các chỉ số hay gặp:

- `dominant_route_key`
- `dominant_route_trip_count`
- `dominant_route_share`

Không nên hiểu sai:

- có những trường hợp hợp lệ vẫn lặp lại cùng một tuyến
- vì vậy rule này nên đọc chung với repeated-pair evidence hoặc ghost evidence

### 4. Cụm liên kết đáng nghi nhiều cấp

Hệ thống đang nói gì:

- cặp đáng nghi này nằm trong một nhóm lớn hơn
- nhóm đó có nhiều cặp cùng chia sẻ đầu mối, ví dụ như route, điểm đón trả, promo, hoặc payment pattern

Bằng chứng kỹ thuật thường đi kèm:

- `KB-C_SUSPICIOUS_COMPONENT`

Các chỉ số hay gặp:

- `component_id`
- `component_size`
- `linked_pair_count`
- `supporting_signal_count`
- `network_support_score`

Không nên hiểu sai:

- đây là bằng chứng hỗ trợ để mở rộng điều tra
- nó không nên được đọc như bằng chứng duy nhất để kết luận fraud

## Mapping từ reason_code sang business rule

| reason_code | Cách gọi để đọc cho business |
| --- | --- |
| `KB-C_EXTREME_VOLUME` | `Cặp lặp lại và phụ thuộc bất thường` |
| `KB-C_TIGHT_PAIR_SHARE` | `Cặp lặp lại và phụ thuộc bất thường` |
| `KB-C_HIGH_GHOST_RATE` | `Dấu hiệu đơn ảo hoặc quay đầu bất thường` |
| `KB-C_SUPERFAST_GAP` | `Dấu hiệu đơn ảo hoặc quay đầu bất thường` |
| `KB-C_ROUTE_LOOP` | `Mẫu farming theo tuyến` |
| `KB-C_SUSPICIOUS_COMPONENT` | `Cụm liên kết đáng nghi nhiều cấp` |

## Luồng xử lý hiện tại trong project

Pipeline hiện tại trong [build_task3_daily_outputs.py](/D:/VSF/scripts/build_task3_daily_outputs.py) được nén lại thành luồng để đọc như sau:

1. Đọc dữ liệu order `ride`
2. Loại bỏ các order không nằm trong phạm vi cần phân tích
3. Gom theo pair `tài xế - khách hàng`
4. Tính các chỉ số repeated pair và concentration
5. Tính thêm ghost signal, temporal signal, và route reuse
6. Tìm network support nếu pair nằm trong cụm đáng nghi
7. Gán `reason_code`
8. Chấm điểm ưu tiên review
9. Đẩy các `order` liên quan ra file output và dashboard

Nơi sinh `reason_code`:

- [ride_kbc_rules.py](/D:/VSF/src/rules/ride_kbc_rules.py)

Nơi tính điểm và xếp ưu tiên:

- [ride_collusion_scoring.py](/D:/VSF/src/scoring/ride_collusion_scoring.py)

## Cách đọc kết quả cho đúng

Khi mở report hoặc dashboard, nên đọc theo thứ tự:

1. Pair này bị flag vì nhóm rule nào?
2. Pair evidence có mạnh không?
3. Có thêm ghost hoặc temporal support không?
4. Có network support không?
5. Sau cùng mới mở các order liên quan để xác minh

Nếu cần một cách diễn giải ngắn gọn cho non-tech:

- pair evidence trả lời: "cặp này có đang nghi không?"
- ghost/route evidence trả lời: "đang nghi theo kiểu nào?"
- network evidence trả lời: "chỉ là một cặp đơn lẻ hay nằm trong một nhóm lớn?"

## Thứ tự ưu tiên review đề xuất

Nếu cần một thứ tự review đơn giản cho vận hành:

1. `Dấu hiệu đơn ảo hoặc quay đầu bất thường`
2. `Cặp lặp lại và phụ thuộc bất thường`
3. `Mẫu farming theo tuyến`
4. `Cụm liên kết đáng nghi nhiều cấp`

Lý do:

- nhóm ghost-trip gần nhất với hành vi gian lận trực tiếp
- repeated locked pair là bằng chứng cấu trúc rất mạnh
- route farming hữu ích nhưng vẫn có trường hợp hợp lệ
- network pattern rất tốt để mở rộng điều tra, nhưng yếu hơn nếu dùng độc lập

## Điều cần đồng bộ trong mọi tài liệu và dashboard

- đơn vị phát hiện là `pair`, không phải từng `order`
- `flag rows` không được đọc nhầm thành `unique flagged orders`
- network là bằng chứng hỗ trợ, không thay thế pair evidence
- score dùng để xếp ưu tiên review, không phải kết luận fraud

## Kết luận

Bộ fraud rules hiện tại đã được viết lại để bám sát luồng mới của bài toán `ride`.

Thông điệp cần giữ đồng nhất ở mọi nơi là:

- hệ thống tìm cặp đáng nghi trước
- hệ thống giải thích lý do sau
- con người xác minh trên order cuối cùng
