#!/usr/bin/env python3
"""
Parse NASA_PSI_Combustion_Science_26_Investigations-2.md and generate
a folder and detailed JSON metadata for each of the 26 NASA PSI databases.
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MD_PATH = BASE_DIR / "NASA_PSI_Combustion_Science_26_Investigations-2.md"
OUTPUT_DIR = BASE_DIR / "data" / "psi_databases"


def parse_markdown(md_content: str):
    # Split by investigation headings (### 01. ..., ### 02. ...)
    sections = re.split(r'\n(?=### \d+\. )', md_content)

    investigations = []

    for section in sections:
        if not section.startswith("### "):
            continue

        # Extract title
        title_match = re.search(r'### \d+\.\s+(.+)', section)
        title = title_match.group(1).strip() if title_match else ""

        # Extract PSI Number
        psi_match = re.search(r'\*\*PSI number:\*\*\s+\*\*([^*]+)\*\*', section)
        psi_id = psi_match.group(1).strip() if psi_match else ""

        if not psi_id:
            continue

        # Extract Research area
        ra_match = re.search(r'\*\*Research area:\*\*\s+(.+)', section)
        research_area = ra_match.group(1).strip() if ra_match else "Combustion Science"

        # Extract Subresearch area
        sra_match = re.search(r'\*\*Subresearch area \([^)]+\):\*\*\s+(.+)', section)
        subresearch_area = sra_match.group(1).strip() if sra_match else None

        # Extract Scientific focus
        sf_match = re.search(r'\*\*Scientific focus:\*\*\s+(.+)', section)
        scientific_focus = sf_match.group(1).strip() if sf_match else None

        # Extract Project setting / type
        ps_match = re.search(r'\*\*Project setting / type:\*\*\s+(.+)', section)
        project_setting = ps_match.group(1).strip() if ps_match else None

        # Extract PSI record type
        rt_match = re.search(r'\*\*PSI record type:\*\*\s+(.+)', section)
        record_type = rt_match.group(1).strip() if rt_match else "Investigation"

        # Extract DOI
        doi_match = re.search(r'\*\*DOI:\*\*\s+\[([^\]]+)\]\(([^)]+)\)', section)
        doi = doi_match.group(1).strip() if doi_match else None
        doi_url = doi_match.group(2).strip() if doi_match else None

        # Extract Objectives
        obj_match = re.search(r'#### Objectives\s*\n\s*\n([^#]+?)(?=\n####|\n\*\*Sources|\Z)', section, re.DOTALL)
        objectives = obj_match.group(1).strip() if obj_match else ""

        # Extract Approach
        app_match = re.search(r'#### \*\*Approach\*\*\s*\n\s*\n([^#]+?)(?=\n\*\*Sources|\Z)', section, re.DOTALL)
        approach = app_match.group(1).strip() if app_match else ""

        # Extract Sources
        sources_match = re.search(r'\*\*Sources:\*\*\s+(.+)', section)
        sources_raw = sources_match.group(1).strip() if sources_match else ""
        # Parse links [label](url)
        sources = []
        for src_label, src_url in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', sources_raw):
            sources.append({"label": src_label, "url": src_url})

        investigations.append({
            "psi_id": psi_id,
            "title": title,
            "research_area": research_area,
            "subresearch_area": subresearch_area,
            "scientific_focus": scientific_focus,
            "project_setting": project_setting,
            "record_type": record_type,
            "doi": doi,
            "doi_url": doi_url,
            "objectives": objectives,
            "approach": approach,
            "sources": sources,
            "folder_path": f"data/psi_databases/{psi_id}",
            "csv_files": []  # Children CSVs will be placed here
        })

    return investigations


def main():
    if not MD_PATH.exists():
        print(f"Error: {MD_PATH} not found")
        return

    content = MD_PATH.read_text(encoding="utf-8")
    investigations = parse_markdown(content)

    print(f"Parsed {len(investigations)} investigations from markdown.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for inv in investigations:
        psi_id = inv["psi_id"]
        inv_dir = OUTPUT_DIR / psi_id
        inv_dir.mkdir(parents=True, exist_ok=True)

        json_path = inv_dir / "database.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=2, ensure_ascii=False)

        # Also write metadata.json for compatibility
        with open(inv_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=2, ensure_ascii=False)

        print(f"✓ Created {psi_id}: {inv_dir} -> database.json")

    print(f"\nAll {len(investigations)} database folders and JSON files successfully created in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
