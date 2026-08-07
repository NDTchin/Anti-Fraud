# Sprint 2 Scope: KB-C Driver-Customer Ghost-Trip Collusion

## Problem statement

Sprint 2 duoc reset scope de di dung mot pattern gian lan cu the:

- driver va customer thong dong tao ghost trips
- cung mot pair lap lai voi tan suat bat thuong
- hanh vi nghi ngo duoc nhin truoc het o cap `driver-customer pair`

Tai lieu nay theo sat huong:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

## Sprint 2 objective

Muc tieu cua Sprint 2 khong phai build mot fraud engine day du ngay lap tuc.

Muc tieu dung hon la xay duoc `graph core MVP` cho bai toan:

1. shortlist suspicious pairs
2. score muc do collusion cua pair
3. gom pair thanh suspicious components de review

## Graph abstraction can chot

Don vi graph trung tam:

- node `Driver`
- node `Customer`
- weighted edge giua `Driver` va `Customer`

Tren moi edge can co toi thieu:

- `trip_count`
- `driver_trip_count`
- `customer_trip_count`
- `pair_share_driver`
- `pair_share_customer`

Day la abstraction du de chay MVP ma khong phu thuoc vao nhieu feature phu.

## Algorithms trong scope Sprint 2

Sprint 2 chi nen chot 3 graph algorithms cot loi:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

## 1. Weighted edge outlier detection

Dung de:

- tim pair co `trip_count` nam o tail cua phan phoi

Day la first-pass detector va la nguon tao suspicious seeds.

## 2. Bipartite concentration scoring

Dung de:

- do xem pair co chiem mot ty trong bat thuong tren ca phia driver va customer hay khong

Day la lop refinement quan trong nhat de xac dinh collusion thay vi chi nhin volume thuan tuy.

## 3. WCC

Dung de:

- gom suspicious pairs thanh component tren suspicious graph

Suspicious graph duoc noi bang cac shared entities huu ich cho dieu tra, vi du:

- shared address
- shared payment
- shared promo
- shared driver
- shared customer

## Ngoai scope Sprint 2 core

Cac y tuong sau co the lam sau, nhung khong nen la blocker cua Sprint 2:

- temporal anomaly scoring
- ghost-rate scoring
- route-loop scoring
- Louvain
- k-core
- node similarity tong quat

Ly do:

- khong can de chot MVP graph core
- de tao scope qua rong
- de lam mo bai toan repeated pair collusion

## Deliverables nen co o cuoi Sprint 2

Sprint 2 nen ket thuc voi cac dau ra sau:

1. `pair table` theo time window
2. `volume_score` cho moi pair
3. `concentration_score` cho moi pair
4. `suspicious_pair_list`
5. `suspicious_graph`
6. `component_id` va `component_size`
7. `flagged_orders` de analyst review

## Proposed build order

Thu tu trien khai de tranh scope creep:

1. Build pair stats
2. Run weighted edge outlier detection
3. Run bipartite concentration scoring
4. Define suspicious pair criteria
5. Build suspicious graph
6. Run WCC
7. Materialize pair/component evidence xuong order level

## Role cua operational signals

`ghost_rate`, `min_gap_min`, va `route reuse` van phu hop voi bai toan ghost-trip, nhung trong Sprint 2 chung nen duoc xep la:

- enrichment signals
- tie-breaker signals
- explainability signals

Khong nen dung chung de dinh nghia graph scope chinh.

## Success criteria

Sprint 2 duoc xem la dat huong dung neu:

- pair-level detection tro thanh trung tam pipeline
- 3 graph algorithms cot loi da duoc dinh nghia ro
- suspicious components co the duoc xuat ra de mo case dieu tra
- cac signal ngoai core duoc dat dung vi tri la enrichment

## Final note

Neu can giam scope de dam bao tien do, thu tu uu tien tuyet doi trong Sprint 2 la:

1. `Weighted edge outlier detection`
2. `Bipartite concentration scoring`
3. `WCC`

Day la bo MVP dung nhat voi huong lam lai project hien tai.
