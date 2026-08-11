# Scoring Va Flagging 

## Pham vi tai lieu

Tai lieu nay mo ta cach nen to chuc scoring va flagging khi project duoc lam lai theo huong:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Muc tieu la tach ro:

- `graph core`
- `optional enrichment`
- `flagging output`

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

## Cap nhat implementation 2026-08-11

Pipeline hien tai da duoc siet lai theo huong giam false positive va giam noise:

- da sua bug tinh `min_gap_min` de luon `sort` dung truoc khi tinh `diff()`
- khong con chap nhan `min_gap_min` am lam bang chung `SUPERFAST_GAP`
- suspicious pair shortlist mac dinh da chat hon
- network support tiep tuc la bang chung ho tro, khong duoc thay the pair evidence

Tac dong da do tren ngay `2026-07-24`:

- truoc update: `3,019` `unique orders` bi flag
- sau update: `482` `unique orders` bi flag
- giam `2,537` orders, tuong duong khoang `84.0%`

Luu y quan trong:

- `8,427` la `flag rows`, khong phai `unique orders`
- mot order co the trung nhieu `reason_code`, vi vay can tach ro `flag rows` va `flagged_orders`

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

- du `min_pair_trips`
- va co bang chung repeated-pair manh hoac ghost signal manh

Mac dinh implementation hien tai uu tien:

- `n_trips >= 4`
- va mot trong hai nhom sau:
  - repeated-pair manh:
    - `is_extreme_volume = True`
    - va `pair_share_driver >= 0.4` hoac `pair_share_customer >= 0.6`
    - va `concentration_score >= 0.85` hoac `pair_core_score >= 50`
  - ghost signal manh:
    - `ghost_rate >= 0.5`

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

Operational note:

- `ghost_rate` van la enrichment quan trong, nhung o implementation hien tai no cung co the dua pair vao shortlist khi du manh
- dieu nay duoc chap nhan vi bai toan dang la `ghost-trip collusion`, nhung pair evidence van phai duoc uu tien trong explainability

## 5. Risk tier va flagging

`risk_tier` nen phan anh muc do uu tien review, khong phai ket luan fraud.

Goi y phan lop:

- `HIGH`: pair core score cao va co them network support hoac enrichment manh
- `MEDIUM`: pair core score ro rang nhung network support vua phai
- `WATCHLIST`: pair duoc shortlist nhung can them bang chung

Trong implementation hien tai, `risk_tier` order-level dang duoc materialize thanh:

- `IMMEDIATE_REVIEW`
- `HIGH_RISK`
- `MONITOR`
- `LOW_PRIORITY`

Trong do:

- `high_confidence` khong con duoc bat chi vi mot `gap` nho don le
- `SUPERFAST_GAP` chi hop le khi gap khong am, du so trip, va co ghost support toi thieu

Co the giu dau ra cap order vi analyst thuong review tren order timeline, nhung can hieu:

- phat hien o cap pair
- clustering o cap network
- materialization o cap order

## 6. Output nen duoc duy tri

Ve mat concept, mot pipeline scoring/flagging theo huong moi nen co toi thieu:

- `pair_summary`
- `pair_reasons`
- `flagged_orders`

Trong do:

- `pair_summary` la bang trung tam de cham diem va rank
- `pair_reasons` giai thich tai sao pair bi shortlist
- `flagged_orders` phuc vu review van hanh

Trong implementation dashboard hien tai, chi 3 file core duoc materialize va doc truc tiep:

- `flagged_orders.parquet`
- `kbc_pair_summary.csv`
- `kbc_pair_reasons.csv`

Thong tin `component` van duoc giu trong cac file core va duoc dashboard suy ra tu do, nen khong can materialize them mot file report rieng chi de phuc vu dashboard.

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
