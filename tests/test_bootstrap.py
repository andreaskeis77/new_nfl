import duckdb

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.settings import load_settings


def test_bootstrap_creates_baseline_database(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()

    bootstrap_local_environment(settings)

    db_path = tmp_path / "data" / "db" / "new_nfl.duckdb"
    assert db_path.exists()

    con = duckdb.connect(str(db_path))
    try:
        schemas = {
            row[0]
            for row in con.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        assert {"meta", "raw", "stg", "core", "mart", "feat", "sim", "scratch"}.issubset(
            schemas
        )

        tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'meta'"
            ).fetchall()
        }
        assert {
            "source_registry",
            "ingest_runs",
            "load_events",
            "dq_events",
            "pipeline_state",
        }.issubset(tables)
    finally:
        con.close()
