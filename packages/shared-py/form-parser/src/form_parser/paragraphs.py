"""Functions for joining Textract blocks into paragraphs and tables."""

import uuid
from typing import Union

from baml_client.types import Form, Paragraph, Table


def build_block_index(blocks: list[dict]) -> dict[str, dict]:
    """Build a lookup index from block ID to block."""
    return {b["Id"]: b for b in blocks if "Id" in b}


def get_child_ids(block: dict, rel_type: str = "CHILD") -> list[str]:
    """Get child IDs from a block's relationships."""
    for rel in block.get("Relationships", []):
        if rel["Type"] == rel_type:
            return rel["Ids"]
    return []


def cell_text(cell_block: dict, index: dict[str, dict]) -> str:
    """Extract text from a table cell by joining child WORD blocks."""
    words = []
    for word_id in get_child_ids(cell_block):
        word_block = index.get(word_id)
        if word_block and word_block.get("BlockType") == "WORD":
            words.append(word_block["Text"])
    return " ".join(words)


def extract_tables(blocks: list[dict], index: dict[str, dict]) -> list[dict]:
    """Extract tables from Textract blocks.

    Args:
        blocks: List of Textract blocks
        index: Block ID → block lookup

    Returns:
        List of table dicts with keys: type, id, content, page, top, height
    """
    tables = []
    for block in blocks:
        if block.get("BlockType") != "TABLE":
            continue

        bb = block["Geometry"]["BoundingBox"]
        cell_ids = get_child_ids(block)

        # Collect cells and determine grid dimensions
        cells = []
        max_row = 0
        max_col = 0
        for cid in cell_ids:
            cb = index.get(cid)
            if not cb or cb.get("BlockType") != "CELL":
                continue
            row = cb["RowIndex"]
            col = cb["ColumnIndex"]
            max_row = max(max_row, row)
            max_col = max(max_col, col)
            cells.append((row, col, cell_text(cb, index)))

        # Build row-major grid
        grid = [[""] * max_col for _ in range(max_row)]
        for row, col, text in cells:
            grid[row - 1][col - 1] = text

        tables.append({
            "type": "table",
            "id": str(uuid.uuid4()),
            "content": grid,
            "page": block.get("Page", 1),
            "top": bb["Top"],
            "height": bb["Height"],
        })

    return tables


def line_inside_table(line: dict, tables: list[dict]) -> bool:
    """Check whether a LINE's midpoint falls inside any table bbox."""
    ly = line["top"] + line["height"] / 2
    for t in tables:
        if line["page"] != t["page"]:
            continue
        if t["top"] <= ly <= t["top"] + t["height"]:
            return True
    return False


def extract_lines(blocks: list[dict], tables: list[dict]) -> list[dict]:
    """Extract LINE blocks that are not inside tables.

    Args:
        blocks: List of Textract blocks
        tables: List of table dicts (must have page, top, height)

    Returns:
        List of line dicts with keys: text, page, top, left, height, width
    """
    lines = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        bb = block["Geometry"]["BoundingBox"]
        line = {
            "text": block["Text"],
            "page": block.get("Page", 1),
            "top": bb["Top"],
            "left": bb["Left"],
            "height": bb["Height"],
            "width": bb["Width"],
        }
        if not line_inside_table(line, tables):
            lines.append(line)
    return lines


def group_into_paragraphs(lines: list[dict], gap_factor: float = 1.5) -> list[dict]:
    """Group lines into paragraphs based on vertical proximity.

    Two consecutive lines belong to the same paragraph when:
      1. They are on the same page.
      2. The vertical gap between them is less than gap_factor * the
         previous line's height (i.e. roughly single-spaced).

    Args:
        lines: List of line dicts (must have page, top, height, text)
        gap_factor: Max vertical gap as a multiple of line height

    Returns:
        List of paragraph dicts with keys: type, id, content, page, top
    """
    if not lines:
        return []

    lines.sort(key=lambda l: (l["page"], l["top"], l["left"]))

    paragraphs = []
    current = [lines[0]]

    for line in lines[1:]:
        prev = current[-1]
        prev_bottom = prev["top"] + prev["height"]
        gap = line["top"] - prev_bottom

        same_page = line["page"] == prev["page"]
        close_enough = gap < prev["height"] * gap_factor

        if same_page and close_enough:
            current.append(line)
        else:
            paragraphs.append({
                "type": "paragraph",
                "id": str(uuid.uuid4()),
                "content": " ".join(l["text"] for l in current),
                "page": current[0]["page"],
                "top": current[0]["top"],
            })
            current = [line]

    paragraphs.append({
        "type": "paragraph",
        "id": str(uuid.uuid4()),
        "content": " ".join(l["text"] for l in current),
        "page": current[0]["page"],
        "top": current[0]["top"],
    })

    return paragraphs


def merge_elements(paragraphs: list[dict], tables: list[dict]) -> list[dict]:
    """Merge paragraphs and tables in document order.

    Args:
        paragraphs: List of paragraph dicts (must have page, top)
        tables: List of table dicts (must have page, top)

    Returns:
        Combined list sorted by (page, top), with positioning keys removed
    """
    elements = paragraphs + tables
    elements.sort(key=lambda e: (e["page"], e["top"]))

    # Strip internal positioning keys from output
    for e in elements:
        e.pop("top", None)
        e.pop("height", None)

    return elements


def join_paragraphs(blocks: list[dict], gap_factor: float = 1.5) -> list[dict]:
    """Main entry point: convert Textract blocks into paragraphs and tables.

    Args:
        blocks: List of Textract block dictionaries
        gap_factor: Max vertical gap as a multiple of line height for paragraph grouping

    Returns:
        List of elements (paragraphs and tables) in document order
    """
    index = build_block_index(blocks)
    tables = extract_tables(blocks, index)
    lines = extract_lines(blocks, tables)
    paragraphs = group_into_paragraphs(lines, gap_factor)
    return merge_elements(paragraphs, tables)
