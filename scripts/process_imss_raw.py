from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.imss_engine.raw_processing import process_imss_raw_period


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process one explicitly requested IMSS raw CSV into a temporary aggregate output."
    )
    parser.add_argument("--period", required=True, help="Period to process in YYYY-MM-DD format.")
    parser.add_argument(
        "--raw-root",
        default="data/raw/imss/asegurados",
        help="Root directory for raw IMSS asegurados files.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/processing",
        help="Directory for temporary processing outputs and manifests.",
    )
    parser.add_argument("--chunk-size", type=int, default=100000, help="CSV chunk size.")
    parser.add_argument(
        "--encoding",
        choices=("auto", "latin-1", "utf-8-sig"),
        default="auto",
        help="Raw encoding resolution mode.",
    )
    parser.add_argument("--separator", default="|", help="Expected raw file separator.")
    parser.add_argument("--duckdb-memory-limit", default="1GB", help="DuckDB memory limit.")
    parser.add_argument("--duckdb-threads", type=int, default=2, help="DuckDB worker threads.")
    parser.add_argument(
        "--preserve-temporary-on-failure",
        action="store_true",
        help="Keep per-run DuckDB temporary files after a failure.",
    )
    parser.add_argument("--write-parquet", action="store_true")
    parser.add_argument(
        "--parquet-compression",
        choices=("zstd", "snappy"),
        default="zstd",
    )
    args = parser.parse_args()

    manifest, manifest_path = process_imss_raw_period(
        args.period,
        raw_root=args.raw_root,
        output_dir=args.output_dir,
        chunk_size=args.chunk_size,
        encoding=args.encoding,
        separator=args.separator,
        duckdb_memory_limit=args.duckdb_memory_limit,
        duckdb_threads=args.duckdb_threads,
        preserve_temporary_on_failure=args.preserve_temporary_on_failure,
        write_parquet=args.write_parquet,
        parquet_compression=args.parquet_compression,
    )
    payload = {
        "manifest_path": str(manifest_path),
        "result": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    if manifest["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
