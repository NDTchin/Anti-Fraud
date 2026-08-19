# Note Ve Property Va Relationship Cho Demo Visualize `ride`

## Pham vi tai lieu

Tai lieu nay khong con mo ta order graph day du cho ca `ride` va `food`.

Muc tieu moi la phuc vu flow demo:

1. demo dashboard truoc
2. sau do mo Neo4j de visualize nhanh cac case can giai thich

Vi vay, tai lieu nay chi tap trung vao schema toi thieu can deploy cho phan visualize, uu tien:

- `order_id`
- `driver_id`
- `customer_id`
- tong so don
- so don bi flag
- tai xe bi gan flag
- khach hang bi gan flag

## Ket luan nhanh

Cho flow demo hien tai, Neo4j khong nen giu full graph nhu moi truong local.

Schema nen duoc rut gon thanh:

1. `Driver`
2. `Customer`
3. `Order`
4. `(:Driver)-[:SERVED]->(:Order)`
5. `(:Customer)-[:PLACED]->(:Order)`

Tat ca cac node phu va relationship phu chi nen giu lai neu buoi demo thuc su can dao sau vao shared infrastructure.

## 1. Muc tieu cua graph demo

Graph demo tren Neo4j duoc dung de tra loi nhanh cac cau hoi:

- Don nay thuoc ve tai xe nao va khach hang nao?
- Tai xe nay co bao nhieu don trong tap demo?
- Khach hang nay co bao nhieu don trong tap demo?
- Don nao bi flag?
- Bao nhieu tai xe co lien quan toi don bi flag?
- Bao nhieu khach hang co lien quan toi don bi flag?

Do do, graph demo uu tien su ro rang, nhe, va de explain trong luc present hon la day du schema.

## 2. Graph core can giu

Day la lop schema bat buoc phai co khi deploy demo:

- node `Order`
- node `Driver`
- node `Customer`
- `(:Driver)-[:SERVED]->(:Order)`
- `(:Customer)-[:PLACED]->(:Order)`

Day la phan du lieu toi thieu de:

- mo graph theo `order_id`
- mo graph theo `driver_id`
- mo graph theo `customer_id`
- tinh metric tong quan cho tap demo

Neu thieu lop nay, graph demo se khong phuc vu dung cau chuyen can trinh bay.

## 3. Property nen giu tren tung node

### `Order`

Nen giu:

- `order_id`
- `order_date`
- `is_flagged`
- `priority_score`
- `risk_tier`

Y nghia:

- `order_id`: de drill-down theo don
- `order_date`: de giai thich boi canh thoi gian
- `is_flagged`: de to mau va filter nhanh
- `priority_score`: de sap thu tu uu tien
- `risk_tier`: de giai thich muc do can review

### `Driver`

Nen giu:

- `driver_id`
- `is_flagged`
- `flagged_order_count`

Y nghia:

- `driver_id`: de tra cuu va visualize
- `is_flagged`: de to mau node tai xe
- `flagged_order_count`: de show tai xe nay co bao nhieu don bi flag

### `Customer`

Nen giu:

- `customer_id`
- `is_flagged`
- `flagged_order_count`

Y nghia tuong tu `Driver`.

## 4. Metric nao nen tinh truc tiep tu graph

Cho buoi demo, khong can tao schema phuc tap cho metric.

Co the tinh truc tiep bang Cypher:

- tong so don
- so don bi flag
- so tai xe bi gan flag
- so khach hang bi gan flag

Noi cach khac:

- metric tong quan nen la query
- graph nen la data model de visualize

Khong can tao them node tong hop neu chua co nhu cau snapshot theo ngay.

## 5. Nhung thanh phan khong can dua len ban deploy demo

De toi uu chi phi va kich thuoc DB deploy, khong nen mang len ban demo cac nhom sau:

- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`
- `RideService`
- `CancelActor`
- `CancelReason`
- `ServiceType`
- `SubVertical`
- `TravelMode`
- `ChannelType`

Cung khong can uu tien:

- `Merchant`
- `DropoffFailActor`
- `DropoffFailCode`
- cac label chi con ton tai o schema cu nhung khong phuc vu story demo

Ly do:

- chung lam graph nang hon
- query cham hon
- visual trong Neo4j Browser de roi
- khong phuc vu truc tiep cho cau chuyen `order-driver-customer-flagged`

## 6. Nguon data nen dua vao DB demo

DB demo khong nen duoc build tu full `neo4j-store`.

Nen tao mot tap demo moi tu:

- source order goc da clean
- danh sach `order_id` bi flag trong `reports/task3/flagged_orders.parquet`

Sau khi join, tap import demo nen co cac cot:

- `order_id`
- `driver_id`
- `customer_id`
- `order_date`
- `is_flagged`
- `priority_score`
- `risk_tier`

Day la du lieu du de:

- tinh tong so don trong tap demo
- tinh so don bi flag
- tinh so tai xe bi gan flag
- tinh so khach hang bi gan flag
- mo graph theo order, driver, customer

## 7. Cach cat du lieu cho ban deploy demo

Khong nen deploy toan bo universe du lieu.

Nen cat theo mot trong hai cach:

1. chi lay cac order bi flag
2. lay cac order bi flag va toan bo order lien quan toi driver/customer bi flag

Cach `2` thuong hop ly hon cho demo vi:

- graph nhin tu nhien hon
- van nho hon full DB rat nhieu
- de explain tai sao mot driver/customer bi gan flag

Neu can tiep tuc cat nho hon nua, co the gioi han:

- top `N` order theo `priority_score`
- top `N` driver bi flag
- top `N` customer bi flag

## 8. Dinh huong deploy phase 2

Phase 2 khong nham muc tieu thay the he thong graph day du o local.

Muc tieu dung hon la:

- tao mot `Neo4j demo graph`
- nhe
- de import
- de query
- de visualize trong Browser hoac Aura

Do do:

- local full graph van co gia tri cho nghien cuu sau nay
- ban deploy chi nen giu subgraph phuc vu demo

## 9. Final note

Trong boi canh hien tai, can phan biet ro hai vai tro:

- `dashboard`: noi trinh bay tong quan va shortlist
- `Neo4j demo graph`: noi mo rong va visualize case

Schema duoc uu tien cho ban deploy demo vi the khong can day du nhu local store.

Thu tu uu tien dung la:

1. `Order`, `Driver`, `Customer`
2. `PLACED`, `SERVED`
3. `is_flagged`, `flagged_order_count`, `priority_score`, `risk_tier`
4. cac metric query cho tong quan

Neu mot property hay relationship khong giup ke cau chuyen demo ro hon, thi khong nen dua vao ban deploy phase 2.
