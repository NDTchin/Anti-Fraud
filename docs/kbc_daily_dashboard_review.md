# Review Dashboard `kbc_daily_dashboard.py`

Tai lieu nay danh gia dashboard trong [kbc_daily_dashboard.py](/D:/VSF/src/dashboard/kbc_daily_dashboard.py) duoi 3 goc nhin:

- nguoi dung cuoi
- data analyst
- goc nhin anti-fraud / security

Muc tieu:

- chi ra diem tot dang co
- chi ra diem chua tot hoac co rui ro
- cap nhat dashboard review theo logic fraud moi nhat trong repo

## Pham vi danh gia

Dashboard hien tai doc chu yeu tu:

- [flagged_orders.parquet](/D:/VSF/reports/task3/flagged_orders.parquet)
- [kbc_pair_summary.csv](/D:/VSF/reports/task3/kbc_pair_summary.csv)
- [kbc_pair_reasons.csv](/D:/VSF/reports/task3/kbc_pair_reasons.csv)

Can doc dashboard voi 2 luu y:

- day la tap da bi flag, khong phai toan bo order universe
- mot order co the xuat hien nhieu dong neu trung nhieu `reason_code`

## Tom tat dieu hanh

Dashboard hien tai co nen tang tot de theo doi fraud hang ngay:

- co cau truc ro
- co KPI tong quan
- co chart va bang detail
- co the drill xuong order-level

Tuy vay, de dong bo voi phuong thuc moi nhat, dashboard va cac bao cao dashboard can sua 5 nhom van de:

1. Tach ro `flag rows` va `unique flagged orders`
2. Cap nhat language de phan anh logic moi da duoc siet
3. Giam kha nang nguoi xem hieu nham metric tong
4. Dung `component` va `network` dung vai tro ho tro
5. Han che lo logic fraud nhay cam cho role khong phu hop

## Goc nhin 1: Nguoi dung cuoi

### Diem tot

- Dashboard co bo cuc de theo doi nhanh tinh hinh trong ngay
- Co the tu KPI xuong detail orders
- Cac truong business rule, risk tier, service va province huu ich cho van hanh

### Diem chua tot

- KPI tong don rat de bi hieu nham thanh tong don cua he thong
- Neu khong tach `flag rows` va `unique orders`, nguoi doc se bi sai ngay tu con so dau tien
- Neu van dung ngon ngu cu, dashboard de gay cam giac he thong dang flag qua rong du logic moi da siet lai

### Khuyen nghi

- Doi ten KPI thanh:
  - `Flag Rows`
  - `Unique Flagged Orders`
- Them ghi chu ngan:
  - `Mot order co the co nhieu reason_code`
- Neu co the, hien them delta truoc/sau cho ngay `2026-07-24` de minh hoa tac dong cua viec siet logic

## Goc nhin 2: Data Analyst

### Diem tot

- Da co du lieu o 3 cap:
  - order
  - pair
  - pair reason
- Da co bo score tuong doi day du:
  - `pair_core_score`
  - `network_support_score`
  - `priority_score`
- Da co san du lieu `component`

### Diem chua tot

- Dashboard review cu co nguy co doc nham `flag rows` thanh `unique orders`
- Neu analyst nhin `SUPERFAST_GAP` theo logic cu, se danh gia sai do manh cua temporal evidence
- Chua nhan manh ro rang rang network support la bang chung ho tro, khong phai first-pass detector

### Khuyen nghi

- O phan notes hoac data dictionary, ghi ro:
  - `pair` la don vi phat hien
  - `order` la cap materialization
  - `component` la cap mo rong dieu tra
- Neu hien top reasons, nen ghi kem dinh nghia operational moi:
  - `SUPERFAST_GAP` chi hop le khi gap khong am, du so trip, va co ghost support toi thieu
- Neu hien `high_confidence`, nen ghi ro rang label nay da duoc siet lai

## Goc nhin 3: Anti-fraud / Security

### Dashboard dang lo gi

Neu khong phan quyen, dashboard van de lo:

- `reason_code`
- `priority_score`
- `ghost_rate`
- `component_id`
- `linked_pair_count`
- `supporting_signal_count`

### Rủi ro nghiep vu

- Nguoi xau co the hoc nguoc he thong dang nhay vao dau
- Ho co the suy ra threshold va pattern can tranh
- Viec lo qua nhieu chi tiet temporal / network co the lam giam hieu qua anti-fraud

### Khuyen nghi

- Tach role view:
  - executive view
  - analyst view
  - investigator view
- Mac dinh chi show business-rule level cho role thong thuong
- An hoac mask `reason_code`, `priority_score`, `component_id` neu role khong du quyen

## Component-level review

Pipeline hien tai da su dung `WCC`, nen dashboard nen tan dung du lieu nay tot hon.

Nen co toi thieu:

- KPI `Largest WCC Component`
- bang top components theo:
  - `component_size`
  - `component_edge_count`
  - `avg/max priority_score`
  - `avg/max network_support_score`
- chi tiet component:
  - so driver
  - so customer
  - so pair
  - so order
  - top rule
  - top service

Thong diep can giu dong nhat voi logic moi:

- component giup mo rong dieu tra
- component khong duoc doc nhu bang chung ket luan fraud doc lap

## P0 can update trong docs va dashboard notes

- Tach ro `flag rows` va `unique flagged orders`
- Them ghi chu rang mot order co the match nhieu `reason_code`
- Cap nhat mo ta `SUPERFAST_GAP` theo logic moi
- Cap nhat mo ta `high_confidence` theo logic moi
- Cap nhat phan giai thich rang pair evidence la trung tam, network evidence la ho tro

## P1 nen lam tiep

- Them insight card `Highest-Risk Component`
- Them breakdown theo `business_rule_label` va `risk_tier`
- Them data notes ve pham vi du lieu va y nghia tung metric
- Them benchmark truoc/sau khi siet logic cho cac ngay spike lon

## Ket luan

Dashboard hien tai van la nen tang tot, nhung cach doc dashboard phai duoc cap nhat theo implementation moi nhat.

