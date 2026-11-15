import json
import os
from pathlib import Path

# Base investigation list
investigations = [
    ("PSI-20", "ACME — Burning Rate Emulator (BRE)"),
    ("PSI-21", "ACME — Coflow Laminar Diffusion Flame (CLD Flame)"),
    ("PSI-159", "ACME — Cool Flames Investigation with Gases (CFI-G)"),
    ("PSI-10", "ACME — Flame Design"),
    ("PSI-22", "ACME — Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames)"),
    ("PSI-23", "ACME — Structure and Response of Spherical Diffusion Flames (s-Flames)"),
    ("PSI-26", "Burning and Suppression of Solids (BASS)"),
    ("PSI-25", "Burning and Suppression of Solids — II (BASS-II)"),
    ("PSI-60", "Computational and Experimental Analysis of SPICE Data Sets"),
    ("PSI-62", "Concurrent Flame Spread Modeling using Flamelet Generated Manifolds in Microgravity with Comparison to BASS Experiments using Two-Color Tomography"),
    ("PSI-39", "Cool Flames Investigation (CFI)"),
    ("PSI-47", "Dust and Aerosol Measurement Feasibility Test (DAFT) / DAFT-2"),
    ("PSI-117", "Effect of External Thermo-Convective Perturbation on Cool Flame Dynamics: A Multidimensional Multi-Physics CFD Analysis"),
    ("PSI-69", "Flame Extinguishment Experiment (FLEX)"),
    ("PSI-68", "Official investigation title not verified"),
    ("PSI-142", "Quantitative Studies of Cool Flame Transitions at Radiation/Stretch Extinction Using Counterflow Flames"),
    ("PSI-101", "Smoke Aerosol Measurement Experiment — Reflight (SAME-R)"),
    ("PSI-102", "Smoke Aerosol Measurement Experiment (SAME)"),
    ("PSI-107", "Smoke Point in Co-flow Experiment (SPICE)"),
    ("PSI-99", "Spacecraft Fire Safety Experiment — II (SAFFIRE-II)"),
    ("PSI-100", "Spacecraft Fire Safety Experiment — III (SAFFIRE-III)"),
    ("PSI-98", "Spacecraft Fire Safety Experiment — I (SAFFIRE-I)"),
    ("PSI-106", "Structure and Liftoff in Combustion Experiment (SLICE)"),
    ("PSI-181", "Official investigation title not verified"),
    ("PSI-108", "Official investigation title not verified"),
    ("PSI-115", "Utilization of SAME Data for Advanced Modeling and Simulation of Smoke Generation in Micro-Gravity")
]

BASE_DIR = Path("/home/dracdarktime/Documents/Maestria/Hackatones/Nasa/Codigo-Enigma-SAC/data/psi_databases")

for psi_id, title in investigations:
    folder = BASE_DIR / psi_id
    folder.mkdir(parents=True, exist_ok=True)

    metadata = {
        "psi_id": psi_id,
        "title": title,
        "csv_files": []
    }

    with open(folder / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=4)

print(f"Generated {len(investigations)} investigation folders in {BASE_DIR}")
