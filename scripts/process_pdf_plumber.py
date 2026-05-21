import argparse
import json
import sys

import pdfplumber


def extract_fields(input_path: str) -> list[dict]:
    fields = []

    with pdfplumber.open(input_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                }
            )

            for table in tables:
                for row in table:
                    if not row or not any((c or "").strip() for c in row):
                        continue

                    cells = [(c or "").strip() for c in row]
                    non_empty = [c for c in cells if c]

                    if len(non_empty) == 0:
                        continue
                    elif len(non_empty) == 1:
                        fields.append({
                            "instructions": non_empty[0],
                            "response": "",
                            "page": page_num,
                        })
                    else:
                        fields.append({
                            "instructions": non_empty[0],
                            "response": "\n".join(non_empty[1:]),
                            "page": page_num,
                        })

    return fields


def main():
    parser = argparse.ArgumentParser(
        description="Extract form fields from a PDF using pdfplumber layout parsing."
    )
    parser.add_argument("input", help="Path to the input PDF")
    parser.add_argument("output", help="Path to write the JSON output")
    args = parser.parse_args()

    try:
        fields = extract_fields(args.input)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(fields, f, indent=2)

    print(f"Extracted {len(fields)} fields to {args.output}")


if __name__ == "__main__":
    main()
