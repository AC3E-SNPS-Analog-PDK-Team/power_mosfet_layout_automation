"""Tests de merge_layer_geoms sobre celdas sintéticas."""

from __future__ import annotations

import gdstk
import pytest

from scripts.generate_power_mosfet import merge_layer_geoms

TOX = (44, 0)


def _layers(cell: gdstk.Cell) -> list[tuple[int, int]]:
    return sorted((p.layer, p.datatype) for p in cell.polygons)


def test_overlapping_shapes_merge_into_one_on_target_layer() -> None:
    cell = gdstk.Cell("t")
    cell.add(
        gdstk.rectangle((0, 0), (2, 1), *TOX),
        gdstk.rectangle((1, 0), (3, 1), *TOX),
        gdstk.rectangle((10, 10), (11, 11), layer=1),
    )
    merge_layer_geoms(cell, *TOX)
    assert _layers(cell) == [(1, 0), TOX]
    merged = [p for p in cell.polygons if (p.layer, p.datatype) == TOX]
    assert merged[0].area() == pytest.approx(3.0)


def test_path_on_target_layer_is_merged_and_other_layers_kept() -> None:
    cell = gdstk.Cell("t")
    cell.add(
        gdstk.rectangle((0, 0), (1, 1), *TOX),
        # path de dos capas: la parte en TOX se fusiona, la parte en 7/0 se conserva
        gdstk.FlexPath([(0.5, 0.5), (3, 0.5)], [0.2, 0.2], [0, 0.5], layer=[TOX[0], 7]),
    )
    merge_layer_geoms(cell, *TOX)
    assert cell.paths == []
    assert _layers(cell) == [(7, 0), TOX]


def test_no_shapes_on_target_layer_is_noop() -> None:
    cell = gdstk.Cell("t")
    cell.add(gdstk.rectangle((0, 0), (1, 1), layer=1))
    merge_layer_geoms(cell, *TOX)
    assert _layers(cell) == [(1, 0)]
