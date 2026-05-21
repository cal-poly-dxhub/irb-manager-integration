#!/usr/bin/env python3
"""Batch process forms through Textract and refinement pipeline.

This script processes a folder of PDF files through the form parsing pipeline,
with options to control which steps are executed. PDF files are automatically
normalized using pikepdf to handle various formats (.pdf, .PDF, .Pdf, etc.).

Usage:
    # Run both Textract and refinement
    python scripts/batch_process_forms.py -i data/input -o data/output

    # Only run Textract (skip refinement)
    python scripts/batch_process_forms.py -i data/input -o data/output --skip-refine

    # Only run refinement (assumes parsed content already exists)
    python scripts/batch_process_forms.py -i data/input -o data/output --skip-textract

    # Custom S3 bucket for large files (>5MB)
    python scripts/batch_process_forms.py -i data/input -o data/output --s3-bucket my-bucket
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

import boto3
import pikepdf

from baml_client import b
from baml_client.types import Form, ParsedContent
from form_parser import (
    collect_results,
    join_paragraphs,
    poll_for_completion,
    process_pdf,
    process_pdf_async,
    start_analysis,
)


def validate_pdf(input_path: Path, verbose: bool = False) -> bool:
    """Validate a PDF file and check for common issues.

    Args:
        input_path: Path to PDF file
        verbose: Print verbose output

    Returns:
        True if PDF appears valid, False otherwise
    """
    try:
        with pikepdf.open(input_path) as pdf:
            # Check if PDF is encrypted
            if pdf.is_encrypted:
                if verbose:
                    print(f"  Warning: PDF is encrypted")
                return False

            # Check if PDF has pages
            if len(pdf.pages) == 0:
                if verbose:
                    print(f"  Warning: PDF has no pages")
                return False

            if verbose:
                print(f"  PDF validation passed: {len(pdf.pages)} page(s)")

            return True

    except Exception as e:
        if verbose:
            print(f"  Warning: PDF validation failed: {e}")
        return False


def normalize_pdf(input_path: Path, output_path: Path, verbose: bool = False) -> None:
    """Normalize a PDF file using pikepdf to handle various PDF formats.

    This performs aggressive normalization including linearization,
    object stream generation, and structure fixes to ensure compatibility
    with AWS Textract.

    Args:
        input_path: Path to input PDF file
        output_path: Path to output normalized PDF file
        verbose: Print verbose output
    """
    if verbose:
        print(f"  Normalizing PDF format...")

    try:
        with pikepdf.open(input_path, allow_overwriting_input=True) as pdf:
            # Remove any encryption
            pdf.remove_unreferenced_resources()

            # Save with aggressive normalization options
            pdf.save(
                output_path,
                linearize=True,  # Optimize for web viewing and processing
                object_stream_mode=pikepdf.ObjectStreamMode.generate,  # Compress object streams
                compress_streams=True,  # Compress all streams
                preserve_pdfa=False,  # Don't preserve PDF/A if it causes issues
                fix_metadata_version=True,  # Fix version mismatches
                recompress_flate=True,  # Recompress with optimal settings
            )

        if verbose:
            print(f"    ✓ Normalized PDF saved to {output_path}")

    except Exception as e:
        if verbose:
            print(f"    Warning: PDF normalization failed: {e}")
            print(f"    Using original PDF...")
        # If normalization fails, just copy the original file
        import shutil
        shutil.copy2(input_path, output_path)


def assign_ids(form_dict: dict) -> dict:
    """Recursively assign UUIDs to all id fields in the form structure.

    Args:
        form_dict: Dictionary representation of Form

    Returns:
        Modified dictionary with UUIDs assigned to all id fields
    """
    if isinstance(form_dict, dict):
        # Assign UUID to id field if it exists and is empty
        if "id" in form_dict and (form_dict["id"] == "" or form_dict["id"] is None):
            form_dict["id"] = str(uuid.uuid4())

        # Recursively process all nested dictionaries
        for key, value in form_dict.items():
            if isinstance(value, dict):
                assign_ids(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        assign_ids(item)

    return form_dict


def run_textract(
    file_path: Path,
    s3_bucket: Optional[str],
    aws_region: str,
    gap_factor: float,
    verbose: bool = False,
) -> ParsedContent:
    """Run Textract on a PDF file and return parsed content.

    Args:
        file_path: Path to PDF file
        s3_bucket: S3 bucket name for large files (>5MB)
        aws_region: AWS region
        gap_factor: Paragraph grouping threshold
        verbose: Print verbose output

    Returns:
        ParsedContent with paragraphs and tables
    """
    if verbose:
        print(f"  Running Textract on {file_path.name}...")

    textract_client = boto3.client("textract", region_name=aws_region)

    # Determine file size
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    if file_size_mb > 5:
        if not s3_bucket:
            raise ValueError(
                f"File {file_path.name} is {file_size_mb:.1f}MB. "
                "S3 bucket required for files >5MB. Use --s3-bucket option."
            )

        if verbose:
            print(f"    Large file ({file_size_mb:.1f}MB), using async processing...")

        s3_client = boto3.client("s3", region_name=aws_region)
        blocks = process_pdf_async(
            s3_client,
            textract_client,
            str(file_path),
            s3_bucket,
            verbose=verbose,
        )
    else:
        if verbose:
            print(f"    Small file ({file_size_mb:.1f}MB), using sync processing...")

        response = process_pdf(textract_client, str(file_path))
        blocks = response.get("Blocks", [])

    # Convert blocks to paragraphs and tables
    elements = join_paragraphs(blocks, gap_factor)

    if verbose:
        print(f"    Extracted {len(elements)} elements")

    return ParsedContent(elements=elements)


def run_refinement(parsed_content: ParsedContent, verbose: bool = False) -> Form:
    """Run refinement on parsed content to create structured form.

    Args:
        parsed_content: ParsedContent with raw paragraphs and tables
        verbose: Print verbose output

    Returns:
        Form with structured and grouped fields
    """
    if verbose:
        print(f"  Refining {len(parsed_content.elements)} elements...")

    refined_form = b.RefineForm(parsed_content)

    if verbose:
        print(f"    Created {len(refined_form.members)} form members")

    # Assign UUIDs to all id fields
    form_dict = refined_form.model_dump()
    form_dict = assign_ids(form_dict)

    return Form(**form_dict)


def process_file(
    input_path: Path,
    output_dir: Path,
    s3_bucket: Optional[str],
    aws_region: str,
    gap_factor: float,
    skip_textract: bool,
    skip_refine: bool,
    verbose: bool = False,
) -> None:
    """Process a single PDF file through the pipeline.

    Args:
        input_path: Path to input PDF file
        output_dir: Directory for output files
        s3_bucket: S3 bucket name for large files
        aws_region: AWS region
        gap_factor: Paragraph grouping threshold
        skip_textract: Skip Textract processing
        skip_refine: Skip refinement step
        verbose: Print verbose output
    """
    base_name = input_path.stem
    normalized_pdf_path = output_dir / f"{base_name}_normalized.pdf"
    parsed_output_path = output_dir / f"{base_name}_parsed.json"
    refined_output_path = output_dir / f"{base_name}_refined.json"

    try:
        # Step 0: Validate and normalize PDF format
        if not skip_textract:
            # Validate PDF first
            if not validate_pdf(input_path, verbose):
                print(f"  ⚠ Warning: PDF validation failed, attempting normalization anyway...")

            # Normalize PDF
            normalize_pdf(input_path, normalized_pdf_path, verbose)
            pdf_to_process = normalized_pdf_path
        else:
            pdf_to_process = input_path

        # Step 1: Textract processing
        if not skip_textract:
            parsed_content = run_textract(
                pdf_to_process, s3_bucket, aws_region, gap_factor, verbose
            )

            # Save parsed content
            with open(parsed_output_path, "w") as f:
                json.dump(parsed_content.model_dump(), f, indent=2)

            if verbose:
                print(f"  ✓ Saved parsed content to {parsed_output_path}")
        else:
            # Load existing parsed content
            if not parsed_output_path.exists():
                print(f"  ✗ Skipping {input_path.name}: No parsed content found at {parsed_output_path}")
                return

            if verbose:
                print(f"  Loading existing parsed content from {parsed_output_path}...")

            with open(parsed_output_path) as f:
                parsed_data = json.load(f)
                parsed_content = ParsedContent(**parsed_data)

        # Step 2: Refinement
        if not skip_refine:
            refined_form = run_refinement(parsed_content, verbose)

            # Save refined form
            with open(refined_output_path, "w") as f:
                json.dump(refined_form.model_dump(), f, indent=2)

            if verbose:
                print(f"  ✓ Saved refined form to {refined_output_path}")

        print(f"✓ Processed {input_path.name}")

    except Exception as e:
        error_msg = str(e)
        print(f"✗ Error processing {input_path.name}: {error_msg}", file=sys.stderr)

        # Provide helpful suggestions based on error type
        if "UnsupportedDocumentException" in error_msg:
            print(f"  → This PDF may be corrupted, password-protected, or in an unsupported format", file=sys.stderr)
            print(f"  → Try opening and re-saving the PDF in Adobe Acrobat or Preview", file=sys.stderr)
            print(f"  → Normalized PDF saved at: {normalized_pdf_path}", file=sys.stderr)

        if verbose:
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Batch process forms through Textract and refinement pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run both Textract and refinement
  %(prog)s -i data/input -o data/output

  # Only run Textract (skip refinement)
  %(prog)s -i data/input -o data/output --skip-refine

  # Only run refinement (assumes parsed content already exists)
  %(prog)s -i data/input -o data/output --skip-textract

  # Custom S3 bucket and AWS region
  %(prog)s -i data/input -o data/output --s3-bucket my-bucket --region us-east-1

  # Adjust gap factor for paragraph grouping
  %(prog)s -i data/input -o data/output --gap-factor 2.0

Note: All PDF files are automatically normalized to handle various formats (.pdf, .PDF, .Pdf, etc.)
        """
    )

    parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Input directory containing PDF files"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        help="Output directory for processed files"
    )

    parser.add_argument(
        "--s3-bucket",
        type=str,
        help="S3 bucket name for large files (>5MB). Uses S3_UPLOAD_BUCKET env var if not specified."
    )

    parser.add_argument(
        "--region",
        type=str,
        default="us-west-2",
        help="AWS region (default: us-west-2)"
    )

    parser.add_argument(
        "--gap-factor",
        type=float,
        default=1.5,
        help="Vertical gap threshold for paragraph grouping (default: 1.5)"
    )

    parser.add_argument(
        "--skip-textract",
        action="store_true",
        help="Skip Textract processing (assumes parsed content already exists)"
    )

    parser.add_argument(
        "--skip-refine",
        action="store_true",
        help="Skip refinement step (only run Textract)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.input.exists():
        print(f"Error: Input directory does not exist: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.input.is_dir():
        print(f"Error: Input path is not a directory: {args.input}", file=sys.stderr)
        sys.exit(1)

    if args.skip_textract and args.skip_refine:
        print("Error: Cannot skip both Textract and refinement. Nothing to do!", file=sys.stderr)
        sys.exit(1)

    # Get S3 bucket from env if not specified
    import os
    s3_bucket = args.s3_bucket or os.environ.get("S3_UPLOAD_BUCKET")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Find all PDF files (case-insensitive for .pdf, .PDF, .Pdf, etc.)
    pdf_files = []
    for file in args.input.iterdir():
        if file.is_file() and file.suffix.lower() == '.pdf':
            pdf_files.append(file)
    pdf_files = sorted(pdf_files)

    if not pdf_files:
        print(f"No PDF files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF file(s) to process")
    print(f"Output directory: {args.output}")
    print(f"Steps: {'PDF Normalization + Textract' if not args.skip_textract else ''}{' + ' if not args.skip_textract and not args.skip_refine else ''}{'Refinement' if not args.skip_refine else ''}")
    print()

    # Process each file
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] Processing {pdf_file.name}...")

        process_file(
            pdf_file,
            args.output,
            s3_bucket,
            args.region,
            args.gap_factor,
            args.skip_textract,
            args.skip_refine,
            args.verbose,
        )

    print()
    print(f"✓ Batch processing complete! Processed {len(pdf_files)} file(s)")
    print(f"  Output directory: {args.output}")


if __name__ == "__main__":
    main()
