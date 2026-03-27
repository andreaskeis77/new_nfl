from new_nfl.settings import load_settings


def test_load_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()

    assert settings.env == "dev"
    assert settings.repo_root == tmp_path
    assert settings.data_root == tmp_path / "data"
    assert settings.db_path == tmp_path / "data" / "db" / "new_nfl.duckdb"
