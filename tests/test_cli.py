"""Tests de la interfaz de línea de comandos."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from runner.main import layer_spec, main
from scripts.generate_power_mosfet import LayerSpec


def test_dry_run_prints_plan_and_writes_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "x.gds"
    assert main(["-m", "100", "-n", "-o", str(out)]) == 0
    assert "n_rows    : 4" in capsys.readouterr().out
    assert not out.exists()


def test_no_solution_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-m", "2", "-n"]) == 1
    assert "error:" in capsys.readouterr().err


def test_missing_blocks_exits_1(tmp_path: Path) -> None:
    assert main(["-m", "10", "-n", "--blocks-dir", str(tmp_path)]) == 1


@pytest.mark.parametrize("argv", [["-m", "0"], ["-m", "abc"], ["-m", "5", "--extra-x", "-1"]])
def test_invalid_arguments_exit_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2


def test_legacy_flag_names_still_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--m_total", "100", "--extra_x", "1", "--extra_y", "2", "-n"]) == 0
    assert "W=43.630um, H=49.360um" in capsys.readouterr().out


@pytest.mark.parametrize(("text", "spec"), [("44", LayerSpec(44, 0)), ("44/0", LayerSpec(44, 0)), ("5/2", LayerSpec(5, 2))])
def test_layer_spec_parses(text: str, spec: LayerSpec) -> None:
    assert layer_spec(text) == spec


@pytest.mark.parametrize("text", ["", "abc", "5/x", "-1/0"])
def test_layer_spec_rejects(text: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        layer_spec(text)
