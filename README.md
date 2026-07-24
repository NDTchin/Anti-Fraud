# Graph Fraud Detection

Sprint 1 project for loading ride orders into Neo4j, detecting suspicious graph patterns with Cypher and GDS, and visualizing fraud groups.

## Local setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Docker Desktop and Neo4j with APOC/GDS are infrastructure dependencies and are not installed inside the Python virtual environment.

## Main folders

- `src/ingestion`: read and validate source data.
- `src/transform`: normalize entities and build graph edges.
- `src/graph`: Neo4j connection, schema and Cypher queries.
- `src/rules`: explainable fraud rules.
- `src/algorithms`: GDS projections and algorithms.
- `src/scoring`: combine rule and algorithm evidence.
- `src/api`: FastAPI application.
- `src/dashboard`: Streamlit application.



## Dual Neo4j setup

If you want to run `food` and `ride` side by side, use [infra/docker-compose.dual-domains.yml](/D:/VSF/infra/docker-compose.dual-domains.yml).

- `food` Browser: `http://localhost:7474/browser/`
- `food` Bolt: `bolt://localhost:7687`
- `ride` Browser: `http://localhost:7475/browser/`
- `ride` Bolt: `bolt://localhost:7688`

Import each graph into its own store:

```powershell
docker compose -f infra/docker-compose.dual-domains.yml --profile tools run --rm neo4j-import-food
docker compose -f infra/docker-compose.dual-domains.yml --profile tools run --rm neo4j-import-ride
```

Start both containers:

```powershell
docker compose -f infra/docker-compose.dual-domains.yml up -d neo4j-food neo4j-ride
```

If you want the app or scripts to point to `ride`, set `NEO4J_URI=bolt://localhost:7688` in `.env`.
