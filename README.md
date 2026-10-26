# Power MOSFET Layout Automation

This repository provides a Python-based CLI tool to generate rectangular NMOS HV layouts from modular GDS blocks. It is intended for automation and rapid prototyping of power MOSFET arrays, optionally including gate straps.

---

## Features

- Generate NMOS HV layouts with configurable total number of transistors.
- Automatically selects row and block configuration to minimize layout squareness error.
- Optional merge of ThickGateOx layer.
- Works with a set of reusable GDS blocks (`LEFT`, `MID`, `RIGHT`, `RIGHT1`).

---

## Repository Structure

power_mosfet_layout_automation/
├── blocks/ # GDS building blocks
│ ├── bloque_izquierdo.gds
│ ├── bloque_medio.gds
│ ├── bloque_derecho.gds
│ └── bloque_derecho_1_transistor.gds
├── scripts/ # Core Python scripts
│ └── generate_power_mosfet.py
├── runner/ # CLI entry point
│ └── main.py
├── output/ # Generated GDS layouts (ignored by git)
├── requirements.txt # Python dependencies
└── README.md


---

## Prerequisites

- Python 3.10+
- [gdstk](https://github.com/heitzmann/gdstk) Python package
- Optional: KLayout for visualizing GDS layouts

Install dependencies:

```bash
python -m pip install -r requirements.txt


#Usage 

git clone https://github.com/AC3E-SNPS-Analog-PDK-Team/power_mosfet_layout_automation.git
cd power_mosfet_layout_automation

Ensure the blocks/ folder contains the required GDS building blocks:
bloque_izquierdo.gds
bloque_medio.gds
bloque_derecho.gds
bloque_derecho_1_transistor.gds
Run the CLI tool:
python -m runner.main --m_total 100

This will generate a rectangular layout with 100 transistors. The default output GDS file will be saved in:

output/mosfet_M100.gds

Common options (run `python -m runner.main --help` for the full list):

```bash
python -m runner.main -m 100 --dry-run              # only print the row plan
python -m runner.main -m 100 -o my_dir/m100.gds     # custom output path
python -m runner.main -m 100 --extra-x 0.5 --extra-y 1.0
python -m runner.main -m 100 --thickox-layer 75/20  # flatten + merge ThickGateOx
python -m runner.main -m 100 --no-gate-strap        # skip POLY strap and gate rail
python -m runner.main -m 100 -v                     # detailed progress
```

Gate/active layers, strap clearance/height and rail width are configurable with
`--gate-layer`, `--active-layer`, `--strap-clearance`, `--strap-min-height` and
`--rail-width`. The tool exits with status 1 if the blocks are missing or no
rectangular layout exists for the requested `m_total` (e.g. `m_total < 3`).

Type checking (strict mypy, configured in `pyproject.toml`):

```bash
python -m pip install -r requirements-dev.txt
python -m mypy
```

# IMPORTANT
The LVS of the base blocks is clean in terms of electrical equivalence between schematic and layout. 
The remaining warnings correspond to discrepancies in port naming, since the base GDS do not contain explicitly exported pins with names consistent with the schematic. 

These base GDS were not modified to add ports, because these blocks are used as input for a script that generates a large MOSFET. Incorporating pins into the base layouts would cause massive replication of labels/ports in the final output, making their handling and extraction difficult.
