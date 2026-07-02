from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imss_csv_profiler import main as profile_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile an existing IMSS CSV output.")
    parser.add_argument("input_csv")
    args = parser.parse_args()
    profile_csv(args.input_csv)


if __name__ == "__main__":
    main()
