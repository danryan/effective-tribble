#!/usr/bin/env python3
"""
Datasheet extraction CLI.

Usage:
    python datasheet.py read <path>         Extract text and tables from a PDF
    python datasheet.py record '<json>'     Validate and render structured data as Markdown
"""
from __future__ import annotations

import base64
import json
import os
import sys
from io import BytesIO

import pdfplumber
import pymupdf
from pydantic import BaseModel, Field

# ── Configuration ─────────────────────────────────────────────────────────────

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

# ── Models ────────────────────────────────────────────────────────────────────

class Pin(BaseModel):
    number: str
    name: str
    type: str = ""  # "I", "O", "I/O", "Power", "GND", "NC"
    description: str = ""


class Spec(BaseModel):
    parameter: str
    min: str | None = None
    typ: str | None = None
    max: str | None = None
    unit: str | None = None
    conditions: str | None = None


class Package(BaseModel):
    name: str
    dimensions: str | None = None
    theta_ja: str | None = None  # °C/W


class TruthTableRow(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None


class TruthTable(BaseModel):
    name: str
    rows: list[TruthTableRow] = Field(default_factory=list)


class Circuit(BaseModel):
    name: str
    description: str


class Datasheet(BaseModel):
    part_number: str = ""
    manufacturer: str = ""
    description: str = ""
    features: list[str] = Field(default_factory=list)
    pins: list[Pin] = Field(default_factory=list)
    absolute_max_ratings: list[Spec] = Field(default_factory=list)
    specs: list[Spec] = Field(default_factory=list)
    package: Package | None = None
    truth_tables: list[TruthTable] = Field(default_factory=list)
    typical_circuits: list[Circuit] = Field(default_factory=list)

# ── Renderer ──────────────────────────────────────────────────────────────────

def _spec_table(specs: list[Spec]) -> str:
    rows = [
        "| Parameter | Min | Typ | Max | Unit | Conditions |",
        "|-----------|-----|-----|-----|------|------------|",
    ]
    for s in specs:
        rows.append(
            f"| {s.parameter} | {s.min or ''} | {s.typ or ''} | {s.max or ''}"
            f" | {s.unit or ''} | {s.conditions or ''} |"
        )
    return "\n".join(rows)


def _truth_table_md(tt: TruthTable) -> str:
    if not tt.rows:
        return f"### {tt.name}\n\n*(no rows)*"
    all_inputs = list(dict.fromkeys(k for row in tt.rows for k in row.inputs))
    all_outputs = list(dict.fromkeys(k for row in tt.rows for k in row.outputs))
    has_notes = any(row.notes for row in tt.rows)
    headers = all_inputs + all_outputs + (["Notes"] if has_notes else [])
    lines = [
        f"### {tt.name}", "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in tt.rows:
        cells = [row.inputs.get(h, "") for h in all_inputs]
        cells += [row.outputs.get(h, "") for h in all_outputs]
        if has_notes:
            cells.append(row.notes or "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render(ds: Datasheet) -> str:
    parts: list[str] = []

    title = ds.part_number or "Unknown Part"
    if ds.manufacturer:
        title += f" — {ds.manufacturer}"
    parts.append(f"# {title}")

    if ds.description:
        parts.append(f"\n## Description\n\n{ds.description}")

    if ds.features:
        parts.append("\n## Features\n\n" + "\n".join(f"- {f}" for f in ds.features))

    if ds.pins:
        rows = ["| Pin | Name | Type | Description |", "|-----|------|------|-------------|"]
        for p in ds.pins:
            rows.append(f"| {p.number} | {p.name} | {p.type} | {p.description} |")
        parts.append("\n## Pin Configuration\n\n" + "\n".join(rows))

    if ds.absolute_max_ratings:
        parts.append("\n## Absolute Maximum Ratings\n\n" + _spec_table(ds.absolute_max_ratings))

    if ds.specs:
        parts.append("\n## Electrical Characteristics\n\n" + _spec_table(ds.specs))

    if ds.truth_tables:
        parts.append("\n## Truth Tables\n\n" + "\n\n".join(_truth_table_md(tt) for tt in ds.truth_tables))

    if ds.package:
        pkg = ds.package
        lines = [f"**Package:** {pkg.name}"]
        if pkg.dimensions:
            lines.append(f"**Dimensions:** {pkg.dimensions}")
        if pkg.theta_ja:
            lines.append(f"**θJA:** {pkg.theta_ja} °C/W")
        parts.append("\n## Package Information\n\n" + "\n\n".join(lines))

    if ds.typical_circuits:
        blocks = [f"### {c.name}\n\n{c.description}" for c in ds.typical_circuits]
        parts.append("\n## Typical Application Circuits\n\n" + "\n\n".join(blocks))

    return "\n".join(parts)

# ── PDF Reader ────────────────────────────────────────────────────────────────

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
        warning = f"{skipped} additional relevant page(s) skipped (DATASHEET_MAX_PAGES={max_pages})"
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


def read_pdf(
    path: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
) -> tuple[list[dict], str | None]:
    """
    Read a datasheet PDF and return content items plus an optional truncation warning.

    Each item is one of:
      {"type": "text",  "page": int, "label": str, "text": str}
      {"type": "image", "page": int, "label": str, "data": str}  # base64 PNG
    """
    with pdfplumber.open(path) as pdf:
        pages_text   = [p.extract_text() or "" for p in pdf.pages]
        pages_tables = [p.extract_tables() or [] for p in pdf.pages]
        pages_chars  = [len(p.chars) for p in pdf.pages]

    selected, warning = _select_pages(pages_text, max_pages)
    doc = pymupdf.open(path)
    items: list[dict] = []

    for idx in selected:
        text       = pages_text[idx].strip()
        tables     = pages_tables[idx]
        char_count = pages_chars[idx]
        label      = ", ".join(_detect_page_types(text)) or "header"

        if char_count < DIAGRAM_CHAR_THRESHOLD:
            page = doc[idx]
            mat  = pymupdf.Matrix(dpi / 72, dpi / 72)
            pix  = page.get_pixmap(matrix=mat, alpha=False)
            data = base64.standard_b64encode(BytesIO(pix.tobytes("png")).getvalue()).decode()
            items.append({"type": "image", "page": idx + 1, "label": label, "data": data})
        else:
            parts = [f"--- Page {idx + 1} [{label}] ---"]
            if text:
                parts.append(text)
            for i, table in enumerate(tables):
                md = _table_to_markdown(table)
                if md:
                    parts.append(f"\nTable {i + 1}:\n{md}")
            items.append({"type": "text", "page": idx + 1, "label": label, "text": "\n".join(parts)})

    doc.close()
    return items, warning

# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_read(path: str, max_pages: int = DEFAULT_MAX_PAGES) -> None:
    items, warning = read_pdf(path, max_pages=max_pages)
    for item in items:
        if item["type"] == "text":
            print(item["text"])
        else:
            print(f"\n--- Page {item['page']} [{item['label']}] (diagram — not renderable in terminal) ---")
    if warning:
        print(f"\nNote: {warning}", file=sys.stderr)


def cmd_record(json_str: str) -> None:
    try:
        raw = json.loads(json_str)
    except json.JSONDecodeError as exc:
        print(f"Error: Invalid JSON — {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        ds = Datasheet.model_validate(raw)
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
