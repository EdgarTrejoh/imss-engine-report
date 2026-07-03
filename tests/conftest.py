from pathlib import Path

import pandas as pd
import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name: str) -> pd.DataFrame:
        return pd.read_csv(FIXTURES / name, sep="|", keep_default_na=False, dtype=str)

    return _load
