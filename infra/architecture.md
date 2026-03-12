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
- Good enough for internal analytics; not meant to replace Tableau/Looker at scale.

### Airflow (orchestration)
- Industry standard for data pipeline scheduling.
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

## Cost estimate (production)

| Service | Monthly estimate |
|---------|-----------------|
| S3 (< 1GB) | ~$0.02 |
| Snowflake XSMALL (1 hr/day) | ~$60 |
| Airflow (MWAA small) | ~$350 |
| Streamlit Cloud | Free (community) |
| **Total** | **~$410/month** |

For a small dataset like this, costs are minimal. The Airflow component is the biggest expense — for simpler needs, a cron job or GitHub Actions could replace it for ~$0.

## Questions I'd ask the team

1. How often does the source data change? (Determines schedule frequency)
2. Who are the consumers — analysts, ML engineers, executives? (Determines what to build in the business layer)
3. Any existing Snowflake infrastructure or roles we need to integrate with?
4. SLA requirements? (Determines monitoring and alerting needs)
5. Do we need historical snapshots or just latest state? (Determines whether we need dbt snapshots)
