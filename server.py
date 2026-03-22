"""
Datasheets Extraction MCP Server

Exposes two tools:
  - extract_datasheet: full extraction → Markdown
  - extract_datasheet_section: targeted section extraction → Markdown
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

import extractor
import renderer

DEFAULT_MAX_PAGES = int(os.environ.get("DATASHEET_MAX_PAGES", "20"))

mcp = FastMCP(
    "datasheets",
    instructions=(
        "Use extract_datasheet to extract structured information from an electronic "
        "component PDF datasheet and receive clean Markdown output. "
        "Use extract_datasheet_section for faster targeted extraction of a specific section."
    ),
)

VALID_SECTIONS = frozenset({
    "specs", "abs_max", "pinout", "description", "features",
    "circuits", "package", "truth_tables",
})

# Map section names to extractor page signal keys
SECTION_TO_SIGNAL: dict[str, str | None] = {
    "specs": "specs",
    "abs_max": "abs_max",
    "pinout": "pinout",
    "circuits": "circuit",
    "package": "package",
    "truth_tables": "truth_table",
    "description": None,  # header pages only
    "features": None,     # header pages only
}


@mcp.tool()
def extract_datasheet(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> str:
    """
    Extract all structured information from an electronic component datasheet PDF
    and return it as formatted Markdown.

    Args:
        path: Absolute or relative path to the PDF file.
        max_pages: Maximum number of pages to send to Claude vision (0 = unlimited).
                   Override the default set by DATASHEET_MAX_PAGES env var.
    """
    try:
        ds, warning = extractor.extract(path, section_filter=None, max_pages=max_pages)
        return renderer.render(ds, truncation_warning=warning)
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as exc:
        return f"Error extracting datasheet: {exc}"


@mcp.tool()
def extract_datasheet_section(
    path: str,
    section: str,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> str:
    """
    Extract a specific section from an electronic component datasheet PDF.
    Faster than full extraction because only relevant pages are processed.

    Args:
        path: Absolute or relative path to the PDF file.
        section: One of: specs, abs_max, pinout, description, features,
                 circuits, package, truth_tables
        max_pages: Maximum number of pages to send to Claude vision (0 = unlimited).
    """
    if section not in VALID_SECTIONS:
        return (
            f"Error: Invalid section '{section}'. "
            f"Valid sections: {', '.join(sorted(VALID_SECTIONS))}"
        )

    signal = SECTION_TO_SIGNAL.get(section)

    try:
        ds, warning = extractor.extract(path, section_filter=signal, max_pages=max_pages)
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as exc:
        return f"Error extracting datasheet section: {exc}"

    # Render only the requested section
    from renderer import _spec_table, _truth_table_md

    lines: list[str] = []

    if section == "description":
        lines.append(f"# {ds.part_number or 'Unknown'} — Description\n")
        lines.append(ds.description or "*(not found)*")

    elif section == "features":
        lines.append(f"# {ds.part_number or 'Unknown'} — Features\n")
        if ds.features:
            lines.extend(f"- {f}" for f in ds.features)
        else:
            lines.append("*(not found)*")

    elif section == "pinout":
        lines.append(f"# {ds.part_number or 'Unknown'} — Pin Configuration\n")
        if ds.pins:
            lines.append("| Pin | Name | Type | Description |")
            lines.append("|-----|------|------|-------------|")
            for p in ds.pins:
                lines.append(f"| {p.number} | {p.name} | {p.type} | {p.description} |")
        else:
            lines.append("*(not found)*")

    elif section == "abs_max":
        lines.append(f"# {ds.part_number or 'Unknown'} — Absolute Maximum Ratings\n")
        lines.append(_spec_table(ds.absolute_max_ratings) or "*(not found)*")

    elif section == "specs":
        lines.append(f"# {ds.part_number or 'Unknown'} — Electrical Characteristics\n")
        lines.append(_spec_table(ds.specs) or "*(not found)*")

    elif section == "truth_tables":
        lines.append(f"# {ds.part_number or 'Unknown'} — Truth Tables\n")
        if ds.truth_tables:
            lines.extend(_truth_table_md(tt) for tt in ds.truth_tables)
        else:
            lines.append("*(not found)*")

    elif section == "package":
        lines.append(f"# {ds.part_number or 'Unknown'} — Package Information\n")
        if ds.package:
            lines.append(f"**Package:** {ds.package.name}")
            if ds.package.dimensions:
                lines.append(f"\n**Dimensions:** {ds.package.dimensions}")
            if ds.package.theta_ja:
                lines.append(f"\n**θJA:** {ds.package.theta_ja} °C/W")
        else:
            lines.append("*(not found)*")

    elif section == "circuits":
        lines.append(f"# {ds.part_number or 'Unknown'} — Typical Application Circuits\n")
        if ds.typical_circuits:
            for c in ds.typical_circuits:
                lines.append(f"### {c.name}\n\n{c.description}")
        else:
            lines.append("*(not found)*")

    result = "\n".join(lines)
    if warning:
        result += f"\n\n> ⚠️ {warning}"
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
