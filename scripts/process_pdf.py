import argparse
import json
import sys

import boto3
from form_parser import process_pdf


def main():
    parser = argparse.ArgumentParser(
        description="Run AWS Textract on a document and write results to a file."
    )
    parser.add_argument("input", help="Path to the input document (PDF or image)")
    parser.add_argument("output", help="Path to write the Textract JSON output")
    args = parser.parse_args()

    client = boto3.client("textract")

    try:
        response = process_pdf(client, args.input)
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except client.exceptions.UnsupportedDocumentException:
        print("Error: unsupported document format", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(response, f, indent=2, default=str)

    print(f"Wrote Textract output to {args.output}")


if __name__ == "__main__":
    main()
