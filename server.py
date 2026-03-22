"""
Datasheets MCP Server

Thin wrapper around datasheet.py that exposes two tools:
  - read_datasheet:   PDF → text + diagram images for Claude to interpret
  - record_datasheet: Claude's structured JSON → validated Markdown output
"""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP, Image

from datasheet import DEFAULT_MAX_PAGES, Datasheet, read_pdf, render

mcp = FastMCP(
    "datasheets",
    instructions=(
        "Use read_datasheet to load a component datasheet PDF. "
        "Extract all information from the returned content, then call "
        "record_datasheet with the structured JSON to produce validated Markdown."
    ),
)


@mcp.tool()
def read_datasheet(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> list:
    """
    Read an electronic component datasheet PDF.
    Returns page text, Markdown-formatted tables, and images for diagram pages.
    After reading, extract all component information and call record_datasheet.

    Args:
        path: Absolute or relative path to the PDF file.
        max_pages: Max relevant pages to process (0 = unlimited).
                   Default set by DATASHEET_MAX_PAGES env var.
    """
    try:
        items, warning = read_pdf(path, max_pages=max_pages)
    except FileNotFoundError:
        return [f"Error: File not found: {path}"]
    except Exception as exc:
        return [f"Error reading PDF: {exc}"]

    result: list = []
    for item in items:
        if item["type"] == "text":
            result.append(item["text"])
        else:
            result.append(f"--- Page {item['page']} [{item['label']}] (diagram/schematic) ---")
            result.append(Image(data=item["data"], format="png"))

    if warning:
        result.append(f"\n> ⚠️ {warning}")

    return result


@mcp.tool()
def record_datasheet(data: str) -> str:
    """
    Validate structured datasheet JSON and render as Markdown.
    Call this after read_datasheet once you have extracted all component information.

    Args:
        data: JSON string matching the Datasheet schema. All numeric values
              should be strings. Use [] for missing lists, null for missing scalars.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON — {exc}"
    try:
        ds = Datasheet.model_validate(raw)
    except Exception as exc:
        return f"Error: Schema validation failed — {exc}"
    return render(ds)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
