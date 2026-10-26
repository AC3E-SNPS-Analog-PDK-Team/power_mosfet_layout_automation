"""Tests unitarios de plan_layout (función pura, no requiere GDS)."""

from __future__ import annotations

import pytest

from scripts.generate_power_mosfet import BlockSizes, NoSolutionError, plan_layout, trans_per_row

# Dimensiones reales de los bloques en blocks/ (um).
SIZES = BlockSizes(w_left=3.15, w_mid=2.42, w_right=2.69, w_right1=1.86, h_row=10.84)


@pytest.mark.parametrize("m_total", [1, 2])
def test_below_minimum_row_has_no_solution(m_total: int) -> None:
    with pytest.raises(NoSolutionError):
        plan_layout(m_total, SIZES)


@pytest.mark.parametrize("m_total", range(3, 301))
def test_plan_places_exactly_m_total(m_total: int) -> None:
    plan = plan_layout(m_total, SIZES)
    assert plan.trans_per_row == trans_per_row(plan.n_mid, plan.use_right1)
    assert plan.n_rows * plan.trans_per_row == m_total


def test_odd_row_uses_right1_and_even_uses_right() -> None:
    assert plan_layout(3, SIZES).use_right1 is True
    assert plan_layout(4, SIZES).use_right1 is False


def test_known_plan_m100() -> None:
    plan = plan_layout(100, SIZES)
    assert (plan.n_rows, plan.n_mid, plan.use_right1) == (4, 11, True)


def test_extra_spacing_grows_dimensions() -> None:
    base = plan_layout(100, SIZES)
    spaced = plan_layout(100, SIZES, extra_x=1.0, extra_y=2.0)
    # mismo plan de filas -> diferencia exacta por los huecos entre bloques y filas
    assert (spaced.n_rows, spaced.n_mid) == (base.n_rows, base.n_mid)
    assert spaced.width == pytest.approx(base.width + (base.n_mid + 1) * 1.0)
    assert spaced.height == pytest.approx(base.height + (base.n_rows - 1) * 2.0)
