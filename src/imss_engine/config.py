"""Configuration helpers for the IMSS engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("config/config.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load a YAML configuration file without triggering ETL execution."""
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
