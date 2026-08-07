# Graph Fraud Detection

Project nay duoc reset scope de tap trung vao bai toan `Driver-Customer Ghost-Trip Collusion` theo tai lieu:

- `docs/graph_algorithms_for_driver_customer_ghost_trip_collusion.md`

Huong chinh hien tai la:

1. `weighted edge outlier detection`
2. `bipartite concentration scoring`
3. `WCC`

Dashboard va report output deu bam theo luong:

- `pair_core_score`
- `network_support_score`
- `priority_score`

## Local setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

## Main folders

- `src/algorithms`: build pair stats va graph features
- `src/rules`: rule shortlist va reason code
- `src/scoring`: scoring pair, network support, output reports
- `src/dashboard`: Streamlit dashboard cho nguoi dung xem danh sach cap can chu y
- `src/graph`: Neo4j helpers va constraints
- `scripts`: build report va import ride orders
- `docs`: target architecture va note nghiep vu
- `tests`: unit tests

## Ride daily import

Khoi dong Neo4j:

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j
```

Import cleaned ride orders:

```powershell
.\scripts\run_ride_import.ps1 -Source data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet
```

Hoac goi truc tiep:

```powershell
python -m scripts.import_ride_daily_to_neo4j `
  --source data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet `
  --batch-size 2000
```

## Daily outputs

Build dashboard-ready reports tu du lieu ngay `2026-07-24` den `2026-07-29`:

```powershell
python -m scripts.build_task3_daily_outputs `
  --input data\handoff\ride\cleaned_orders\orders_ride_masked_2026-07-2[4-9].parquet `
  --report-dir reports/task3
```

Output chinh:

- `reports/task3/kbc_pair_summary.csv`
- `reports/task3/kbc_pair_reasons.csv`
- `reports/task3/suspicious_components.csv`
- `reports/task3/flagged_orders.parquet`

## Dashboard

Chay dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/dashboard/app.py --server.port 8502
```

Dashboard hien dung goc nhin nguoi dung:

- xem nhanh cap tai xe - khach hang can xem
- uu tien theo `priority_score`
- giai thich bang repeated pair, muc do tap trung, va nhom lien ket WCC
