import argparse
from pathlib import Path

from scripts.generate_power_mosfet import generate_layout


def main():
    parser = argparse.ArgumentParser(
        description="Power MOSFET Layout Generator"
    )

    parser.add_argument("--m_total", type=int, required=True)
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--extra_x", type=float, default=0.0)
    parser.add_argument("--extra_y", type=float, default=0.0)

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if args.out:
        output_path = output_dir / args.out
    else:
        output_path = output_dir / f"mosfet_M{args.m_total}.gds"

    generate_layout(
        m_total=args.m_total,
        output_path=output_path,
        extra_space_x=args.extra_x,
        extra_space_y=args.extra_y,
    )


if __name__ == "__main__":
    main()
