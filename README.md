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

git clone https://github.com/<ORG_NAME>/power_mosfet_layout_automation.git
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
