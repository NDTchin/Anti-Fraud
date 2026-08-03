# Graph Fraud Detection

Project này tập trung vào phát hiện gian lận `ride` bằng graph và rule-based analysis trên Neo4j.

## Local setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Docker Desktop và Neo4j với `APOC`/`GDS` là dependency hạ tầng, không nằm trong virtual environment Python.

## Main folders

- `src/algorithms`: logic phát hiện collusion và graph signals
- `src/config`: cấu hình `.env`
- `src/dashboard`: dashboard Streamlit cho analyst
- `src/graph`: Cypher constraints và Neo4j helpers
- `src/rules`: rule nghiệp vụ
- `src/scoring`: scoring và report output
- `scripts`: tác vụ build report và import dữ liệu
- `tests`: unit tests

## Ride daily import

Luồng import hiện tại là incremental upsert theo ngày, không còn rebuild toàn bộ Neo4j store.

Khởi động Neo4j:

```powershell
docker compose -f infra/docker-compose.full.yml up -d neo4j
```

Import một file `ride` đã clean:

```powershell
.\scripts\run_ride_import.ps1 -Source data\handoff\ride\cleaned_orders\orders_ride_clean_2026-07-14_to_17.parquet
```

Hoặc gọi trực tiếp:

```powershell
python -m scripts.import_ride_daily_to_neo4j `
  --source data\handoff\ride\cleaned_orders\orders_ride_clean_2026-07-14_to_17.parquet `
  --batch-size 2000
```

Script sẽ:

- đảm bảo Neo4j constraints/index tồn tại
- đọc dữ liệu theo batch
- `MERGE` `Order`, `Customer`, `Driver`, `Address`, `PromotionCode` và các node liên quan
- upsert quan hệ như `PLACED`, `SERVED`, `PICKUP_AT`, `DROPOFF_AT`, `USED_PROMO`

## Daily outputs

Để build output phục vụ dashboard:

```powershell
python -m scripts.build_task3_daily_outputs --report-dir reports/task3
```
