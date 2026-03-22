#!/usr/bin/env python3
"""
Datasheet extraction CLI.

Usage:
    python datasheet.py read <path>         Extract text and tables from a PDF
    python datasheet.py record '<json>'     Validate and render structured data as Markdown
"""
from __future__ import annotations

import json
import os
import sys

import fitz  # PyMuPDF
import pdfplumber

from renderer import render
from schema import Circuit, Datasheet, Package, Pin, Spec, TruthTable, TruthTableRow

DEFAULT_DPI = int(os.environ.get("DATASHEET_DPI", "150"))
DEFAULT_MAX_PAGES = int(os.environ.get("DATASHEET_MAX_PAGES", "20"))
DIAGRAM_CHAR_THRESHOLD = 50

PAGE_SIGNALS: dict[str, list[str]] = {
    "pinout": [
        "pin configuration", "pinout", "pin description",
        "pin functions", "pin assignment",
    ],
    "abs_max": [
        "absolute maximum", "stresses beyond",
    ],
    "specs": [
        "electrical characteristics", "dc characteristics", "ac characteristics",
        "recommended operating", "operating conditions",
    ],
    "truth_table": [
        "truth table", "logic table", "function table", "mode select",
    ],
    "circuit": [
        "typical application", "application circuit", "application diagram",
        "application schematic",
    ],
    "package": [
        "package dimensions", "mechanical dimensions", "land pattern",
        "thermal resistance", "theta", "package outline",
    ],
}


def _detect_page_types(text: str) -> list[str]:
    lower = text.lower()
    return [label for label, signals in PAGE_SIGNALS.items()
            if any(sig in lower for sig in signals)]


def _select_pages(pages_text: list[str], max_pages: int) -> tuple[list[int], str | None]:
    selected = list(range(min(2, len(pages_text))))
    for i, text in enumerate(pages_text):
        if i not in selected and _detect_page_types(text):
            selected.append(i)
    selected = sorted(set(selected))

    warning = None
    if max_pages > 0 and len(selected) > max_pages:
        skipped = len(selected) - max_pages
        selected = selected[:max_pages]
        warning = f"Note: {skipped} additional relevant page(s) skipped (DATASHEET_MAX_PAGES={max_pages})"
    return selected, warning


def _table_to_markdown(table: list[list[str | None]]) -> str:
    if not table:
        return ""
    rows = [[cell or "" for cell in row] for row in table]
    header, body = rows[0], rows[1:]
    sep = ["---"] * len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in body:
        padded = row + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(padded[:len(header)]) + " |")
    return "\n".join(lines)


def cmd_read(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> None:
    """Extract text and tables from a PDF, print to stdout for Claude to read."""
    with pdfplumber.open(path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
        pages_tables = [p.extract_tables() or [] for p in pdf.pages]
        pages_chars = [len(p.chars) for p in pdf.pages]

    selected, warning = _select_pages(pages_text, max_pages)

    for idx in selected:
        text = pages_text[idx].strip()
        tables = pages_tables[idx]
        char_count = pages_chars[idx]
        page_types = _detect_page_types(text)
        label = ", ".join(page_types) if page_types else "header"

        print(f"\n--- Page {idx + 1} [{label}] ---")

        if char_count < DIAGRAM_CHAR_THRESHOLD:
            print(f"(diagram/schematic page — no extractable text)")
        else:
            if text:
                print(text)
            for i, table in enumerate(tables):
                md = _table_to_markdown(table)
                if md:
                    print(f"\nTable {i + 1}:\n{md}")

    if warning:
        print(f"\n{warning}", file=sys.stderr)


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


def cmd_record(json_str: str) -> None:
    """Validate structured JSON and render as Markdown, print to stdout."""
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON — {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        ds = _parse_datasheet(raw)
    except Exception as exc:
        print(f"Error: Schema validation failed — {exc}", file=sys.stderr)
        sys.exit(1)

    print(render(ds))


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "read":
        cmd_read(sys.argv[2])
    elif command == "record":
        cmd_record(sys.argv[2])
    else:
        print(f"Error: Unknown command '{command}'. Use 'read' or 'record'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
