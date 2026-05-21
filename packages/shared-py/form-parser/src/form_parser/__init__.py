"""Form parsing utilities for AWS Textract."""

from baml_client.types import Form, Paragraph, Table
from form_parser.paragraphs import (
    build_block_index,
    cell_text,
    extract_lines,
    extract_tables,
    get_child_ids,
    group_into_paragraphs,
    join_paragraphs,
    line_inside_table,
    merge_elements,
)
from form_parser.textract import (
    analyze_document,
    collect_results,
    poll_for_completion,
    process_pdf,
    process_pdf_async,
    start_analysis,
    upload_to_s3,
)

__all__ = [
    # types
    "Form",
    "Paragraph",
    "Table",
    # textract
    "analyze_document",
    "collect_results",
    "poll_for_completion",
    "process_pdf",
    "process_pdf_async",
    "start_analysis",
    "upload_to_s3",
    # paragraphs
    "build_block_index",
    "cell_text",
    "extract_lines",
    "extract_tables",
    "get_child_ids",
    "group_into_paragraphs",
    "join_paragraphs",
    "line_inside_table",
    "merge_elements",
]
