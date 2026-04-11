# -*- coding: utf-8 -*-
"""
segunda_gen.py  (Python puro, SIN pya) — requiere: pip install gdstk

Convención (correcta):
- Extremo IZQUIERDO : bloque_izquierdo (2 trans)
- Centro repetible  : bloque_medio     (2 trans)
- Extremo DERECHO   : bloque_derecho   (2 trans)
- Extremo DERECHO (impar): bloque_derecho_1_transistor (1 trans)

CONDICIÓN NUEVA (para evitar "escalones/notches"):
- NO se permite mezclar en el mismo layout filas que terminen con RIGHT (2 trans) y otras con RIGHT1 (1 trans).
- El layout entero elige UNA opción:
    A) todas las filas terminan con RIGHT
    B) todas las filas terminan con RIGHT1
- Además, todas las filas son idénticas: mismo n_mid.
=> El contorno queda rectangular y continuo, aunque no sea un cuadrado perfecto.
=> Se elige la solución más "cuadrada posible" (W/H cercano a 1) entre las que cumplan EXACTAMENTE M_TOTAL.

Merge opcional (si lo deseas) para ThickGateOx.drawing:
- GDS no guarda nombres de capa: debes definir THICKOX_LAYER y THICKOX_DATATYPE.
- Incluye polygons+paths y hace flatten del TOP antes de merge.
"""

import os
import math
import gdstk

# ----------------------------
# CONFIGURA ESTO
# ----------------------------
BASE_DIR = "/foss/designs/power_mosfet/dos"

GDS_LEFT   = os.path.join(BASE_DIR, "bloque_izquierdo.gds")
GDS_MID    = os.path.join(BASE_DIR, "bloque_medio.gds")
GDS_RIGHT  = os.path.join(BASE_DIR, "bloque_derecho.gds")
GDS_RIGHT1 = os.path.join(BASE_DIR, "bloque_derecho_1_transistor.gds")

GDS_OUT    = os.path.join(BASE_DIR, f"powermos_M200_rowblocks_RECT_NO_NOTCH_busvia7.gds")

M_TOTAL = 200

# Espacio extra (um)
EXTRA_SPACE_X = 0.0
EXTRA_SPACE_Y = 0.0

# ---- MERGE ThickGateOx.drawing (opcional) ----
DO_THICKOX_MERGE = False
THICKOX_LAYER = None      # ej: 65  (pon el real)
THICKOX_DATATYPE = None   # ej: 0   (pon el real)
# ----------------------------


