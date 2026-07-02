from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit import analizar_y_auditar_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CSV audit for an existing IMSS output file.")
    parser.add_argument("input_csv")
    parser.add_argument("--output", default="reports/audits/auditoria.csv")
    args = parser.parse_args()
    analizar_y_auditar_csv(args.input_csv, args.output)


if __name__ == "__main__":
    main()
