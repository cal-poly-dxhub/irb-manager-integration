#!/usr/bin/env python3
"""Test script for RefineForm BAML function.

This script takes a ParsedContent JSON file (with paragraph/table elements) and runs
the Claude-powered RefineForm function to convert it into a structured Form with
grouped fields.

Usage:
    python scripts/test_refine_form.py -i data/parsed_content.json -o data/refined_form.json
    python scripts/test_refine_form.py --input parsed.json --output refined.json
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

from baml_client import b
from baml_client.types import ParsedContent, Form


def load_parsed_content(input_path: Path) -> ParsedContent:
    """Load a ParsedContent from a JSON file.

    Args:
        input_path: Path to JSON file containing ParsedContent data

    Returns:
        ParsedContent object with elements (paragraphs and tables)

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If JSON is invalid or doesn't match ParsedContent schema
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path) as f:
        data = json.load(f)

    # Handle different input formats
    if "elements" in data:
        parsed_data = {"elements": data["elements"]}
    else:
        raise ValueError("Input JSON must contain 'elements' field")

    try:
        return ParsedContent(**parsed_data)
    except Exception as e:
        raise ValueError(f"Failed to parse ParsedContent from JSON: {e}")


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


def refine_form(parsed_content: ParsedContent) -> Form:
    """Refine ParsedContent into a structured Form using BAML RefineForm function.

    This calls Claude to analyze the raw parsed content and intelligently group
    related fields together while preserving individual fields where appropriate.

    Args:
        parsed_content: ParsedContent with raw paragraphs and tables

    Returns:
        Form with structured and grouped fields
    """
    print(f"Refining form with {len(parsed_content.elements)} elements...")
    refined = b.RefineForm(parsed_content)
    print(f"✓ Refined into {len(refined.members)} form members")
    return refined


def save_output(form: Form, output_path: Path) -> None:
    """Save Form to a JSON file with UUIDs assigned to all id fields.

    Args:
        form: Form to save
        output_path: Path where JSON should be written
    """
    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict
    form_dict = form.model_dump()

    # Assign UUIDs to all id fields
    form_dict = assign_ids(form_dict)

    # Save as JSON
    with open(output_path, "w") as f:
        json.dump(form_dict, f, indent=2)

    print(f"✓ Saved refined form to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Test RefineForm BAML function to convert ParsedContent to structured Form",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i data/parsed_content.json -o data/refined_form.json
  %(prog)s --input parsed.json --output refined.json
        """
    )

    parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        help="Path to input JSON file (ParsedContent with paragraph/table elements)"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        help="Path to output JSON file (Form with grouped fields)"
    )

    args = parser.parse_args()

    try:
        # Load parsed content
        print(f"Loading parsed content from {args.input}...")
        parsed_content = load_parsed_content(args.input)
        print(f"✓ Loaded {len(parsed_content.elements)} elements")

        # Refine with Claude
        refined_form = refine_form(parsed_content)

        # Save output with UUIDs assigned
        save_output(refined_form, args.output)

        print("\n✓ Success!")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
