# Part 2 — Infrastructure & Architecture Thinking

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION                            │
│                      AWS MWAA (Managed Airflow)                 │
│       Schedules daily: fetch → upload → dbt → test → ml         │
└────────────┬──────────────┬──────────────┬──────────────────────┘
             │              │              │
             ▼              ▼              ▼
┌──────────────────┐  ┌──────────┐  ┌──────────────────────────┐
│   EXTRACT        │  │  STORE   │  │     TRANSFORM + SERVE    │
│                  │  │          │  │     (Incremental runs)   │
│  Python script   │  │  AWS S3  │  │                          │
│  fetches from    ├─►│  bucket  ├─►│       Snowflake          │
│  fakestoreapi    │  │  (raw/)  │  │  RAW ──► STAGING ──► BIZ │
│                  │  │          │  │                     │    │
└──────────────────┘  └──────────┘  │                     ▼    │
                                    │                   ML     │
                                    │              (Cortex ML) │
                                    └──────────┬───────────────┘
                                               │
                        ┌──────────────────────┼──────────────────────┐
                        ▼                      ▼                      ▼
             ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
             │    DASHBOARD     │   │    MONITORING    │   │    ALERTING      │
             │    Streamlit     │   │    Elementary    │   │    Slack         │
             │  (reads from BIZ │   │  (volume, fresh- │   │  (test failures, │
             │   + ML schemas)  │   │   ness anomalies)│   │   DAG failures)  │
             └──────────────────┘   └──────────────────┘   └──────────────────┘
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
- Good enough for internal analytics.

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
| **Monitoring** | None | dbt Elementary (volume/freshness anomalies) + Airflow alerts → Slack |
| **Dashboard** | Streamlit (local) | Streamlit Cloud or Tableau for executive-level reporting |
| **Testing** | dbt tests only | + Python unit tests, integration tests, data quality checks (Great Expectations) |
| **CI/CD** | Manual | GitHub Actions: lint → test → deploy dbt → trigger Airflow |

### Scaling considerations

1. **Data volume grows**: Snowflake auto-scales. S3 handles any volume. No changes needed.
2. **More data sources**: Add new Python scripts + dbt models. Airflow DAG gets new tasks.
3. **Real-time needs**: Swap batch for Snowpipe (auto-ingest from S3) or Kafka → Snowflake.
4. **Multiple environments**: Use dbt targets (dev/staging/prod) + separate Snowflake databases.

### Data quality & monitoring

- **dbt tests** catch schema issues (nulls, duplicates, broken references).
- **dbt Elementary** adds observability on top of dbt tests. `volume_anomalies` tracks row counts over time and flags when a table suddenly has 0 rows or 10x more than usual. 
- **Snowflake query history** provides cost tracking and slow-query detection.
- **Lineage** is visible through dbt docs (`dbt docs generate && dbt docs serve`).

### ML integration (Snowflake Cortex)

The pipeline already builds a feature table (`ML.USER_FEATURES`) via dbt, joining purchase data with user demographics. Each row is one user with: total orders, total spend, average order value, items purchased, unique categories, favorite category, and city.

The plan was to use **Snowflake Cortex ML Classification** to predict each user's favorite product category. The SQL in `snowflake/03_ml_model.sql` creates a classification model, trains it on `ML.USER_FEATURES` with `FAVORITE_CATEGORY` as the target, and writes predictions to `ML.USER_INTEREST_PREDICTIONS`. The dashboard already has an ML tab that reads these predictions and shows predicted vs. actual category with confidence scores.

In a production DAG, this becomes two extra tasks after `dbt_test`:

```
fetch_data >> upload_to_s3 >> dbt_run >> dbt_test >> ml_predict >> ml_validate
```

`ml_predict` runs the Cortex `PREDICT()` SQL, and `ml_validate` checks that the predictions table is populated. The model is created once; the DAG only re-runs predictions daily so they stay in sync with fresh feature data. Retraining would be a separate weekly task.

