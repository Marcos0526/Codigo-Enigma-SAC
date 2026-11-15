#!/usr/bin/env python3
"""
Check the status of all investigations and verify data availability.
This script ensures that investigations without data have the status_message field set.
"""

import json
from pathlib import Path

BASE_DIR = Path("/home/dracdarktime/Documents/Maestria/Hackatones/Nasa/Codigo-Enigma-SAC/data/psi_databases")

def check_all():
    print(f"Checking {len(list(BASE_DIR.iterdir()))} investigations...")
    for d in sorted(BASE_DIR.iterdir()):
        if not d.is_dir():
            continue

        json_path = d / "database.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            has_data = len(data.get("csv_files", [])) > 0
            has_status = "status_message" in data

            if has_data:
                if has_status:
                    # Remove status_message if data is now present
                    if "status_message" in data:
                        del data["status_message"]
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"  ✓ {d.name}: Has data ({len(data['csv_files'])} files)")
            else:
                if not has_status:
                    data["status_message"] = "No data available for this investigation yet. Graphs cannot be generated."
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"  • {d.name}: No data - status message set")

if __name__ == "__main__":
    check_all()