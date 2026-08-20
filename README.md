# Graph Fraud Detection

Project nay hien duoc thu hep scope de tap trung vao bai toan `ride`:

- tim cap `tai xe - khach hang` lap lai bat thuong
- uu tien cac dau hieu lien quan den `ghost-trip collusion`
- dua ket qua ra dashboard de doi van hanh review

Tai lieu goc mo ta huong phan tich:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

## Doc nhanh trong 2 phut

Neu chi can hieu he thong dang lam gi, co the doc nhu sau:

1. He thong doc du lieu chuyen xe `ride`
2. He thong nhom du lieu theo cap `tai xe - khach hang`
3. He thong tim xem cap nao lap lai qua nhieu, phu thuoc vao nhau qua muc, hoac co dau hieu chuyen xe khong tu nhien
4. He thong xem cap dang nghi do co nam trong mot cum lien ket rong hon hay khong
5. He thong xep hang uu tien de nguoi review biet nen xem case nao truoc
6. Ket qua cuoi cung van duoc hien thi xuong cap `order` de de doi chieu nghiep vu

Dieu quan trong nhat:

- don vi phat hien chinh la `pair` = cap `tai xe - khach hang`
- `network` chi la bang chung ho tro
- `order` la cap hien thi de review, khong phai cap phat hien goc

## 3 lop diem chinh

He thong hien tai xoay quanh 3 lop diem:

- `pair_core_score`: cap nay bat thuong den muc nao neu chi nhin rieng cap do
- `network_support_score`: cap nay co duoc cung co boi cum lien ket xung quanh hay khong
- `priority_score`: tong hop de xep thu tu review

Cach doc don gian:

- `pair_core_score` cao: cap nay tu than da dang nghi
- `network_support_score` cao: cap nay khong don le, co them boi canh lien ket
- `priority_score` cao: nen xem truoc trong dashboard

## Cac thu muc chinh

- `src/algorithms`: tinh thong ke cap `tai xe - khach hang` va graph features
- `src/rules`: sinh `reason_code` va nhom rule de giai thich case
- `src/scoring`: cham diem, xep hang, va materialize output
- `src/dashboard`: dashboard cho analyst va van hanh
- `src/graph`: helper phuc vu Neo4j
- `scripts`: import du lieu va build daily outputs
- `docs`: tai lieu nghiep vu, scoring, dashboard review
- `tests`: unit tests cho pipeline

## Nen doc tai lieu nao truoc

Neu la nguoi moi vao project:

1. `docs/fraud_rules.md`
2. `docs/scoring_flagging.md`
3. `docs/kbc_daily_dashboard_review.md`

Neu can di sau vao logic graph:

1. `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`
2. `docs/proposed_graph_algorithms_for_fraud_scoring.md`

## Local setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

## Import du lieu ride vao Neo4j

Khoi dong Neo4j:

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j
```

Import cleaned ride orders:


```
python -m scripts.import_neo4j_demo_graph --orders-input data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2.parquet --cypher src\graph\cypher\002_demo_visualization_constraints.cypher --wipe-existing --confirm-wipe DELETE_ALL_DATA
Hoac chay truc tiep bang Python trong `venv`:


## Build daily outputs

Daily outputs la bo file de dashboard doc truc tiep.

Chay scoring va build output bang Python trong `venv`:

.\.venv\Scripts\python.exe -m scripts.build_task3_daily_outputs `
  --input data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet `
  --report-dir reports\task3

Cac output chinh:

- `reports/task3/kbc_pair_summary.csv`: bang trung tam o cap pair
- `reports/task3/kbc_pair_reasons.csv`: ly do tai sao pair bi dua vao shortlist
- `reports/task3/flagged_orders.parquet`: cac order lien quan de review nghiep vu
- `reports/task3/suspicious_components.csv`: thong tin cum lien ket de mo rong dieu tra

Luu y khi doc output:

- `flag rows` khac voi `unique flagged orders`
- mot `order` co the trung nhieu `reason_code`
- vi vay khong duoc doc tong so dong bi flag thanh tong so order bi flag

## Dashboard

Chay dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/dashboard/app.py --server.port 8502
```

Dashboard duoc thiet ke de tra loi 3 cau hoi:

1. Hom nay nhung cap nao can xem truoc?
2. Moi cap dang nghi vi ly do gi?
3. Cac order nao can mo ra de kiem tra chi tiet?

Theo logic moi, dashboard nen duoc doc nhu sau:

- pair evidence la trung tam
- network evidence la bo sung
- order detail la noi de xac minh nghiep vu
