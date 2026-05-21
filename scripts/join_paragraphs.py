import argparse
import json
import sys

from form_parser import join_paragraphs


def main():
    parser = argparse.ArgumentParser(
        description="Join Textract blocks into paragraphs and tables in document order."
    )
    parser.add_argument("input", help="Path to the Textract JSON output")
    parser.add_argument("output", help="Path to write the result JSON")
    parser.add_argument(
        "--gap-factor", type=float, default=1.5,
        help="Max vertical gap as a multiple of line height (default: 1.5)",
    )
    args = parser.parse_args()

    try:
        with open(args.input) as f:
            blocks = json.load(f)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    elements = join_paragraphs(blocks, args.gap_factor)

    with open(args.output, "w") as f:
        json.dump(elements, f, indent=2)

    n_para = sum(1 for e in elements if e["type"] == "paragraph")
    n_table = sum(1 for e in elements if e["type"] == "table")
    print(f"Wrote {n_para} paragraphs and {n_table} tables → {args.output}")


if __name__ == "__main__":
    main()
