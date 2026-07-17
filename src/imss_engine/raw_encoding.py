"""Deterministic IMSS raw CSV encoding resolution using the expected schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .schema import CRITICAL_METRIC_COLUMNS


DEFAULT_RAW_ENCODING = "auto"
SUPPORTED_RAW_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "latin-1")
DEFAULT_RAW_SEPARATOR = "|"

REQUIRED_RAW_DIMENSION_COLUMNS: tuple[str, ...] = (
    "cve_delegacion",
    "cve_subdelegacion",
    "cve_entidad",
    "cve_municipio",
    "sector_economico_1",
    "sector_economico_2",
    "sector_economico_4",
    "tamaño_patron",
    "sexo",
    "rango_edad",
    "rango_salarial",
)
REQUIRED_RAW_COLUMNS: tuple[str, ...] = REQUIRED_RAW_DIMENSION_COLUMNS + CRITICAL_METRIC_COLUMNS


class RawEncodingOrSchemaError(ValueError):
    """Raised when no requested encoding produces the required IMSS raw schema."""

    def __init__(
        self,
        message: str,
        resolution: "RawEncodingResolution",
        *,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.resolution = resolution
        self.reason = reason


@dataclass(frozen=True)
class RawEncodingResolution:
    encoding_requested: str
    encoding_detected: str | None
    encoding_candidates_tried: list[str]
    columns_detected: list[str]
    missing_required_columns: list[str]
    candidate_diagnostics: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_raw_header(header_line: str, separator: str) -> list[str]:
    """Split an IMSS header using only safe technical normalization."""
    return [
        column.strip().lstrip("\ufeff")
        for column in header_line.rstrip("\r\n").split(separator)
    ]


def _encoding_candidates(encoding: str) -> tuple[str, ...]:
    if encoding == DEFAULT_RAW_ENCODING:
        return SUPPORTED_RAW_ENCODINGS
    if encoding in SUPPORTED_RAW_ENCODINGS:
        return (encoding,)
    supported = ", ".join((DEFAULT_RAW_ENCODING, *SUPPORTED_RAW_ENCODINGS))
    raise ValueError(f"Unsupported raw encoding {encoding!r}. Expected one of: {supported}.")


def resolve_raw_encoding(
    path: str | Path,
    *,
    separator: str = DEFAULT_RAW_SEPARATOR,
    encoding: str = DEFAULT_RAW_ENCODING,
) -> RawEncodingResolution:
    """Resolve encoding only when the decoded header contains the complete schema."""
    raw_path = Path(path)
    candidates = _encoding_candidates(encoding)
    diagnostics: list[dict] = []

    for candidate in candidates:
        try:
            with raw_path.open("r", encoding=candidate, newline="") as file:
                header_line = file.readline()
        except UnicodeError as error:
            diagnostics.append(
                {
                    "encoding": candidate,
                    "decoded": False,
                    "error_message": str(error),
                    "separator_found": False,
                    "columns_detected": [],
                    "missing_required_columns": list(REQUIRED_RAW_COLUMNS),
                    "schema_match_count": 0,
                }
            )
            continue

        if not header_line or not header_line.rstrip("\r\n"):
            diagnostics.append(
                {
                    "encoding": candidate,
                    "decoded": True,
                    "error_message": "Raw header is empty.",
                    "separator_found": False,
                    "columns_detected": [],
                    "missing_required_columns": list(REQUIRED_RAW_COLUMNS),
                    "schema_match_count": 0,
                }
            )
            continue

        columns = normalize_raw_header(header_line, separator)
        missing = [column for column in REQUIRED_RAW_COLUMNS if column not in columns]
        separator_found = separator in header_line
        diagnostic = {
            "encoding": candidate,
            "decoded": True,
            "error_message": None,
            "separator_found": separator_found,
            "columns_detected": columns,
            "missing_required_columns": missing,
            "schema_match_count": len(REQUIRED_RAW_COLUMNS) - len(missing),
        }
        diagnostics.append(diagnostic)
        if separator_found and not missing:
            return RawEncodingResolution(
                encoding_requested=encoding,
                encoding_detected=candidate,
                encoding_candidates_tried=[item["encoding"] for item in diagnostics],
                columns_detected=columns,
                missing_required_columns=[],
                candidate_diagnostics=diagnostics,
            )

    decoded_diagnostics = [item for item in diagnostics if item["decoded"]]
    best = max(decoded_diagnostics, key=lambda item: item["schema_match_count"], default=None)
    resolution = RawEncodingResolution(
        encoding_requested=encoding,
        encoding_detected=None,
        encoding_candidates_tried=[item["encoding"] for item in diagnostics],
        columns_detected=list(best["columns_detected"]) if best else [],
        missing_required_columns=list(best["missing_required_columns"]) if best else [],
        candidate_diagnostics=diagnostics,
    )
    if decoded_diagnostics and all(not item["columns_detected"] for item in decoded_diagnostics):
        message = "Raw header is empty or invalid."
        reason = "empty_header"
    elif decoded_diagnostics and all(not item["separator_found"] for item in decoded_diagnostics):
        message = f"Raw header does not contain expected separator {separator!r}."
        reason = "invalid_separator"
        resolution = RawEncodingResolution(
            encoding_requested=encoding,
            encoding_detected=None,
            encoding_candidates_tried=resolution.encoding_candidates_tried,
            columns_detected=[],
            missing_required_columns=resolution.missing_required_columns,
            candidate_diagnostics=diagnostics,
        )
    elif decoded_diagnostics:
        message = "Raw header is missing required IMSS columns."
        reason = "missing_required_columns"
    else:
        message = "No supported encoding produced a readable raw header."
        reason = "unreadable_header"
    raise RawEncodingOrSchemaError(message, resolution, reason=reason)
