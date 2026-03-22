"""
Datasheets MCP Server

Single tool: extract_datasheet
Returns PDF page content (text, Markdown tables, diagram images) for Claude to interpret.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP, Image

from datasheet import DEFAULT_MAX_PAGES, read_pdf

mcp = FastMCP(
    "datasheets",
    instructions=(
        "Use extract_datasheet to read a component datasheet PDF. "
        "Extract all information from the returned content and format it as Markdown."
    ),
)


@mcp.tool()
def extract_datasheet(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> list:
    """
    Read an electronic component datasheet PDF and return its content for extraction.

    Returns page text with Markdown-formatted tables, and images for diagram/schematic
    pages. Use the returned content to extract component information and produce
    structured Markdown output.

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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
