# Part 2 — Infrastructure & Architecture Thinking

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION                            │
│                    Airflow (Docker Compose)                      │
│         Schedules daily: fetch → upload → load → dbt            │
└────────────┬──────────────┬──────────────┬──────────────────────┘
             │              │              │
             ▼              ▼              ▼
┌──────────────────┐  ┌──────────┐  ┌──────────────────────────┐
│   EXTRACT        │  │  STORE   │  │     TRANSFORM + SERVE    │
│                  │  │          │  │                           │
│  Python script   │  │  AWS S3  │  │       Snowflake          │
│  fetches from    ├─►│  bucket  ├─►│                           │
│  fakestoreapi    │  │  (raw/)  │  │  RAW ──► STAGING ──► BIZ │
│                  │  │          │  │                     │     │
└──────────────────┘  └──────────┘  │                     ▼     │
                                    │                   ML      │
                                    │              (Cortex ML)  │
                                    └──────────┬───────────────┘
                                               │
                                               ▼
                                    ┌──────────────────┐
                                    │    DASHBOARD      │
                                    │    Streamlit      │
                                    │  (reads from BIZ  │
                                    │   + ML schemas)   │
                                    └──────────────────┘
```

## Why these tools?

### Python (extraction)
- The API is simple REST with JSON responses. No need for Spark or a heavy framework.
- `requests` library is all we need. Anyone can read the code.

### AWS S3 (storage)
- Acts as our "data lake" — a landing zone before data enters Snowflake.
- Decouples extraction from loading (if S3 has data, we can reload Snowflake anytime).
- Snowflake can read directly from S3 via external stages — no extra tooling.
- Cheap and nearly infinite storage.

### Snowflake (warehouse)
- Handles JSON natively with VARIANT columns — no pre-processing needed.
- Separates compute from storage — we only pay for queries, not idle time.
- Built-in ML with Cortex — no separate ML infrastructure.
- Free trial available for development and demos.

### dbt (transformation)
- SQL-based transformations that anyone on the team can understand.
- Built-in testing (not_null, unique, relationships).
- Version controlled — every change is tracked in git.
- Clear lineage: staging → business → ml_features.

### Streamlit (dashboard)
- Python-native — same language as our extraction scripts.
- Connects directly to Snowflake.
- Fast to build a working dashboard (no frontend skills needed).
- Good enough for internal smalll analytics;

### Airflow (orchestration)
- DAG clearly shows task dependencies.
- Docker Compose makes local development easy.
- Easy to add alerting, retries, and monitoring later.

## If this were production...

### What I'd change

| Area | Current (demo) | Production |
|------|----------------|------------|
| **Secrets** | `.env` file | AWS Secrets Manager or Snowflake key-pair auth |
| **S3** | Single bucket, no lifecycle | Partitioned by date, lifecycle policies to archive old data |
| **Snowflake** | Single role, XSMALL warehouse | Multiple roles (loader, transformer, reader), auto-scaling warehouse |
| **dbt** | Local profiles.yml | dbt Cloud or CI/CD with `dbt build` in GitHub Actions |
| **Airflow** | Docker Compose, LocalExecutor | AWS MWAA or Astronomer, CeleryExecutor |
| **Monitoring** | None | Airflow alerts → Slack, dbt test failures → PagerDuty, Snowflake query history |
| **Dashboard** | Streamlit (local) | Streamlit Cloud or Tableau for executive-level reporting |
| **Testing** | dbt tests only | + Python unit tests, integration tests, data quality checks (Great Expectations) |
| **CI/CD** | Manual | GitHub Actions: lint → test → deploy dbt → trigger Airflow |

### Scaling considerations

1. **Data volume grows**: Snowflake auto-scales. S3 handles any volume. No changes needed.
2. **More data sources**: Add new Python scripts + dbt models. Airflow DAG gets new tasks.
3. **Real-time needs**: Swap batch for Snowpipe (auto-ingest from S3) or Kafka → Snowflake.
4. **Multiple environments**: Use dbt targets (dev/staging/prod) + separate Snowflake databases.

### Data quality

- **dbt tests** catch schema issues (nulls, duplicates, broken references).
- **Snowflake data sharing** lets teams access curated business tables without touching raw data.
- **Lineage** is visible through dbt docs (`dbt docs generate && dbt docs serve`).

