from src.imss_engine.postgres.config import PostgresConfig, load_dotenv_if_exists


def test_load_dotenv_if_exists_does_not_override_existing_env(tmp_path, monkeypatch):
    postgres_env_keys = (
        "IMSS_PG_HOST",
        "IMSS_PG_PORT",
        "IMSS_PG_DATABASE",
        "IMSS_PG_USER",
        "IMSS_PG_PASSWORD",
    )
    for key in postgres_env_keys:
        monkeypatch.delenv(key, raising=False)

    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "\n".join(
            [
                "IMSS_PG_HOST=from_file",
                "IMSS_PG_PORT=5432",
                "IMSS_PG_DATABASE=imss_engine_test",
                "IMSS_PG_USER=imss_user",
                "IMSS_PG_PASSWORD='secret_from_file'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IMSS_PG_HOST", "from_environment")

    loaded = load_dotenv_if_exists(dotenv)

    assert loaded["IMSS_PG_PORT"] == "5432"
    assert "IMSS_PG_HOST" not in loaded
    assert PostgresConfig.from_env().host == "from_environment"
