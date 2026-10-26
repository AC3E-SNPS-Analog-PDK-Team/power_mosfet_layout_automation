"""Firma geométrica de un GDS, independiente del timestamp del archivo.

Uso para regenerar golden files:
    python tests/_signature.py output/mosfet_M23.gds ...
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import gdstk

# GDS guarda coordenadas en enteros de 1 nm; 5 decimales en um absorbe el ruido de float.
_DECIMALS = 5


def _r(v: float) -> float:
    return round(float(v), _DECIMALS) + 0.0  # +0.0 normaliza -0.0


def _cell_payload(cell: gdstk.Cell) -> dict[str, Any]:
    polys = sorted(
        [p.layer, p.datatype, [[_r(x), _r(y)] for x, y in p.points]]
        for p in cell.polygons
    )
    refs = sorted(
        [
            r.cell.name if isinstance(r.cell, gdstk.Cell) else str(r.cell),
            [_r(r.origin[0]), _r(r.origin[1])],
            _r(r.rotation),
            _r(r.magnification),
            bool(r.x_reflection),
        ]
        for r in cell.references
    )
    labels = sorted(
        [lb.text, lb.layer, lb.texttype, [_r(lb.origin[0]), _r(lb.origin[1])]]
        for lb in cell.labels
    )
    return {"polygons": polys, "references": refs, "labels": labels}


def gds_signature(path: Path) -> dict[str, Any]:
    """Retorna {sha256, cells, top_layers} de un GDS."""
    lib = gdstk.read_gds(path)
    cells = sorted((c for c in lib.cells if isinstance(c, gdstk.Cell)), key=lambda c: c.name)
    payload = {c.name: _cell_payload(c) for c in cells}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    # Conteo por capa del layout aplanado: no entra al hash, sirve para diagnosticar diffs.
    # El GDS puede traer bloques no usados como top-level huérfanos; el top real es el de mayor área.
    tops = [c for c in lib.top_level() if isinstance(c, gdstk.Cell)]
    top = max(tops, key=_bbox_area)
    flat = top.copy("_flat").flatten()
    counts = Counter((p.layer, p.datatype) for p in flat.polygons)
    return {
        "sha256": digest,
        "cells": [c.name for c in cells],
        "top": top.name,
        "top_layers": {f"{l}/{d}": n for (l, d), n in sorted(counts.items())},
    }


def _bbox_area(cell: gdstk.Cell) -> float:
    bb = cell.bounding_box()
    if bb is None:
        return 0.0
    (x0, y0), (x1, y1) = bb
    return (x1 - x0) * (y1 - y0)


if __name__ == "__main__":
    out = {Path(p).name: gds_signature(Path(p)) for p in sys.argv[1:]}
    print(json.dumps(out, indent=2, sort_keys=True))
