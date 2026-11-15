"""Tests for the read-only local NASA PSI catalog."""

import json

from services.search.src.rag.local_catalog import LocalPSICatalog


def make_investigation(tmp_path, psi_id="PSI-20"):
    directory = tmp_path / psi_id
    directory.mkdir()
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "psi_id": psi_id,
                "title": "Real local investigation",
                "research_area": "Combustion Science",
                "objectives": "Test real measurements",
                "approach": "Read observations without modifying them",
                "sources": [{"url": "https://psi.nasa.gov/example"}],
            }
        ),
        encoding="utf-8",
    )
    return directory


def test_acme_header_preview_and_chart_use_real_rows(tmp_path):
    directory = make_investigation(tmp_path)
    path = directory / "19056A2_data.csv"
    path.write_text(
        "2026-01-01,Test Point 1\n"
        "Time,Temperature,Pressure\n"
        "21:31:53:317,100.5,1.2\n"
        "21:31:53:325,101.5,1.3\n"
        "21:31:53:333,102.5,1.4\n",
        encoding="utf-8",
    )
    catalog = LocalPSICatalog(tmp_path)
    dataset_id = "psi-20-19056a2-data-csv"

    schema = catalog.get_schema(dataset_id)
    assert schema["rowCount"] == 3
    assert [column["column_name"] for column in schema["columns"]] == [
        "Time",
        "Temperature",
        "Pressure",
    ]
    assert catalog.public_dataset(dataset_id)["numericColumns"] == [
        "Temperature",
        "Pressure",
    ]

    preview = catalog.get_preview(dataset_id, limit=2)
    assert preview["returnedRows"] == 2
    assert preview["rows"] == [
        {"Time": "21:31:53:317", "Temperature": 100.5, "Pressure": 1.2},
        {"Time": "21:31:53:325", "Temperature": 101.5, "Pressure": 1.3},
    ]

    offset = catalog.get_preview(dataset_id, limit=1, offset=1)
    assert offset["rows"][0]["Temperature"] == 101.5
    rows = catalog.get_chart_rows(dataset_id, "Time", "Temperature", limit=2)
    assert [row["Temperature"] for row in rows] == [100.5, 101.5]


def test_windows_1252_and_mixed_values_are_not_fabricated(tmp_path):
    directory = make_investigation(tmp_path, psi_id="PSI-69")
    path = directory / "experiment.csv"
    path.write_bytes(
        "Fuel; name,Burn time; s,Diameter; mm\n"
        "Heptane,~6,–\n"
        "Methanol,7,1.5\n".encode("cp1252")
    )
    catalog = LocalPSICatalog(tmp_path)
    dataset_id = "psi-69-experiment-csv"
    schema = catalog.get_schema(dataset_id)
    types = {column["column_name"]: column["column_type"] for column in schema["columns"]}

    assert types["Fuel; name"] == "categorical"
    assert types["Burn time; s"] == "mixed"
    assert types["Diameter; mm"] == "mixed"


def test_investigation_without_files_has_metadata_but_no_dataset(tmp_path):
    make_investigation(tmp_path, psi_id="PSI-10")
    catalog = LocalPSICatalog(tmp_path)

    assert catalog.investigation_count == 1
    assert len(catalog) == 0
    documents = catalog.retrieval_documents()
    assert len(documents) == 1
    assert documents[0][1]["psi_id"] == "PSI-10"
