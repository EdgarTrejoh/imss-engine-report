from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imss_duckdb_exports import main as export_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DuckDB reports for an existing IMSS CSV output.")
    parser.add_argument("input_csv")
    args = parser.parse_args()
    export_csv(args.input_csv)


if __name__ == "__main__":
    main()
