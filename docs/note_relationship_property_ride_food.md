# Note Ve Property Va Relationship Cho Du Lieu `ride` / `food`

## Pham vi tai lieu

Tai lieu nay giai thich vai tro cua `property` va `relationship` trong order graph hien co, nhung duoc viet lai de phu hop voi huong moi cua project:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Muc tieu la lam ro:

- du lieu nao la `graph core input`
- du lieu nao la `shared-entity support`
- du lieu nao la `optional enrichment`

Tai lieu nay khong co muc tieu de thiet ke schema hoan toan moi. No giup doc schema hien co theo dung uu tien nghiep vu moi.

## Ket luan nhanh

Trong huong moi, schema order graph nen duoc hieu theo 3 lop:

1. `pair graph inputs`
2. `suspicious graph inputs`
3. `enrichment attributes`

Noi cach khac:

- khong phai moi property/relationship deu co vai tro ngang nhau
- uu tien cao nhat la cac thanh phan giup aggregate thanh pair `driver-customer`
- uu tien ke tiep la cac thanh phan giup noi suspicious pairs de chay `WCC`

## 1. Pair graph inputs

Day la nhung thanh phan quan trong nhat neu project di theo 3 graph algorithms cot loi.

Can co:

- node `Order`
- node `Driver`
- node `Customer`
- `(:Customer)-[:PLACED]->(:Order)`
- `(:Driver)-[:SERVED]->(:Order)`

Tu nhung lien ket nay downstream moi co the tong hop thanh:

- `trip_count`
- `driver_trip_count`
- `customer_trip_count`
- `pair_share_driver`
- `pair_share_customer`

Neu thieu lop nay, khong the build dung `weighted edge outlier detection` va `bipartite concentration scoring`.

## 2. Suspicious graph inputs

Day la lop du lieu dung de noi suspicious pairs thanh network phuc vu `WCC`.

Quan trong nhat:

- `Address`
- `PaymentMethod`
- `PromotionCode`
- `PromotionCampaign`

Quan he lien quan:

- `PICKUP_AT`
- `DROPOFF_AT`
- `PAID_BY`
- `USED_PROMO`
- `IN_CAMPAIGN`

Vai tro:

- noi pair qua shared address
- noi pair qua shared payment
- noi pair qua shared promo

Day la phan schema phuc vu truc tiep cho suspicious graph, khac voi pair graph core nhung van la mandatory support cho giai doan cluster investigation.

## 3. Enrichment attributes

Nhom nay van huu ich, nhung khong phai trung tam cua huong moi.

Vi du:

- `avg_kmh`
- `declared_km`
- `actual_km`
- `km_diff`
- `intrip_time_second`
- `lead_time_second`
- `gmv`
- `discount`
- `service_name`
- `service_type`
- `sub_vertical_name`
- `travel_mode`
- `channel_type`

Chung co the duoc dung de:

- tao business filters
- giai thich case
- tinh enrichment signals sau nay

Nhung khong nen lam mo 2 lop uu tien cao hon.

## 4. Cach hieu dung mo hinh lai property + relationship

Schema hien co co nhieu nhom du lieu vua ton tai duoi dang `property` tren `Order`, vua ton tai duoi dang node/relationship chuan hoa.

Dieu nay van hop ly trong huong moi vi:

- property giup filter nhanh va lam feature table
- relationship giup graph traversal va shared-entity linking

Do do, khong can ep buoc schema ve mot cuc:

- "chi property"
- hoac "chi relationship"

Can danh gia moi truong theo cau hoi:

- co phuc vu pair graph khong?
- co phuc vu suspicious graph khong?
- hay chi la enrichment?

## 5. Cac thanh phan quan trong nhat doi voi huong `Driver-Customer Ghost-Trip Collusion`

Neu phai uu tien schema theo tac dong toi huong moi, thu tu nen la:

1. `Driver`, `Customer`, `Order`
2. `PLACED`, `SERVED`
3. `Address`, `PaymentMethod`, `PromotionCode`
4. `PICKUP_AT`, `DROPOFF_AT`, `PAID_BY`, `USED_PROMO`
5. metric va taxonomy enrichment

Day la cach nhin schema phu hop nhat voi pipeline:

1. build pair table
2. score suspicious pairs
3. build suspicious graph
4. run `WCC`

## 6. Food va ride nen duoc doc the nao trong boi canh nay

`ride` la domain uu tien cho huong moi, vi bai toan hien tai la `Driver-Customer Ghost-Trip Collusion`.

Do do:

- cac lien ket giua `Driver`, `Customer`, `Order` la trong tam
- shared entities phuc vu repeated pair investigation la trong tam

`food` van co gia tri o muc schema dung chung, nhung khong nen chi phoi cach mo ta uu tien modeling cho bai toan nay.

## 7. Final note

Khi doc schema hien co de phuc vu huong moi, nen nho:

- `Order` graph la tang luu tru va truy vet
- `pair graph` moi la tang phan tich cot loi
- `suspicious graph` la tang dieu tra network

Vi vay, doc/schema note nay nen duoc hieu nhu mot tai lieu canh chinh uu tien du lieu cho bai toan pair-collusion, khong phai mot ban inventory trung lap moi field trong importer.
