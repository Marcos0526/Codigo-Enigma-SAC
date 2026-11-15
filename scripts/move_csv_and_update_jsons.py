#!/usr/bin/env python3
import os
import json
import shutil
from pathlib import Path

BASE_DIR = Path("/home/dracdarktime/Documents/Maestria/Hackatones/Nasa/Codigo-Enigma-SAC")
SOURCE_DIR = BASE_DIR / "psi csv 1"
TARGET_BASE = BASE_DIR / "data" / "psi_databases"

def update_json(folder_path, files_added):
    json_files = ["database.json", "metadata.json"]
    for jf in json_files:
        p = folder_path / jf
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reset or initialize csv_files
            data["csv_files"] = []
            if files_added:
                for file_name in files_added:
                    data["csv_files"].append({
                        "path": file_name,
                        "description": f"Dataset file: {file_name}",
                        "format": file_name.split(".")[-1]
                    })
                # Remove no data message if it existed
                if "status_message" in data:
                    del data["status_message"]
            else:
                data["status_message"] = "No data available for this investigation yet. Graphs cannot be generated."

            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # 1. Move files
    if SOURCE_DIR.exists():
        for source_folder in SOURCE_DIR.iterdir():
            if not source_folder.is_dir():
                continue

            # Map folder name: psi20 -> PSI-20
            psi_num = source_folder.name.replace("psi", "")
            target_psi_id = f"PSI-{psi_num}"
            target_folder = TARGET_BASE / target_psi_id

            if not target_folder.exists():
                print(f"Warning: Target folder {target_folder} does not exist for {source_folder.name}")
                continue

            files_moved = []
            for file in source_folder.iterdir():
                if file.is_file():
                    shutil.move(str(file), str(target_folder / file.name))
                    files_moved.append(file.name)

            print(f"Moved {len(files_moved)} files from {source_folder.name} to {target_psi_id}")

    # 2. Update all JSONs (even for folders that didn't have source data)
    for target_folder in TARGET_BASE.iterdir():
        if not target_folder.is_dir():
            continue

        # Check current files in folder (excluding .json files)
        current_files = [f.name for f in target_folder.iterdir() if f.is_file() and not f.name.endswith(".json")]
        update_json(target_folder, current_files)
        print(f"Updated JSONs for {target_folder.name} (found {len(current_files)} data files)")

    # 3. Remove source directory
    if SOURCE_DIR.exists():
        shutil.rmtree(SOURCE_DIR)
        print(f"Removed source directory: {SOURCE_DIR}")

if __name__ == "__main__":
    main()
