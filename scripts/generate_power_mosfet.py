# -*- coding: utf-8 -*-
"""
Generador de layout NMOS HV de potencia (Python puro, SIN pya) — requiere gdstk.

Basado en segunda_gen_gates.py.

Convención:
- Extremo IZQUIERDO : bloque_izquierdo (2 trans)
- Centro repetible  : bloque_medio     (2 trans)
- Extremo DERECHO   : bloque_derecho   (2 trans)
- Extremo DERECHO (impar): bloque_derecho_1_transistor (1 trans)

Condición para evitar "escalones/notches":
- NO se permite mezclar en el mismo layout filas que terminen con RIGHT (2 trans) y otras con RIGHT1 (1 trans).
- El layout entero elige UNA opción:
    A) todas las filas terminan con RIGHT
    B) todas las filas terminan con RIGHT1
- Además, todas las filas son idénticas: mismo n_mid.
=> El contorno queda rectangular y continuo, aunque no sea un cuadrado perfecto.
=> Se elige la solución más "cuadrada posible" (W/H cercano a 1) entre las que cumplan EXACTAMENTE m_total.

Merge opcional para ThickGateOx.drawing:
- GDS no guarda nombres de capa: hay que indicar layer/datatype (ver LayoutConfig.thickox).
- Incluye polygons+paths y hace flatten del TOP antes de merge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import gdstk

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
BLOCKS_DIR = BASE_DIR / "blocks"
OUTPUT_DIR = BASE_DIR / "output"

GDS_LEFT_NAME = "bloque_izquierdo.gds"
GDS_MID_NAME = "bloque_medio.gds"
GDS_RIGHT_NAME = "bloque_derecho.gds"
GDS_RIGHT1_NAME = "bloque_derecho_1_transistor.gds"


class NoSolutionError(RuntimeError):
    """No existe un layout rectangular (sin notch) para el m_total pedido."""


@dataclass(frozen=True)
class LayerSpec:
    layer: int
    datatype: int = 0

    def __str__(self) -> str:
        return f"{self.layer}/{self.datatype}"


@dataclass(frozen=True)
class BlockSizes:
    """Ancho/alto (um) de cada bloque base."""

    w_left: float
    w_mid: float
    w_right: float
    w_right1: float
    h_row: float


@dataclass(frozen=True)
class LayoutPlan:
    n_rows: int
    n_mid: int
    use_right1: bool
    trans_per_row: int
    width: float
    height: float
    squareness: float


@dataclass(frozen=True)
class LayoutConfig:
    m_total: int
    # Espacio extra entre bloques / filas (um)
    extra_space_x: float = 0.0
    extra_space_y: float = 0.0
    # Gate strap (POLY) en bloques + rail vertical en TOP
    gate_strap: bool = True
    gate: LayerSpec = LayerSpec(5, 0)
    active: LayerSpec = LayerSpec(1, 0)
    strap_y_clear: float = 0.09  # ANTES 0.01
    strap_min_h: float = 0.20
    rail_w: float = 0.18  # ANTES 0.25
    # Merge ThickGateOx (None = no merge)
    thickox: LayerSpec | None = None


Bbox = tuple[float, float, float, float, float, float]


def must_exist(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")


def load_main_cell(gds_path: Path) -> tuple[gdstk.Library, gdstk.Cell]:
    """Lee un GDS y retorna (lib, main_cell) donde main_cell es la celda con bbox más grande."""
    lib = gdstk.read_gds(gds_path)
    best: gdstk.Cell | None = None
    best_area = -1.0
    for c in lib.cells:
        if not isinstance(c, gdstk.Cell):
            continue
        bb = c.bounding_box()
        if bb is None:
            continue
        (xmin, ymin), (xmax, ymax) = bb
        area = (xmax - xmin) * (ymax - ymin)
        if area > best_area:
            best_area = area
            best = c
    if best is None:
        raise RuntimeError(f"No encontré celdas con geometría en: {gds_path}")
    return lib, best


def bbox_wh(cell: gdstk.Cell) -> Bbox:
    bb = cell.bounding_box()
    if bb is None:
        raise RuntimeError(f"Celda {cell.name} no tiene bounding box.")
    (xmin, ymin), (xmax, ymax) = bb
    return xmin, ymin, xmax, ymax, (xmax - xmin), (ymax - ymin)


def copy_lib_with_prefix(
    lib_in: gdstk.Library, out_lib: gdstk.Library, prefix: str
) -> dict[str, gdstk.Cell]:
    """
    Copia todas las celdas de lib_in a out_lib renombrándolas con prefijo
    para evitar colisiones entre los 4 GDS.
    """
    mapping: dict[str, gdstk.Cell] = {}
    for c in lib_in.cells:
        if not isinstance(c, gdstk.Cell):
            continue
        new_cell = c.copy(f"{prefix}__{c.name}")
        mapping[c.name] = new_cell
        out_lib.add(new_cell)
    return mapping


def row_width(n_mid: int, use_right1: bool, sizes: BlockSizes, extra_x: float) -> float:
    """
    Ancho físico de una fila:
      LEFT + MID*n_mid + (RIGHT o RIGHT1)
    """
    w = sizes.w_left + n_mid * sizes.w_mid + (sizes.w_right1 if use_right1 else sizes.w_right)
    blocks = 2 + n_mid  # left + mids + right/right1
    if blocks > 1:
        w += (blocks - 1) * extra_x
    return w


def trans_per_row(n_mid: int, use_right1: bool) -> int:
    """
    Conteo de transistores por fila:
      LEFT=2, MID=2, RIGHT=2, RIGHT1=1
    """
    return 2 + 2 * n_mid + (1 if use_right1 else 2)


def total_height(n_rows: int, h_row: float, extra_y: float) -> float:
    return n_rows * h_row + max(0, n_rows - 1) * extra_y


def plan_layout(
    m_total: int, sizes: BlockSizes, extra_x: float = 0.0, extra_y: float = 0.0
) -> LayoutPlan:
    """
    Búsqueda SIN notch:
    - elegir UNA sola terminación (RIGHT o RIGHT1) para TODAS las filas
    - filas idénticas (mismo n_mid)
    - m_total debe ser divisible por trans_per_row
    - elegir el layout más "cuadrado" posible
    """
    best_key: tuple[float, float, int, int, bool] | None = None
    best: LayoutPlan | None = None

    for use_right1 in (False, True):
        for n_mid in range(0, m_total // 2 + 1):
            t_row = trans_per_row(n_mid, use_right1)
            if m_total % t_row != 0:
                continue  # debe cerrar exacto

            n_rows = m_total // t_row
            if n_rows <= 0:
                continue

            w = row_width(n_mid, use_right1, sizes, extra_x)
            h = total_height(n_rows, sizes.h_row, extra_y)
            if w <= 0 or h <= 0:
                continue

            squareness = abs((w / h) - 1.0)
            # (leve) penalización por muchísimas filas
            score = squareness + 0.0005 * n_rows

            key = (score, squareness, n_rows, n_mid, use_right1)
            if best_key is None or key < best_key:
                best_key = key
                best = LayoutPlan(n_rows, n_mid, use_right1, t_row, w, h, squareness)

    if best is None:
        raise NoSolutionError(
            f"No hay solución SIN notch para m_total={m_total} usando filas idénticas. "
            "La fila mínima tiene 3 transistores (LEFT+RIGHT1); "
            "cambia m_total o agrega fillers/dummies."
        )
    return best


def merge_layer_geoms(
    cell: gdstk.Cell, layer: int, datatype: int, precision: float = 1e-6
) -> None:
    """
    Merge (OR) de geometría en (layer,datatype) dentro de 'cell', incluyendo polygons y paths.
    Requiere flatten del cell para que la geometría de subceldas quede en esta celda.
    """
    # Cell.polygons / Cell.paths son de solo lectura: se usa remove()/add().
    target: list[gdstk.Polygon] = []
    remove_polys: list[gdstk.Polygon] = []
    remove_paths: list[gdstk.FlexPath | gdstk.RobustPath] = []

    for p in cell.polygons:
        if p.layer == layer and p.datatype == datatype:
            target.append(p)
            remove_polys.append(p)

    for path in cell.paths:
        # Un path puede tener varias capas; to_polygons las expande por separado.
        polys = path.to_polygons()
        hits = [p for p in polys if p.layer == layer and p.datatype == datatype]
        if hits:
            target.extend(hits)
            remove_paths.append(path)
            # conservar la parte del path que está en otras capas
            cell.add(*(p for p in polys if not (p.layer == layer and p.datatype == datatype)))

    log.info("[MERGE] Found %d shapes on layer=%d, datatype=%d", len(target), layer, datatype)

    if not target:
        return

    merged = gdstk.boolean(target, [], "or", precision=precision, layer=layer, datatype=datatype)
    cell.remove(*remove_polys, *remove_paths)
    cell.add(*merged)
    log.info("[MERGE] After OR -> %d merged polygons", len(merged))


def _max_y_of_layer(cell: gdstk.Cell, spec: LayerSpec) -> float | None:
    ys = [
        p.bounding_box()[1][1]  # ymax
        for p in cell.polygons
        if p.layer == spec.layer and p.datatype == spec.datatype
    ]
    return max(ys) if ys else None


def add_gate_strap_poly(
    cell: gdstk.Cell,
    gate: LayerSpec = LayerSpec(5, 0),
    active: LayerSpec = LayerSpec(1, 0),
    y_clear: float = 10.0,  # "margen" arriba del active y abajo del borde del gate
    min_h: float = 40.0,  # alto mínimo del strap (en unidades del GDS)
) -> None:
    """
    Agrega un strap HORIZONTAL en POLY (misma capa del gate) dentro del bbox del cell.
    - Une gates internas
    - Extiende a bordes del cell para conexión por abutment
    """
    bb = cell.bounding_box()
    if bb is None:
        raise RuntimeError(f"{cell.name}: sin bounding box.")
    (x0, y0), (x1, y1) = bb

    gate_top = _max_y_of_layer(cell, gate)
    if gate_top is None:
        log.warning("[GATE] %s: no encontré POLY gate en %s.", cell.name, gate)
        return

    active_top = _max_y_of_layer(cell, active)
    # Si no hay active, igual hacemos el strap cerca del top del gate
    if active_top is None:
        active_top = gate_top - (min_h + 2 * y_clear)

    # Ventana segura: entre active_top y gate_top
    y_lo = active_top + y_clear
    y_hi = gate_top - y_clear

    if y_hi <= y_lo:
        # fallback (no ideal): usa un strap delgado pegado al top del gate
        y_hi = gate_top - 1.0
        y_lo = y_hi - min_h

    # No salirse del bbox del cell
    y_lo = max(y_lo, y0)
    y_hi = min(y_hi, y1)

    # asegura altura mínima si se puede
    if (y_hi - y_lo) < min_h and (y1 - y0) >= min_h:
        y_hi = min(y1, y_lo + min_h)

    if y_hi <= y_lo:
        log.warning("[GATE] %s: no pude ubicar strap (revisa y_clear/min_h).", cell.name)
        return

    # Strap: de borde a borde en X, en la capa de gate poly
    cell.add(gdstk.rectangle((x0, y_lo), (x1, y_hi), layer=gate.layer, datatype=gate.datatype))
    log.info("[GATE] Strap POLY agregado en %s: y=[%g,%g] x=[%g,%g]", cell.name, y_lo, y_hi, x0, x1)


def add_vertical_gate_rail_top(
    top: gdstk.Cell,
    total_h: float,
    gate: LayerSpec = LayerSpec(5, 0),
    rail_w: float = 60.0,  # ancho del rail en X
) -> None:
    """
    Rail vertical en el TOP (POLY) para unir todas las filas.
    Se ubica en el borde izquierdo (x=0..rail_w).
    """
    top.add(gdstk.rectangle((0.0, 0.0), (rail_w, total_h), layer=gate.layer, datatype=gate.datatype))
    log.info("[GATE] Rail vertical TOP: x=[0,%g] y=[0,%g]", rail_w, total_h)


@dataclass(frozen=True)
class _Blocks:
    libs: tuple[gdstk.Library, gdstk.Library, gdstk.Library, gdstk.Library]
    cells: tuple[gdstk.Cell, gdstk.Cell, gdstk.Cell, gdstk.Cell]
    sizes: BlockSizes


def _load_blocks(blocks_dir: Path) -> _Blocks:
    paths = [blocks_dir / n for n in (GDS_LEFT_NAME, GDS_MID_NAME, GDS_RIGHT_NAME, GDS_RIGHT1_NAME)]
    for p in paths:
        must_exist(p)

    log.info("[INFO] Inputs:")
    for label, p in zip(("LEFT", "MID", "RIGHT", "RIGHT1"), paths):
        log.info("  %-6s: %s", label, p)

    lib_l, cell_l = load_main_cell(paths[0])
    lib_m, cell_m = load_main_cell(paths[1])
    lib_r, cell_r = load_main_cell(paths[2])
    lib_r1, cell_r1 = load_main_cell(paths[3])

    *_, w_l, h_l = bbox_wh(cell_l)
    *_, w_m, h_m = bbox_wh(cell_m)
    *_, w_r, h_r = bbox_wh(cell_r)
    *_, w_r1, h_r1 = bbox_wh(cell_r1)

    sizes = BlockSizes(w_l, w_m, w_r, w_r1, h_row=max(h_l, h_m, h_r, h_r1))

    log.info("[INFO] Block sizes (um):")
    log.info("  LEFT  : W=%.3f, H=%.3f", w_l, h_l)
    log.info("  MID   : W=%.3f, H=%.3f", w_m, h_m)
    log.info("  RIGHT : W=%.3f, H=%.3f", w_r, h_r)
    log.info("  RIGHT1: W=%.3f, H=%.3f", w_r1, h_r1)
    log.info("[INFO] Row height used (um): %.3f", sizes.h_row)

    return _Blocks((lib_l, lib_m, lib_r, lib_r1), (cell_l, cell_m, cell_r, cell_r1), sizes)


def compute_plan(config: LayoutConfig, blocks_dir: Path = BLOCKS_DIR) -> LayoutPlan:
    """Calcula el plan de filas sin generar el GDS."""
    blocks = _load_blocks(blocks_dir)
    return plan_layout(config.m_total, blocks.sizes, config.extra_space_x, config.extra_space_y)


def generate_layout(
    config: LayoutConfig, output_path: Path, blocks_dir: Path = BLOCKS_DIR
) -> LayoutPlan:
    """Genera el GDS del MOSFET de potencia en output_path y retorna el plan usado."""
    blocks = _load_blocks(blocks_dir)
    sizes = blocks.sizes
    extra_x, extra_y = config.extra_space_x, config.extra_space_y
    plan = plan_layout(config.m_total, sizes, extra_x, extra_y)

    # --- build output lib ---
    out = gdstk.Library()

    lib_l, lib_m, lib_r, lib_r1 = blocks.libs
    cell_l, cell_m, cell_r, cell_r1 = blocks.cells
    L = copy_lib_with_prefix(lib_l, out, "L")[cell_l.name]
    M = copy_lib_with_prefix(lib_m, out, "M")[cell_m.name]
    R = copy_lib_with_prefix(lib_r, out, "R")[cell_r.name]
    R1 = copy_lib_with_prefix(lib_r1, out, "R1")[cell_r1.name]

    # --- GATE STRAP en bloques (POLY) ---
    if config.gate_strap:
        for c in (L, M, R, R1):
            add_gate_strap_poly(
                c,
                gate=config.gate,
                active=config.active,
                y_clear=config.strap_y_clear,
                min_h=config.strap_min_h,
            )

    l0x, l0y, *_ = bbox_wh(L)
    m0x, m0y, *_ = bbox_wh(M)
    r0x, r0y, *_ = bbox_wh(R)
    r10x, r10y, *_ = bbox_wh(R1)

    top = gdstk.Cell(f"NMOSHV_PWR_M{config.m_total}_NO_NOTCH")
    out.add(top)

    # --- place rows (todas iguales) ---
    y = 0.0
    for _ in range(plan.n_rows):
        x = 0.0

        # LEFT
        top.add(gdstk.Reference(L, origin=(x - l0x, y - l0y)))
        x += sizes.w_left + extra_x

        # MID chain
        for _k in range(plan.n_mid):
            top.add(gdstk.Reference(M, origin=(x - m0x, y - m0y)))
            x += sizes.w_mid + extra_x

        # RIGHT end (misma opción para todas las filas)
        if plan.use_right1:
            top.add(gdstk.Reference(R1, origin=(x - r10x, y - r10y)))
        else:
            top.add(gdstk.Reference(R, origin=(x - r0x, y - r0y)))

        y += sizes.h_row + extra_y

    # --- Rail vertical en TOP para unir filas ---
    if config.gate_strap:
        add_vertical_gate_rail_top(top, total_h=plan.height, gate=config.gate, rail_w=config.rail_w)

    # --- merge ThickGateOx (optional) ---
    if config.thickox is not None:
        log.info("[INFO] Flatten TOP for ThickGateOx merge (%s) ...", config.thickox)
        top.flatten(True)
        merge_layer_geoms(top, config.thickox.layer, config.thickox.datatype)
        log.info("[INFO] ThickGateOx merge done.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.write_gds(output_path)
    log.info("[DONE] wrote: %s", output_path)
    return plan
