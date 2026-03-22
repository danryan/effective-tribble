"""
Datasheets Extraction MCP Server

Two tools:
  - read_datasheet: mechanical PDF reading → text + images for Claude to interpret
  - record_datasheet: accepts Claude's structured extraction → validates + renders Markdown
"""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP, Image

import pdf_reader
import renderer
from schema import (
    Circuit,
    Datasheet,
    Package,
    Pin,
    Spec,
    TruthTable,
    TruthTableRow,
)

DEFAULT_MAX_PAGES = int(os.environ.get("DATASHEET_MAX_PAGES", "20"))

mcp = FastMCP(
    "datasheets",
    instructions=(
        "Use read_datasheet to load a component datasheet PDF. "
        "After reading the content, extract all information and call record_datasheet "
        "with the structured data to produce validated Markdown output."
    ),
)


@mcp.tool()
def read_datasheet(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> list:
    """
    Read an electronic component datasheet PDF and return its content
    (text, Markdown-formatted tables, and diagram images) for extraction.

    After calling this tool, extract all component information from the returned
    content and call record_datasheet with the structured data.

    Args:
        path: Absolute or relative path to the PDF file.
        max_pages: Maximum number of relevant pages to process (0 = unlimited).
                   Configurable via DATASHEET_MAX_PAGES env var.
    """
    try:
        items, warning = pdf_reader.read_pdf(path, max_pages=max_pages)
    except FileNotFoundError:
        return [f"Error: File not found: {path}"]
    except Exception as exc:
        return [f"Error reading PDF: {exc}"]

    result = []
    for item in items:
        if item["type"] == "text":
            result.append(item["text"])
        elif item["type"] == "image":
            result.append(f"--- Page {item['page']} [{item['label']}] (diagram/schematic) ---")
            result.append(Image(data=item["data"], format="png"))

    if warning:
        result.append(f"\n> ⚠️ {warning}")

    return result


@mcp.tool()
def record_datasheet(data: str) -> str:
    """
    Validate and render extracted datasheet data as formatted Markdown.

    Call this after read_datasheet once you have extracted all component information.
    Pass a JSON string conforming to the Datasheet schema.

    Schema:
      {
        "part_number": str,
        "manufacturer": str,
        "description": str,
        "features": [str, ...],
        "pins": [{"number": str, "name": str, "type": str, "description": str}, ...],
        "absolute_max_ratings": [{"parameter": str, "min": str|null, "typ": str|null,
                                   "max": str|null, "unit": str|null, "conditions": str|null}, ...],
        "specs": [same as absolute_max_ratings, ...],
        "package": {"name": str, "dimensions": str|null, "theta_ja": str|null} | null,
        "truth_tables": [{"name": str, "rows": [{"inputs": {}, "outputs": {}, "notes": str|null}]}, ...],
        "typical_circuits": [{"name": str, "description": str}, ...]
      }

    Args:
        data: JSON string with extracted datasheet fields.
    """
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON — {exc}"

    try:
        ds = _parse_datasheet(raw)
    except Exception as exc:
        return f"Error: Schema validation failed — {exc}"

    return renderer.render(ds)


def _parse_datasheet(raw: dict) -> Datasheet:
    pins = [Pin(**p) for p in raw.get("pins", [])]

    def parse_specs(items: list) -> list[Spec]:
        return [Spec(**s) for s in items]

    truth_tables = [
        TruthTable(
            name=tt["name"],
            rows=[TruthTableRow(**r) for r in tt.get("rows", [])],
        )
        for tt in raw.get("truth_tables", [])
    ]

    pkg_raw = raw.get("package")
    package = Package(**pkg_raw) if pkg_raw else None

    return Datasheet(
        part_number=raw.get("part_number", ""),
        manufacturer=raw.get("manufacturer", ""),
        description=raw.get("description", ""),
        features=raw.get("features", []),
        pins=pins,
        absolute_max_ratings=parse_specs(raw.get("absolute_max_ratings", [])),
        specs=parse_specs(raw.get("specs", [])),
        package=package,
        truth_tables=truth_tables,
        typical_circuits=[Circuit(**c) for c in raw.get("typical_circuits", [])],
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
