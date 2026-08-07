# Scoring Va Flagging Theo Huong Moi Cua Project

## Pham vi tai lieu

Tai lieu nay mo ta cach nen to chuc scoring va flagging khi project duoc lam lai theo huong:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Muc tieu la tach ro:

- `graph core`
- `optional enrichment`
- `flagging output`

Tai lieu nay khong dong nhat voi implementation lich su. No la dinh huong scoring/flagging can phu hop voi kien truc moi.

Ngay cap nhat: `2026-08-05`

## Ket luan nhanh

Scoring nen duoc to chuc thanh 3 lop:

1. `pair core score`
2. `network support score`
3. `investigation priority`

Trong do:

- `pair core score` den tu `weighted edge outlier detection` va `bipartite concentration scoring`
- `network support score` den tu suspicious graph va `WCC`
- `investigation priority` la diem cuoi de xep thu tu review

Flagging van nen materialize xuong cap `order`, nhung logic phat hien va cham diem phai duoc xac lap o cap `driver-customer pair`.

## 1. Don vi scoring chinh

Don vi scoring trung tam la pair:

- `driver_id`
- `customer_id`

Ly do:

- collusion trong bai toan nay xuat hien tren quan he lap lai giua hai dau mut
- scoring o cap order rat de bi nhieu va kho nhin ra pattern lap
- pair scoring cho phep gan network context de mo case dieu tra

## 2. Graph core scoring

## 2.1. Pair core score

`pair_core_score` nen duoc xay tu 2 thanh phan bat buoc:

- `volume_score`
- `concentration_score`

Y nghia:

- `volume_score` tra loi pair co lap lai bat thuong hay khong
- `concentration_score` tra loi pair co dang "dinh" vao nhau bat thuong hay khong

Tai lieu huong moi khuyen nghi uu tien 2 diem nay truoc moi signal khac.

## 2.2. Suspicious pair rule

Mot pair nen duoc dua vao suspicious list neu:

- `volume_score` cao
- hoac `concentration_score` cao
- hoac ca hai

Neu can mot ban MVP de trien khai nhanh, co the dung rule don gian:

- `trip_count` nam o tail cua phan phoi
- va `pair_share_driver` hoac `pair_share_customer` vuot nguong

## 2.3. Network support score

Sau khi co suspicious pair list, build suspicious graph va chay `WCC`.

Tu do sinh cac metric ho tro:

- `component_id`
- `component_size`
- `linked_pair_count`
- so loai shared entities ho tro

Nhung metric nay nen duoc tong hop thanh:

- `network_support_score`

Day khong phai first-pass detector. No la lop bo sung de biet:

- pair do dung mot minh
- hay nam trong cum co ha tang dung chung

## 3. Diem cuoi cung nen duoc dinh nghia the nao

Thay vi tron qua nhieu logic ngay tu dau, nen tach ro:

- `pair_core_score`
- `network_support_score`
- `priority_score`

Trong do:

- `pair_core_score` la diem chinh de quyet dinh pair co dang review hay khong
- `network_support_score` la diem nang uu tien dieu tra
- `priority_score` la diem sap hang cuoi cung cho analyst

Nguyen tac:

- khong de network support thay the pair evidence
- khong de enrichment lam mo 2 signal cot loi
- pair co evidence manh phai van noi bat ke ca khi component nho

## 4. Cac signal enrichment nen dat dung vi tri

Trong huong moi, cac signal sau van nen duoc giu, nhung dung o vai tro enrichment:

- `ghost_rate`
- `min_gap_min`
- `dominant_route_share`
- route template reuse

Nen dung chung de:

- tang precision
- tang explainability cho analyst
- uu tien review trong cung mot component

Khong nen de chung tro thanh trung tam kien truc scoring.

## 5. Risk tier va flagging

`risk_tier` nen phan anh muc do uu tien review, khong phai ket luan fraud.

Goi y phan lop:

- `HIGH`: pair core score cao va co them network support hoac enrichment manh
- `MEDIUM`: pair core score ro rang nhung network support vua phai
- `WATCHLIST`: pair duoc shortlist nhung can them bang chung

Co the giu dau ra cap order vi analyst thuong review tren order timeline, nhung can hieu:

- phat hien o cap pair
- clustering o cap network
- materialization o cap order

## 6. Output nen duoc duy tri

Mot pipeline scoring/flagging theo huong moi nen xuat toi thieu:

- `pair_summary`
- `pair_reasons`
- `suspicious_components`
- `flagged_orders`

Trong do:

- `pair_summary` la bang trung tam de cham diem va rank
- `pair_reasons` giai thich tai sao pair bi shortlist
- `suspicious_components` phuc vu mo case cluster
- `flagged_orders` phuc vu review van hanh

## 7. Cach doc score cho dung

Nen dien giai nhu sau:

- `pair_core_score`: muc do bat thuong cua chinh pair
- `network_support_score`: muc do duoc cung co boi network xung quanh
- `priority_score`: muc do nen review truoc

Day la ngon ngu scoring phu hop hon voi huong graph-first moi so voi viec tron nhieu score lich su vao mot nhan chung.

## 8. Final recommendation

Neu update pipeline scoring/flagging theo huong moi, thu tu uu tien nen la:

1. chot pair table
2. chot `volume_score`
3. chot `concentration_score`
4. chot suspicious pair rule
5. build suspicious graph
6. chot `WCC`
7. moi them enrichment va risk tier

Lam nhu vay se giu scoring gon, de explain, va dung trong tam cua bai toan `Driver-Customer Ghost-Trip Collusion`.
