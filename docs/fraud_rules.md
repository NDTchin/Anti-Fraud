# Fraud Rules

## Muc dich tai lieu

Tai lieu nay giai thich bo fraud rules hien tai theo cach de:

- fraud operations doc duoc
- business user doc duoc
- product owner doc duoc
- data team doi chieu duoc voi code

Muc tieu cua tai lieu khong phai la mo ta tat ca chi tiet ky thuat, ma la tra loi 4 cau hoi:

1. He thong dang tim mau fraud nao?
2. Moi mau fraud duoc nhan dien bang nhung bang chung nao?
3. Ket qua dang duoc hien thi cho nguoi dung ra sao?
4. Nen doc nhung nhan canh bao nay nhu the nao de tranh hieu sai?

## Nguyen tac can nho

- Day la bo luat phat hien dau hieu dang nghi, khong phai bo luat ket luan fraud 100%.
- Mot case co the trung nhieu bang chung cung luc.
- Score duoc dung de sap xep uu tien review, khong thay the xac minh nghiep vu.
- Logic phat hien duoc xac lap o cap `driver-customer pair`, sau do moi materialize xuong cap `order`.

## 4 nhom fraud rule nghiep vu

He thong hien tai tao ra nhieu `reason_code` ky thuat, nhung de doc cho de hieu, nen gom thanh 4 nhom rule nghiep vu.

### Rule 1. Cap Lap Lai Va Phu Thuoc Bat Thuong

Y nghia:

- tai xe va khach hang di voi nhau nhieu lan mot cach bat thuong
- va muc do phu thuoc cua hai dau mut cao hon mat bang thong thuong

Bang chung ky thuat thuong di kem:

- `KB-C_EXTREME_VOLUME`
- `KB-C_TIGHT_PAIR_SHARE`

Chi so chinh:

- `n_trips`
- `volume_score`
- `pair_share_driver`
- `pair_share_customer`
- `concentration_score`
- `pair_core_score`

Khong nen hieu sai:

- rule nay khong co nghia da chung minh ghost trip
- no noi rang cau truc giao dich cua pair nay rat dang nghi

### Rule 2. Mau Thuc Thi Ghost Trip

Y nghia:

- cach pair nay tao chuyen xe giong hanh vi gia lap hon la van hanh that

Bang chung ky thuat thuong di kem:

- `KB-C_HIGH_GHOST_RATE`
- `KB-C_SUPERFAST_GAP`

Chi so chinh:

- `ghost_rate`
- `n_ghost`
- `min_gap_min`
- `temporal_score`
- `suspected_ghost_score`
- `high_confidence`

Khong nen hieu sai:

- rule nay manh, nhung van can doi chieu du lieu goc neu case quan trong
- `min_gap_min` don le khong du de ket luan

### Rule 3. Mau Farming Theo Tuyen

Y nghia:

- pair lap di lap lai mot route theo cach giong script hoac farming hon la nhu cau di chuyen tu nhien

Bang chung ky thuat thuong di kem:

- `KB-C_ROUTE_LOOP`

Chi so chinh:

- `dominant_route_key`
- `dominant_route_trip_count`
- `dominant_route_share`

Khong nen hieu sai:

- co nhung truong hop hop le van lap lai route
- vi vay rule nay nen doc cung ghost evidence hoac repeated-pair evidence

### Rule 4. Mau Lien Ket Theo Mang

Y nghia:

- pair dang nghi nay khong dung mot minh ma nam trong mot nhom co lien he voi cac pair dang nghi khac

Bang chung ky thuat thuong di kem:

- `KB-C_SUSPICIOUS_COMPONENT`

Chi so chinh:

- `component_id`
- `component_size`
- `linked_pair_count`
- `supporting_signal_count`
- `network_support_score`

Khong nen hieu sai:

- day la rule support rat tot, nhung khong nen xem la bang chung duy nhat
- no hieu qua nhat khi di cung bang chung pair-level manh va ghost evidence

## Mapping tu reason_code sang business rule

| reason_code | Business rule |
| --- | --- |
| `KB-C_EXTREME_VOLUME` | `Cap Lap Lai Va Phu Thuoc Bat Thuong` |
| `KB-C_TIGHT_PAIR_SHARE` | `Cap Lap Lai Va Phu Thuoc Bat Thuong` |
| `KB-C_HIGH_GHOST_RATE` | `Mau Thuc Thi Ghost Trip` |
| `KB-C_SUPERFAST_GAP` | `Mau Thuc Thi Ghost Trip` |
| `KB-C_ROUTE_LOOP` | `Mau Farming Theo Tuyen` |
| `KB-C_SUSPICIOUS_COMPONENT` | `Mau Lien Ket Theo Mang` |

## Luong xu ly hien tai trong project

Pipeline hien tai trong [build_task3_daily_outputs.py](/D:/VSF/scripts/build_task3_daily_outputs.py) di theo thu tu:

1. Doc du lieu chuyen xe
2. Lam sach du lieu
3. Gom theo pair `driver - customer`
4. Tinh pair features va pair scores
5. Tinh them ghost va temporal features
6. Tinh network support va `WCC`
7. Sinh `reason_code`
8. Gan `priority_score`
9. Gan `risk_tier`
10. Materialize ket qua ra report va dashboard

Noi sinh `reason_code`:

- [ride_kbc_rules.py](/D:/VSF/src/rules/ride_kbc_rules.py)

Noi tinh score va uu tien:

- [ride_collusion_scoring.py](/D:/VSF/src/scoring/ride_collusion_scoring.py)


## Thu tu uu tien review de xuat

Neu can mot thu tu review don gian:

1. `Mau Thuc Thi Ghost Trip`
2. `Cap Lap Lai Va Phu Thuoc Bat Thuong`
3. `Mau Farming Theo Tuyen`
4. `Mau Lien Ket Theo Mang`

Ly do:

- ghost-like execution gan nhat voi hanh vi fraud truc tiep
- repeated locked pair la bang chung cau truc rat manh
- route farming huu ich nhung van co kha nang hop le
- network pattern rat tot de mo rong dieu tra, nhung yeu hon neu dung doc lap

## Ket luan

Bo fraud rules hien tai van dung 4 nhom nghiep vu nhu truoc, nhung implementation da duoc siet lai ro rang hon.

Thong diep quan trong nhat can dong bo trong cac bao cao:

- pair evidence la trung tam
- network evidence la ho tro
- temporal evidence phai hop le va khong duoc bi noise
- `flag rows` khong duoc doc nham thanh `unique orders`
