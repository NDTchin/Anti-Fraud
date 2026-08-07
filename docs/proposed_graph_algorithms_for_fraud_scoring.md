# Graph Algorithms Dang Duoc Chon Cho Huong Di Moi Cua Project

## Pham vi tai lieu

Tai lieu nay mo ta bo graph algorithms nen duoc xem la huong chinh moi cua project cho bai toan:

- `Driver-Customer Ghost-Trip Collusion`

Nguon dinh huong goc:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Tai lieu nay khong co muc tieu mo ta "code dang chay hien tai" theo nghia implementation lich su. Thay vao do, no chot bo thuat toan can duoc uu tien khi lam lai project.

Ngay cap nhat: `2026-08-05`

## Ket luan nhanh

Project nen tap trung vao 3 graph algorithms cot loi:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Ba thanh phan nay tuong ung voi 3 cau hoi chinh:

1. Pair nao lap lai bat thuong?
2. Pair nao that su co tinh collusion cao?
3. Cac pair nghi ngo co ket noi thanh network de mo case dieu tra hay khong?

## 1. Don vi phan tich trung tam

Don vi phan tich chinh khong phai tung order rieng le, ma la pair:

- `driver_id`
- `customer_id`

Moi pair duoc xem la mot canh co trong so trong do thi hai phia:

- ben trai: `Driver`
- ben phai: `Customer`
- trong so canh: `trip_count`

Day la abstraction dung nhat cho bai toan ghost-trip collusion vi hanh vi gian lan thuong tap trung vao quan he lap lai giua hai dau mut.

## 2. Bo 3 thuat toan cot loi

## 2.1. Weighted edge outlier detection

Muc tieu:

- tim cac pair co `trip_count` nam o phan duoi cua phan phoi toan bo pairs trong cung time window

Vai tro:

- first-pass detector
- tao seed suspicious pairs
- de giai thich va de scale

Day la lop phat hien dau tien, nhung khong nen dung mot minh de ket luan collusion.

## 2.2. Bipartite concentration scoring

Muc tieu:

- do xem mot pair co chiem ti trong bat thuong tren ca hai dau mut hay khong

Feature cot loi:

- `pair_share_driver = pair_trip_count / total_driver_trip_count`
- `pair_share_customer = pair_trip_count / total_customer_trip_count`

Vai tro:

- refinement layer cho suspicious pairs
- giam false positive tu volume tuyet doi
- bat dung ban chat "khoa cung" giua driver va customer

## 2.3. WCC

Muc tieu:

- gom cac pair nghi ngo thanh `component` de phuc vu dieu tra

WCC duoc chay tren suspicious graph, noi cac suspicious pairs qua shared entities nhu:

- shared driver
- shared customer
- shared address
- shared payment
- shared promo

Vai tro:

- chuyen tu pair detection sang network investigation
- tao `component_id`, `component_size`, danh sach member, va do uu tien mo case

## 3. Pipeline nen duoc xem la chuan

Pipeline graph-first duoc uu tien trong huong moi:

1. Build pair table theo time window
2. Tinh `trip_count`, `driver_trip_count`, `customer_trip_count`
3. Tinh `pair_share_driver`, `pair_share_customer`
4. Chay `weighted edge outlier detection`
5. Chay `bipartite concentration scoring`
6. Tao suspicious pair list
7. Build suspicious graph tu shared entities
8. Chay `WCC`
9. Rank pair va rank component de analyst review

## 4. Cac signal nen duoc xem la enrichment, khong phai graph core

Cac signal sau van huu ich, nhung trong huong moi chung khong phai bo 3 graph algorithms cot loi:

- `ghost_rate` tu `avg_kmh = 0`
- `min_gap_min` hoac superfast repeat gap
- `dominant_route_share`
- route reuse templates
- script similarity

Nen xem chung la:

- `operational fraud signals`
- `business enrichment`
- `precision boosters`

Khong nen de cac signal nay chi phoi kien truc graph core cua project.

## 5. Nhung gi khong con la uu tien giai doan dau

O giai doan MVP va huong lam lai project, khong nen dat cac thuat toan sau lam trung tam:

- `Louvain`
- `k-core`
- `node similarity` tong quat
- ring scoring phuc tap

Ly do:

- kho explain hon
- can graph phong phu hon moi phat huy tac dung
- khong sat bai toan repeated pair bang bo 3 cot loi

## 6. Cach dinh vi tai lieu nay so voi implementation

Tai lieu nay la `target architecture note`, khong phai bao cao "as-is".

Neu implementation hien tai co them:

- ghost rules
- fast-gap rules
- route-loop rules
- blended risk score

thi nen hieu do la phan di san hoac enrichment. Huong moi can duoc mo ta va danh gia theo logic:

- core graph pipeline truoc
- enrichment sau

## 7. Final recommendation

Neu can chot bo graph algorithms de build lai project theo huong gon, dung trong tam, de ban giao va de explain, thi bo can chot la:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Day la bo khung graph chinh. Moi signal khac nen duoc gan vao nhu lop ho tro sau khi bo khung nay on dinh.
