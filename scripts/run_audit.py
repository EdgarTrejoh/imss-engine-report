from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imss_duckdb_exports import run_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DuckDB audit for an existing Phase 2 IMSS CSV.")
    parser.add_argument("input_csv")
    parser.add_argument("--output-dir", default="reports/audits")
    args = parser.parse_args()
    run_audit(args.input_csv, args.output_dir)


if __name__ == "__main__":
    main()
