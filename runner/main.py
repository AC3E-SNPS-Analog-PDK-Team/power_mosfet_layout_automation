"""Command line interface for the power MOSFET layout generator."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from scripts.generate_power_mosfet import (
    BLOCKS_DIR,
    OUTPUT_DIR,
    LayerSpec,
    LayoutConfig,
    LayoutPlan,
    NoSolutionError,
    compute_plan,
    generate_layout,
)

_DEFAULTS = LayoutConfig(m_total=1)


def positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {value!r}") from None
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def non_negative_float(value: str) -> float:
    try:
        x = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {value!r}") from None
    if x < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {x}")
    return x


def layer_spec(value: str) -> LayerSpec:
    """Parse 'LAYER' or 'LAYER/DATATYPE' (e.g. '65' or '65/20')."""
    layer_s, _, dt_s = value.partition("/")
    try:
        layer = int(layer_s)
        datatype = int(dt_s) if dt_s else 0
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid layer spec {value!r}, expected LAYER or LAYER/DATATYPE"
        ) from None
    if layer < 0 or datatype < 0:
        raise argparse.ArgumentTypeError(f"layer/datatype must be >= 0, got {value!r}")
    return LayerSpec(layer, datatype)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m runner.main",
        description=(
            "Generate a rectangular NMOS HV power MOSFET layout (GDS) from the "
            "LEFT/MID/RIGHT/RIGHT1 building blocks."
        ),
    )

    parser.add_argument(
        "-m", "--m-total", "--m_total",
        dest="m_total", type=positive_int, required=True,
        help="total number of transistors (fingers) in the array",
    )
    parser.add_argument(
        "-o", "--out",
        type=Path, default=None,
        help=f"output GDS path (default: {OUTPUT_DIR}/mosfet_M<m_total>.gds)",
    )
    parser.add_argument(
        "--blocks-dir",
        type=Path, default=BLOCKS_DIR,
        help="directory containing the building-block GDS files (default: %(default)s)",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="only compute and print the row plan, do not write a GDS",
    )

    spacing = parser.add_argument_group("spacing")
    spacing.add_argument(
        "--extra-x", "--extra_x",
        dest="extra_x", type=non_negative_float, default=_DEFAULTS.extra_space_x,
        help="extra horizontal space between blocks (um) (default: %(default)s)",
    )
    spacing.add_argument(
        "--extra-y", "--extra_y",
        dest="extra_y", type=non_negative_float, default=_DEFAULTS.extra_space_y,
        help="extra vertical space between rows (um) (default: %(default)s)",
    )

    gate = parser.add_argument_group("gate strap")
    gate.add_argument(
        "--no-gate-strap",
        dest="gate_strap", action="store_false",
        help="do not add the POLY gate strap to blocks nor the vertical gate rail",
    )
    gate.add_argument(
        "--gate-layer",
        type=layer_spec, default=_DEFAULTS.gate, metavar="L[/D]",
        help="gate POLY layer/datatype (default: %(default)s)",
    )
    gate.add_argument(
        "--active-layer",
        type=layer_spec, default=_DEFAULTS.active, metavar="L[/D]",
        help="active layer/datatype (default: %(default)s)",
    )
    gate.add_argument(
        "--strap-clearance",
        type=non_negative_float, default=_DEFAULTS.strap_y_clear,
        help="vertical clearance between strap and active / gate edge (um) (default: %(default)s)",
    )
    gate.add_argument(
        "--strap-min-height",
        type=non_negative_float, default=_DEFAULTS.strap_min_h,
        help="minimum strap height (um) (default: %(default)s)",
    )
    gate.add_argument(
        "--rail-width",
        type=non_negative_float, default=_DEFAULTS.rail_w,
        help="width of the vertical gate rail on the top cell (um) (default: %(default)s)",
    )

    parser.add_argument(
        "--thickox-layer",
        type=layer_spec, default=None, metavar="L[/D]",
        help="flatten the top cell and merge ThickGateOx shapes on this layer "
        "(disabled if not given)",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="show detailed progress")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="only show errors")

    return parser


def print_plan(plan: LayoutPlan) -> None:
    print("Plan (no RIGHT/RIGHT1 mixing):")
    print(f"  right end : {'RIGHT1 (1T)' if plan.use_right1 else 'RIGHT (2T)'}")
    print(f"  n_mid     : {plan.n_mid}")
    print(f"  trans/row : {plan.trans_per_row}")
    print(f"  n_rows    : {plan.n_rows}")
    print(f"  size      : W={plan.width:.3f}um, H={plan.height:.3f}um, squareness={plan.squareness:.4f}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.WARNING
    logging.basicConfig(level=level, format="%(message)s")
    if args.verbose:
        logging.getLogger("scripts").setLevel(logging.INFO)

    config = LayoutConfig(
        m_total=args.m_total,
        extra_space_x=args.extra_x,
        extra_space_y=args.extra_y,
        gate_strap=args.gate_strap,
        gate=args.gate_layer,
        active=args.active_layer,
        strap_y_clear=args.strap_clearance,
        strap_min_h=args.strap_min_height,
        rail_w=args.rail_width,
        thickox=args.thickox_layer,
    )
    output_path: Path = args.out if args.out is not None else OUTPUT_DIR / f"mosfet_M{args.m_total}.gds"

    try:
        if args.dry_run:
            plan = compute_plan(config, args.blocks_dir)
        else:
            plan = generate_layout(config, output_path, args.blocks_dir)
    except (FileNotFoundError, NoSolutionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: could not write {output_path}: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print_plan(plan)
        if not args.dry_run:
            print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
