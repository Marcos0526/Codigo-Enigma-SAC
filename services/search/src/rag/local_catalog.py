"""Read-only catalog and tabular data access for local NASA PSI investigations."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from datetime import date, datetime
from itertools import chain
from functools import lru_cache
from pathlib import Path
from statistics import fmean
from typing import Any, Dict, Iterator, List, Optional, Tuple

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _dataset_id(psi_id: str, path: Path) -> str:
    return f"{_slug(psi_id)}-{_slug(path.name)}"


def _is_number(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    text = str(value).strip()
    if not text:
        return False
    try:
        return math.isfinite(float(text))
    except ValueError:
        return False


def _as_number(value: Any) -> Optional[float]:
    try:
        number = float(str(value).strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _as_datetime(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    text = str(value or "").strip()
    if len(text) < 6:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _json_value(value: Any, column_type: str) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if column_type == "numeric":
        number = _as_number(value)
        return int(number) if number is not None and number.is_integer() else number
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class LocalPSICatalog:
    """Catalog backed exclusively by data/psi_databases, never synthetic data."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._investigations: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"NASA PSI data directory not found: {self.data_dir}")

        for directory in sorted(self.data_dir.glob("PSI-*")):
            metadata_path = directory / "metadata.json"
            if not directory.is_dir() or not metadata_path.is_file():
                continue
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            psi_id = str(metadata.get("psi_id") or directory.name)
            metadata["_directory"] = directory
            self._investigations[psi_id] = metadata

            for path in sorted(directory.iterdir()):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                dataset_id = _dataset_id(psi_id, path)
                source_url = metadata.get("doi_url") or next(
                    (
                        source.get("url")
                        for source in metadata.get("sources", [])
                        if source.get("url")
                    ),
                    "",
                )
                description = (
                    f"Local NASA PSI data file '{path.name}' from {metadata.get('title', psi_id)}. "
                    f"{metadata.get('objectives', '')}"
                ).strip()
                self._datasets[dataset_id] = {
                    "id": dataset_id,
                    "dataset_id": dataset_id,
                    "psi_id": psi_id,
                    "psiId": psi_id,
                    "name": path.stem.replace("_", " "),
                    "description": description,
                    "url": source_url,
                    "url_type": "investigation_landing_page",
                    "format": path.suffix.lower().lstrip("."),
                    "investigation_title": metadata.get("title", psi_id),
                    "investigationTitle": metadata.get("title", psi_id),
                    "source": "local NASA PSI investigation files",
                    "license": "See the source NASA PSI investigation",
                    "access_policy": "local read-only",
                    "tags": [
                        metadata.get("research_area", ""),
                        metadata.get("subresearch_area", ""),
                        metadata.get("scientific_focus", ""),
                    ],
                    "verification_status": "verified",
                    "verificationStatus": "verified",
                    "verified_at": None,
                    "_path": path,
                }

    def __len__(self) -> int:
        return len(self._datasets)

    @property
    def investigation_count(self) -> int:
        return len(self._investigations)

    def list_investigations(self) -> List[Dict[str, Any]]:
        return list(self._investigations.values())

    def list_datasets(self) -> List[Dict[str, Any]]:
        return list(self._datasets.values())

    def get_investigation(self, psi_id: str) -> Dict[str, Any]:
        investigation = self._investigations.get(psi_id)
        if not investigation:
            raise FileNotFoundError(f"NASA PSI investigation not found: {psi_id}")
        return investigation

    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            raise FileNotFoundError(f"Local NASA PSI dataset not found: {dataset_id}")
        return dataset

    def public_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """Return route-compatible metadata without the internal filesystem path."""
        dataset = self.get_dataset(dataset_id)
        schema = self.get_schema(dataset_id)
        result = {key: value for key, value in dataset.items() if not key.startswith("_")}
        result["numeric_columns"] = [
            column["column_name"]
            for column in schema["columns"]
            if column["column_type"] == "numeric"
        ]
        result["numericColumns"] = result["numeric_columns"]
        return result

    @lru_cache(maxsize=128)
    def get_schema(self, dataset_id: str) -> Dict[str, Any]:
        dataset = self.get_dataset(dataset_id)
        path: Path = dataset["_path"]
        rows, row_count = self._sample(path, sample_size=1000)
        if not rows:
            return {
                "datasetId": dataset_id,
                "columns": [],
                "rowCount": 0,
                "byteSize": path.stat().st_size,
                "profiledAt": None,
                "profileVersion": "local-file-v1",
            }

        headers = rows[0]
        samples = rows[1:]
        columns = []
        for position, header in enumerate(headers):
            values = [row[position] for row in samples if position < len(row)]
            present = [value for value in values if value is not None and str(value).strip()]
            numeric = [value for value in present if _is_number(value)]
            temporal = [value for value in present if _as_datetime(value)]
            if present and len(numeric) == len(present):
                column_type = "numeric"
            elif numeric:
                column_type = "mixed"
            elif present and len(temporal) == len(present):
                column_type = "datetime"
            elif len({str(value) for value in present}) <= 20:
                column_type = "categorical"
            else:
                column_type = "text"

            statistics = None
            if column_type == "numeric":
                numbers = [_as_number(value) for value in numeric]
                numbers = [value for value in numbers if value is not None]
                if numbers:
                    statistics = {
                        "min": min(numbers),
                        "max": max(numbers),
                        "mean": fmean(numbers),
                        "sampleSize": len(numbers),
                    }
            columns.append(
                {
                    "column_name": header,
                    "column_type": column_type,
                    "description": "Inferred from the local NASA PSI source file",
                    "unit": None,
                    "nullable": len(present) < len(values),
                    "sample_values": [_json_value(value, column_type) for value in present[:5]],
                    "statistics": statistics,
                    "ordinal_position": position + 1,
                }
            )

        return {
            "datasetId": dataset_id,
            "columns": columns,
            "rowCount": row_count,
            "byteSize": path.stat().st_size,
            "profiledAt": None,
            "profileVersion": "local-file-v1",
        }

    def get_preview(self, dataset_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        schema = self.get_schema(dataset_id)
        table, _ = self._sample(
            self.get_dataset(dataset_id)["_path"], sample_size=limit + 1, offset=offset
        )
        rows = table[1:] if table else []
        column_types = {
            column["column_name"]: column["column_type"] for column in schema["columns"]
        }
        headers = [column["column_name"] for column in schema["columns"]]
        output = [
            {
                header: _json_value(row[index] if index < len(row) else None, column_types[header])
                for index, header in enumerate(headers)
            }
            for row in rows
        ]
        return {
            "datasetId": dataset_id,
            "columns": schema["columns"],
            "rows": output,
            "totalRows": schema["rowCount"],
            "returnedRows": len(output),
            "offset": offset,
            "limit": limit,
            "warnings": [],
        }

    def get_chart_rows(
        self,
        dataset_id: str,
        x_axis: str,
        y_axis: Optional[str] = None,
        group_by: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        selected = [name for name in (x_axis, y_axis, group_by) if name]
        preview = self.get_preview(dataset_id, limit=min(max(limit * 4, limit), 10000))
        rows = []
        for row in preview["rows"]:
            if any(row.get(name) is None for name in selected):
                continue
            rows.append({name: row.get(name) for name in selected})
            if len(rows) >= limit:
                break
        return rows

    def retrieval_documents(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Build text/metadata pairs for the existing FAISS RAG pipeline."""
        documents: List[Tuple[str, Dict[str, Any]]] = []
        for investigation in self._investigations.values():
            psi_id = investigation["psi_id"]
            shared = (
                f"Investigation: {psi_id} — {investigation.get('title', '')}\n"
                f"Research area: {investigation.get('research_area', '')}\n"
                f"Subarea: {investigation.get('subresearch_area', '')}\n"
                f"Scientific focus: {investigation.get('scientific_focus', '')}\n"
                f"Setting: {investigation.get('project_setting', '')}\n"
                f"Objectives: {investigation.get('objectives', '')}\n"
                f"Approach: {investigation.get('approach', '')}"
            )
            documents.append(
                (
                    shared,
                    {
                        "source": f"{psi_id}/metadata.json",
                        "filename": "metadata.json",
                        "psi_id": psi_id,
                        "title": investigation.get("title", psi_id),
                    },
                )
            )
            for dataset in self._datasets.values():
                if dataset["psi_id"] != psi_id:
                    continue
                try:
                    schema = self.get_schema(dataset["id"])
                    columns = ", ".join(
                        f"{column['column_name']} ({column['column_type']})"
                        for column in schema["columns"]
                    )
                    row_count = schema["rowCount"]
                except (OSError, ValueError, csv.Error):
                    columns = "Schema unavailable"
                    row_count = "unknown"
                text = (
                    f"{shared}\n"
                    f"Dataset: {dataset['name']}\n"
                    f"Local file: {dataset['_path'].name}\n"
                    f"Format: {dataset['format']}\n"
                    f"Rows: {row_count}\n"
                    f"Columns: {columns}\n"
                    f"Description: {dataset['description']}"
                )
                documents.append(
                    (
                        text,
                        {
                            "source": f"{psi_id}/{dataset['_path'].name}",
                            "filename": dataset["_path"].name,
                            "page": 1,
                            "psi_id": psi_id,
                            "dataset_id": dataset["id"],
                            "title": dataset["name"],
                        },
                    )
                )
        return documents

    def _sample(self, path: Path, sample_size: int, offset: int = 0) -> Tuple[List[List[Any]], int]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._sample_csv(path, sample_size, offset)
        if suffix == ".xlsx":
            return self._sample_xlsx(path, sample_size, offset)
        if suffix == ".xls":
            return self._sample_xls(path, sample_size, offset)
        raise ValueError(f"Unsupported local data format: {suffix}")

    @staticmethod
    def _sample_csv(path: Path, sample_size: int, offset: int) -> Tuple[List[List[Any]], int]:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        handle = io.StringIO(text, newline="")
        sample_text = text[:16384]
        try:
            dialect = csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        try:
            first_row = next(reader)
        except StopIteration:
            return [], 0

        # ACME execution files have one run-metadata line before the real header.
        if (
            path.parent.name in {"PSI-20", "PSI-21", "PSI-22", "PSI-23"}
            and path.name.endswith("_data.csv")
        ):
            try:
                possible_header = next(reader)
                if possible_header and possible_header[0].strip() == "Time":
                    first_row = possible_header
                else:
                    reader = chain([possible_header], reader)
            except StopIteration:
                pass
        headers = [str(value).strip() or f"column_{index + 1}" for index, value in enumerate(first_row)]
        rows = []
        row_count = 0
        for row in reader:
            if offset <= row_count < offset + max(sample_size - 1, 0):
                rows.append(row)
            row_count += 1
        return [headers, *rows], row_count

    @staticmethod
    def _sample_xlsx(path: Path, sample_size: int, offset: int) -> Tuple[List[List[Any]], int]:
        from openpyxl import load_workbook

        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = (
                workbook["Calibrated Data"]
                if "Calibrated Data" in workbook.sheetnames
                else workbook.worksheets[0]
            )
            iterator: Iterator[Tuple[Any, ...]] = sheet.iter_rows(values_only=True)
            try:
                headers = [str(value).strip() if value is not None else f"column_{index + 1}" for index, value in enumerate(next(iterator))]
                headers = [value or f"column_{index + 1}" for index, value in enumerate(headers)]
                if sheet.title == "Calibrated Data":
                    next(iterator)  # Units belong to the schema, not to observations.
            except StopIteration:
                return [], 0
            rows = []
            for index, row in enumerate(iterator):
                if offset <= index < offset + max(sample_size - 1, 0):
                    rows.append(list(row))
                if index >= offset + sample_size - 1:
                    break
            header_rows = 2 if sheet.title == "Calibrated Data" else 1
            return [headers, *rows], max((sheet.max_row or header_rows) - header_rows, 0)
        finally:
            workbook.close()

    @staticmethod
    def _sample_xls(path: Path, sample_size: int, offset: int) -> Tuple[List[List[Any]], int]:
        import xlrd

        workbook = xlrd.open_workbook(path, on_demand=True)
        try:
            # Legacy workbooks often start with a notes sheet and keep the table
            # on a later sheet, so use the sheet with the most rows.
            sheet = max(workbook.sheets(), key=lambda item: item.nrows)
            if sheet.nrows == 0:
                return [], 0

            def cell_text(row_index: int, column_index: int) -> str:
                value = sheet.cell_value(row_index, column_index)
                if isinstance(value, float) and value.is_integer():
                    return ""
                return str(value).strip()

            header_row = 0
            for row_index in range(min(sheet.nrows, 30)):
                first = cell_text(row_index, 0) if sheet.ncols else ""
                present = sum(
                    1 for column in range(sheet.ncols) if cell_text(row_index, column)
                )
                if first and present >= 2:
                    header_row = row_index
                    break

            # Column blocks can carry their label in a preceding row, e.g.
            # "Instrument: P-Trak" above the readings column.
            section_labels = {}
            for row_index in range(header_row):
                for column in range(sheet.ncols):
                    text = cell_text(row_index, column)
                    if text.lower().startswith("instrument:"):
                        section_labels[column] = text.split(":", 1)[1].strip()

            headers: List[str] = []
            for column in range(sheet.ncols):
                text = cell_text(header_row, column)
                if not text or text.lower().startswith("number of points"):
                    text = section_labels.get(column, "")
                headers.append(text or f"column_{column + 1}")

            data_start = header_row + 1
            keep = [
                column
                for column in range(sheet.ncols)
                if any(
                    str(sheet.cell_value(row_index, column)).strip()
                    for row_index in range(data_start, min(data_start + 2000, sheet.nrows))
                )
            ]
            headers = [headers[column] for column in keep]
            seen: Dict[str, int] = {}
            for index, header in enumerate(headers):
                count = seen.get(header, 0)
                seen[header] = count + 1
                if count:
                    headers[index] = f"{header} ({count + 1})"

            rows = []
            for row_index in range(
                data_start + offset, min(data_start + offset + sample_size - 1, sheet.nrows)
            ):
                rows.append([sheet.cell_value(row_index, column) for column in keep])
            return [headers, *rows], max(sheet.nrows - data_start, 0)
        finally:
            workbook.release_resources()
