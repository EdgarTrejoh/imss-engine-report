from decimal import Decimal

from src.imss_engine.postgres.loader import summarize_reserved_periods


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def cursor(self):
        return self.cursor_instance


def test_summarize_reserved_periods_returns_compact_final_summary():
    connection = FakeConnection(
        [
            (
                "2026-01-31",
                2,
                Decimal("10"),
                Decimal("5"),
                Decimal("100.50"),
                Decimal("20.10"),
            )
        ]
    )

    result = summarize_reserved_periods(connection, period="2026-01-31")

    assert result["mode"] == "summary_reserved_periods"
    assert result["period_count"] == 1
    assert result["reads_source_csv"] is False
    assert result["touches_final_table"] is False
    assert connection.cursor_instance.params == ("2026-01-31",)
    assert "imss.imss_hechos_asegurados" in connection.cursor_instance.sql
    assert result["periods"] == [
        {
            "periodo_informacion": "2026-01-31",
            "final_row_count": 2,
            "asegurados_total_sum_ta": 10,
            "trabajadores_con_sbc_sum_ta_sal": 5,
            "masa_salarial_sum_masa_sal_ta": "100.50",
            "sbc_promedio": "20.10",
        }
    ]
