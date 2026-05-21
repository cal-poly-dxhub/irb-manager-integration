import argparse
import json
import os
import sys

import boto3
from form_parser import process_pdf_async


def main():
    parser = argparse.ArgumentParser(
        description="Run async AWS Textract analysis on a multi-page document."
    )
    parser.add_argument("input", help="Path to the input document (PDF or image)")
    parser.add_argument("output", help="Path to write the Textract JSON output")
    parser.add_argument("--bucket", required=True, help="S3 bucket for uploading the document")
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between status checks (default: 5)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    s3_client = boto3.client("s3")
    textract_client = boto3.client("textract")

    try:
        blocks = process_pdf_async(
            s3_client,
            textract_client,
            args.input,
            args.bucket,
            poll_interval=args.poll_interval,
            verbose=True,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(blocks, f, indent=2, default=str)

    print(f"Wrote {len(blocks)} blocks to {args.output}")


if __name__ == "__main__":
    main()
