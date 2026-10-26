"""Tests de caracterización: la geometría generada debe coincidir con la del código previo al refactor.

Los golden (tests/golden/signatures.json) se generaron desde el commit 521d13e
con `python tests/_signature.py output/mosfet_M<N>.gds ...`. Si un cambio de
geometría es intencional, regenerarlos y explicar el cambio en el commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from _signature import gds_signature

REPO = Path(__file__).resolve().parent.parent
GOLDEN: dict[str, dict[str, Any]] = json.loads((REPO / "tests/golden/signatures.json").read_text())


@pytest.mark.parametrize("m_total", [3, 4, 23, 100, 5000])
def test_cli_output_matches_golden(m_total: int, tmp_path: Path) -> None:
    out = tmp_path / f"mosfet_M{m_total}.gds"
    subprocess.run(
        # Flags legacy a propósito: el test también corre sobre el código previo al refactor
        # y verifica que la CLI mantenga compatibilidad hacia atrás.
        [sys.executable, "-m", "runner.main", "--m_total", str(m_total), "--out", str(out)],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    expected = GOLDEN[out.name]
    actual = gds_signature(out)
    # top_layers primero: si difiere, el mensaje dice qué capa cambió.
    assert actual["top_layers"] == expected["top_layers"]
    assert actual["cells"] == expected["cells"]
    assert actual["sha256"] == expected["sha256"]