def must_exist(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo: {path}")


def load_main_cell(gds_path: str):
    """Lee un GDS y retorna (lib, main_cell) donde main_cell es la celda con bbox más grande."""
    lib = gdstk.read_gds(gds_path)
    best = None
    best_area = -1.0
    for c in lib.cells:
        bb = c.bounding_box()
        if bb is None:
            continue
        (xmin, ymin), (xmax, ymax) = bb
        w = xmax - xmin
        h = ymax - ymin
        area = w * h
        if area > best_area:
            best_area = area
            best = c
    if best is None:
        raise RuntimeError(f"No encontré celdas con geometría en: {gds_path}")
    return lib, best


def bbox_wh(cell: gdstk.Cell):
    bb = cell.bounding_box()
    if bb is None:
        raise RuntimeError(f"Celda {cell.name} no tiene bounding box.")
    (xmin, ymin), (xmax, ymax) = bb
    return xmin, ymin, xmax, ymax, (xmax - xmin), (ymax - ymin)


def copy_lib_with_prefix(lib_in: gdstk.Library, out_lib: gdstk.Library, prefix: str):
    """
    Copia todas las celdas de lib_in a out_lib renombrándolas con prefijo
    para evitar colisiones entre los 4 GDS.
    """
    mapping = {}
    for c in lib_in.cells:
        new_name = f"{prefix}__{c.name}"
        new_cell = c.copy(new_name)
        mapping[c.name] = new_cell
        out_lib.add(new_cell)
    return mapping


def row_width(n_mid: int, use_right1: bool,
              w_left: float, w_mid: float, w_right: float, w_right1: float,
              extra_x: float):
    """
    Ancho físico de una fila:
      LEFT + MID*n_mid + (RIGHT o RIGHT1)
    """
    w = w_left + n_mid * w_mid + (w_right1 if use_right1 else w_right)
    blocks = 2 + n_mid  # left + mids + right/right1
    if blocks > 1:
        w += (blocks - 1) * extra_x
    return w


def trans_per_row(n_mid: int, use_right1: bool):
    """
    Conteo de transistores por fila:
      LEFT=2, MID=2, RIGHT=2, RIGHT1=1
    """
    return 2 + 2 * n_mid + (1 if use_right1 else 2)


def merge_layer_geoms(cell: gdstk.Cell, layer: int, datatype: int, precision: float = 1e-6):
    """
    Merge (OR) de geometría en (layer,datatype) dentro de 'cell', incluyendo polygons y paths.
    Requiere flatten del cell para que la geometría de subceldas quede en esta celda.
    """
    target = []
    keep_polys = []
    keep_paths = []

    for p in cell.polygons:
        if p.layer == layer and p.datatype == datatype:
            target.append(p)
        else:
            keep_polys.append(p)

    for path in cell.paths:
        if path.layer == layer and path.datatype == datatype:
            target.extend(path.to_polygons())
        else:
            keep_paths.append(path)

    print(f"[MERGE] Found {len(target)} shapes on layer={layer}, datatype={datatype}")

    if not target:
        cell.polygons = keep_polys
        cell.paths = keep_paths
        return

    merged = gdstk.boolean(target, None, "or", precision=precision) or []
    cell.polygons = keep_polys + merged
    cell.paths = keep_paths
    print(f"[MERGE] After OR -> {len(merged)} merged polygons")

def _max_y_of_layer(cell: gdstk.Cell, layer: int, datatype: int):
    ys = []
    for p in cell.polygons:
        if p.layer == layer and p.datatype == datatype:
            bb = p.bounding_box()
            if bb is not None:
                ys.append(bb[1][1])  # ymax
    return max(ys) if ys else None


def _merge_intervals(ints):
    ints = sorted(ints)
    merged = []
    for a, b in ints:
        if not merged or a > merged[-1][1]:
            merged.append([a, b])
        else:
            merged[-1][1] = max(merged[-1][1], b)
    return [(a, b) for a, b in merged]

def pick_y_clear_band(cell, layer, dt, margin=0.05, prefer_frac=0.6):
    bb = cell.bounding_box()
    (x0, y0), (x1, y1) = bb

    blocked = []
    for p in cell.polygons:
        if p.layer == layer and p.datatype == dt:
            bbp = p.bounding_box()
            if bbp is None:
                continue
            (_, by0), (_, by1) = bbp
            blocked.append((max(y0, by0 - margin), min(y1, by1 + margin)))

    blocked = [(a, b) for a, b in blocked if a < b]
    blocked = _merge_intervals(blocked)

    # gaps = complementos
    gaps = []
    cur = y0
    for a, b in blocked:
        if cur < a:
            gaps.append((cur, a))
        cur = max(cur, b)
    if cur < y1:
        gaps.append((cur, y1))

    target = y0 + prefer_frac * (y1 - y0)
    for a, b in gaps:
        if a <= target <= b:
            return 0.5 * (a + b)

    if gaps:
        a, b = max(gaps, key=lambda g: g[1] - g[0])
        return 0.5 * (a + b)

    return target  # fallback

def add_gate_strap_poly(
    cell: gdstk.Cell,
    gate_layer=5, gate_dt=0,
    active_layer=1, active_dt=0,
    y_clear=10.0,   # “margen” arriba del active y abajo del borde del gate
    min_h=40.0      # alto mínimo del strap (en tus unidades del GDS)
):
    """
    Agrega un strap HORIZONTAL en POLY (misma capa del gate) dentro del bbox del cell.
    - Une gates internas
    - Extiende a bordes del cell para conexión por abutment
    """
    bb = cell.bounding_box()
    if bb is None:
        raise RuntimeError(f"{cell.name}: sin bounding box.")
    (x0, y0), (x1, y1) = bb

    gate_top = _max_y_of_layer(cell, gate_layer, gate_dt)
    if gate_top is None:
        print(f"[GATE] {cell.name}: no encontré POLY gate en {gate_layer}/{gate_dt}.")
        return

    active_top = _max_y_of_layer(cell, active_layer, active_dt)
    # Si no hay active, igual hacemos el strap cerca del top del gate
    if active_top is None:
        active_top = gate_top - (min_h + 2*y_clear)

    # Ventana segura: entre active_top y gate_top
    y_lo = active_top + y_clear
    y_hi = gate_top   - y_clear

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
        print(f"[GATE] {cell.name}: no pude ubicar strap (revisa y_clear/min_h).")
        return

    # Strap: de borde a borde en X, en la capa de gate poly
    cell.add(gdstk.rectangle((x0, y_lo), (x1, y_hi), layer=gate_layer, datatype=gate_dt))
    print(f"[GATE] Strap POLY agregado en {cell.name}: y=[{y_lo},{y_hi}] x=[{x0},{x1}]")

def add_vertical_gate_rail_top(
    top: gdstk.Cell,
    total_w: float,
    total_h: float,
    gate_layer=5, gate_dt=0,
    rail_w=60.0,  # ancho del rail en X
):
    """
    Rail vertical en el TOP (POLY) para unir todas las filas.
    Lo pongo en el borde izquierdo (x=0..rail_w).
    """
    top.add(gdstk.rectangle((0.0, 0.0), (rail_w, total_h), layer=gate_layer, datatype=gate_dt))
    print(f"[GATE] Rail vertical TOP: x=[0,{rail_w}] y=[0,{total_h}]")

def _metal1_columns(cell: gdstk.Cell, layer=8, dt=0, min_w=1e-6):
    """
    Devuelve columnas verticales de Metal1 (8/0) como bboxes (x0,x1,y0,y1),
    deduplicadas por (x0,x1).
    """
    cols = {}
    for p in cell.polygons:
        if p.layer == layer and p.datatype == dt:
            bb = p.bounding_box()
            if bb is None:
                continue
            (x0, y0), (x1, y1) = bb
            if (x1 - x0) <= min_w:
                continue
            key = (round(x0, 6), round(x1, 6))
            if key in cols:
                ox0, ox1, oy0, oy1 = cols[key]
                cols[key] = (ox0, ox1, min(oy0, y0), max(oy1, y1))
            else:
                cols[key] = (x0, x1, y0, y1)

    out = list(cols.values())
    out.sort(key=lambda c: 0.5 * (c[0] + c[1]))  # por x-center
    return out

def add_drain_bus_m2_with_via1(
    cell: gdstk.Cell,
    drain_parity: int = 1,
    met1_layer=8, met1_dt=0,
    met2_layer=10, met2_dt=0,
    via1_layer=19, via1_dt=0,
    bus_h=0.20,
    via_size=0.16,
    bus_only=False
):
    bb = cell.bounding_box()
    if bb is None: return
    (cx0, cy0), (cx1, cy1) = bb

    cols = _metal1_columns(cell, met1_layer, met1_dt)

    # Filtra rails muy anchos (se queda solo con los fingers verticales)
    widths = [(c[1]-c[0]) for c in cols]
    if widths:
        w_med = sorted(widths)[len(widths)//2]
        cols = [c for c in cols if (c[1]-c[0]) <= 1.5*w_med]

    if len(cols) < 2:
        print(f"[DRAIN] {cell.name}: no hay suficientes columnas M1 filtradas.")
        return

    # LA MAGIA: Selecciona estrictamente por índice (el centro en celdas de 3, el derecho en celdas de 2)
    drain_cols = cols[drain_parity::2]

    print(f"[DRAIN] {cell.name}: cols={len(cols)} drain_cols={len(drain_cols)}")

    if not drain_cols:
        return

    # Elige franja Y limpia para el bus/vías
    y_mid = pick_y_clear_band(cell, via1_layer, via1_dt, margin=0.08, prefer_frac=0.6)
    y_lo = max(cy0, y_mid - bus_h/2)
    y_hi = min(cy1, y_mid + bus_h/2)

    # Dibuja bus metal2
    cell.add(gdstk.rectangle((cx0, y_lo), (cx1, y_hi), layer=met2_layer, datatype=met2_dt))

    if bus_only: return

    # Vías SOLO sobre la columna drain seleccionada (exactamente 1 por celda)
    for (x0, x1, _, _) in drain_cols:
        xc = 0.5 * (x0 + x1)
        
        w = via_size

        if w <= 0: continue

        vx0 = xc - w / 2
        vx1 = xc + w / 2
        vy0 = y_mid - via_size / 2
        vy1 = y_mid + via_size / 2

        cell.add(gdstk.rectangle((vx0, vy0), (vx1, vy1), layer=via1_layer, datatype=via1_dt))

    print(f"[DRAIN] {cell.name}: Metal2 bus + Via1 sobre {len(drain_cols)} columnas.")

def add_vertical_drain_rail_top(
    top: gdstk.Cell,
    total_w: float,
    total_h: float,
    drain_layer: int = 10,
    drain_dt: int = 0,
    rail_w: float = 0.30,
    side: str = "right",  # "right" o "left"
):
    if side == "right":
        x0 = total_w - rail_w
    else:
        x0 = 0.0

    top.add(gdstk.rectangle((x0, 0.0), (x0 + rail_w, total_h), layer=drain_layer, datatype=drain_dt))
    print(f"[DRAIN] Rail vertical TOP en {drain_layer}/{drain_dt}: x=[{x0},{x0+rail_w}] y=[0,{total_h}]")

def main():
    # --- chequeo rutas ---
    for p in [GDS_LEFT, GDS_MID, GDS_RIGHT, GDS_RIGHT1]:
        must_exist(p)

    print("[INFO] Inputs:")
    print("  LEFT  :", GDS_LEFT)
    print("  MID   :", GDS_MID)
    print("  RIGHT :", GDS_RIGHT)
    print("  RIGHT1:", GDS_RIGHT1)

    # --- load blocks ---
    lib_l, cell_l = load_main_cell(GDS_LEFT)
    lib_m, cell_m = load_main_cell(GDS_MID)
    lib_r, cell_r = load_main_cell(GDS_RIGHT)
    lib_r1, cell_r1 = load_main_cell(GDS_RIGHT1)

    xl0, yl0, xl1, yl1, w_l, h_l = bbox_wh(cell_l)
    xm0, ym0, xm1, ym1, w_m, h_m = bbox_wh(cell_m)
    xr0, yr0, xr1, yr1, w_r, h_r = bbox_wh(cell_r)
    x10, y10, x11, y11, w_r1, h_r1 = bbox_wh(cell_r1)

    h_row = max(h_l, h_m, h_r, h_r1)

    print("[INFO] Block sizes (um):")
    print(f"  LEFT  : W={w_l:.3f}, H={h_l:.3f}")
    print(f"  MID   : W={w_m:.3f}, H={h_m:.3f}")
    print(f"  RIGHT : W={w_r:.3f}, H={h_r:.3f}")
    print(f"  RIGHT1: W={w_r1:.3f}, H={h_r1:.3f}")
    print(f"[INFO] Row height used (um): {h_row:.3f}")

    # ---------------------------------------------------------
    # BÚSQUEDA SIN NOTCH:
    # - elegir UNA sola terminación (RIGHT o RIGHT1) para TODAS las filas
    # - filas idénticas (mismo n_mid)
    # - M_TOTAL debe ser divisible por trans_per_row
    # - elegir el layout más "cuadrado" posible
    # ---------------------------------------------------------
    best = None

    for use_right1 in (False, True):
        for n_mid in range(0, M_TOTAL // 2 + 1):
            t_row = trans_per_row(n_mid, use_right1)
            if t_row <= 0:
                continue

            if M_TOTAL % t_row != 0:
                continue  # debe cerrar exacto

            n_rows = M_TOTAL // t_row
            if n_rows <= 0:
                continue

            W = row_width(n_mid, use_right1, w_l, w_m, w_r, w_r1, EXTRA_SPACE_X)
            H = n_rows * h_row + max(0, n_rows - 1) * EXTRA_SPACE_Y
            if W <= 0 or H <= 0:
                continue

            squareness = abs((W / H) - 1.0)
            # (leve) penalización por muchísimas filas
            score = squareness + 0.0005 * n_rows

            cand = (score, squareness, n_rows, n_mid, use_right1, W, H, t_row)
            if best is None or cand < best:
                best = cand

    if best is None:
        raise RuntimeError(
            f"No hay solución SIN notch para M_TOTAL={M_TOTAL} usando filas idénticas.\n"
            "Esto es esperable si M_TOTAL no es divisible por ninguna fila válida.\n"
            "Opciones: cambia M_TOTAL o agrega fillers/dummies."
        )

    _, squareness, n_rows, n_mid, use_right1, W, H, t_row = best

    print("[INFO] Plan elegido (NO mezcla RIGHT/RIGHT1):")
    print(f"  right end : {'RIGHT1 (1T)' if use_right1 else 'RIGHT (2T)'}")
    print(f"  n_mid     : {n_mid}")
    print(f"  trans/row : {t_row}")
    print(f"  n_rows    : {n_rows}")
    print(f"  Final size: W={W:.3f}um, H={H:.3f}um, squareness={squareness:.4f}")

    # --- build output lib ---
    out = gdstk.Library()

    map_l  = copy_lib_with_prefix(lib_l,  out, "L")
    map_m  = copy_lib_with_prefix(lib_m,  out, "M")
    map_r  = copy_lib_with_prefix(lib_r,  out, "R")
    map_r1 = copy_lib_with_prefix(lib_r1, out, "R1")

    L  = map_l[cell_l.name]
    M  = map_m[cell_m.name]
    R  = map_r[cell_r.name]
    R1 = map_r1[cell_r1.name]


    # --- GATE STRAP en bloques (POLY) ---
    for c in (L, M, R, R1):
        for dt in (0, 2):  # 5/0 = drawing, 5/2 = pin
            add_gate_strap_poly(
                c,
                gate_layer=5, gate_dt=dt,
                active_layer=1, active_dt=0,
                y_clear=0.09,
                min_h=0.20
            )


    # --- DRAIN bus en Metal2 + Via1 (en bloques) ---
    for c in (L, M, R, R1):
        add_drain_bus_m2_with_via1(
            c,
            drain_parity=1,
            bus_only=False,
            bus_h=0.20,
            via_size=0.19
        )

    l0x, l0y, _, _, _, _ = bbox_wh(L)
    m0x, m0y, _, _, _, _ = bbox_wh(M)
    r0x, r0y, _, _, _, _ = bbox_wh(R)
    r10x, r10y, _, _, _, _ = bbox_wh(R1)

    top = gdstk.Cell("DCDCBuck_vto1p1")
    out.add(top)

    # --- place rows (todas iguales) ---
    y = 0.0
    for _ in range(n_rows):
        x = 0.0

        # LEFT
        top.add(gdstk.Reference(L, origin=(x - l0x, y - l0y)))
        x += w_l + EXTRA_SPACE_X

        # MID chain
        for _k in range(n_mid):
            top.add(gdstk.Reference(M, origin=(x - m0x, y - m0y)))
            x += w_m + EXTRA_SPACE_X

        # RIGHT end (misma opción para todas las filas)
        if use_right1:
            top.add(gdstk.Reference(R1, origin=(x - r10x, y - r10y)))
        else:
            top.add(gdstk.Reference(R, origin=(x - r0x, y - r0y)))

        y += h_row + EXTRA_SPACE_Y

    # --- Rail vertical en TOP para unir filas ---
    TOTAL_H = n_rows * h_row + max(0, n_rows - 1) * EXTRA_SPACE_Y
    add_vertical_gate_rail_top(
        top,
        total_w=W,
        total_h=TOTAL_H,
        gate_layer=5, gate_dt=0,
        rail_w=0.18 #ANTES 0.25
    )

    add_vertical_gate_rail_top(
        top,
        total_w=W,
        total_h=TOTAL_H,
        gate_layer=5, gate_dt=2,
        rail_w=0.18
    )

    # ✅ Drain rail en Metal2
    add_vertical_drain_rail_top(top, total_w=W, total_h=TOTAL_H, drain_layer=10, drain_dt=0, rail_w=0.30, side="right")
    
    # --- merge ThickGateOx (optional) ---
    if DO_THICKOX_MERGE:
        if THICKOX_LAYER is None or THICKOX_DATATYPE is None:
            print("[INFO] ThickGateOx merge skipped (define THICKOX_LAYER y THICKOX_DATATYPE).")
        else:
            print(f"[INFO] Flatten TOP for ThickGateOx merge (layer={THICKOX_LAYER}, datatype={THICKOX_DATATYPE}) ...")
            top.flatten(True)
            merge_layer_geoms(top, THICKOX_LAYER, THICKOX_DATATYPE)
            print("[INFO] ThickGateOx merge done.")

    out.write_gds(GDS_OUT)
    print(f"[DONE] wrote: {GDS_OUT}")


if __name__ == "__main__":
    main()
