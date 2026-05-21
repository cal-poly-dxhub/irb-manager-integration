import argparse
import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def render_paragraph(console: Console, element: dict):
    page = element.get("page", "?")
    console.print(
        Panel(
            element["content"],
            title=f"Page {page}",
            title_align="right",
            border_style="dim",
            padding=(0, 1),
        )
    )


def render_table(console: Console, element: dict):
    page = element.get("page", "?")
    rows = element.get("rows", [])

    if not rows:
        return

    table = Table(
        title=f"Page {page}",
        show_header=True,
        header_style="bold",
        border_style="blue",
        padding=(0, 1),
    )

    # Use first row as headers
    for i, cell in enumerate(rows[0]):
        table.add_column(cell or f"Col {i + 1}")

    for row in rows[1:]:
        table.add_row(*(cell or "" for cell in row))

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="View paragraph/table JSON in a scrollable terminal format."
    )
    parser.add_argument("input", nargs="+", help="One or more JSON files to display")
    args = parser.parse_args()

    console = Console()

    for path in args.input:
        try:
            with open(path) as f:
                elements = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Error:[/red] file not found: {path}", style="bold")
            sys.exit(1)

        if len(args.input) > 1:
            console.rule(f"[bold]{path}[/bold]")

        for element in elements:
            kind = element.get("type")
            if kind == "paragraph":
                render_paragraph(console, element)
            elif kind == "table":
                render_table(console, element)
            else:
                console.print(Text(str(element), style="dim"))
            console.print()


if __name__ == "__main__":
    main()
