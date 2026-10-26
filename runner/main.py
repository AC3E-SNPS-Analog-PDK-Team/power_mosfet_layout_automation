import argparse
import logging
from pathlib import Path

from scripts.generate_power_mosfet import LayoutConfig, generate_layout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Power MOSFET Layout Generator"
    )

    parser.add_argument("--m_total", type=int, required=True)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--extra_x", type=float, default=0.0)
    parser.add_argument("--extra_y", type=float, default=0.0)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    base_dir = Path(__file__).resolve().parent.parent
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if args.out:
        output_path = output_dir / args.out
    else:
        output_path = output_dir / f"mosfet_M{args.m_total}.gds"

    config = LayoutConfig(
        m_total=args.m_total,
        extra_space_x=args.extra_x,
        extra_space_y=args.extra_y,
    )
    generate_layout(config, output_path)


if __name__ == "__main__":
    main()
