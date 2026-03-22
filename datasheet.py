#!/usr/bin/env python3
"""
Datasheet extraction CLI.

Usage:
    python datasheet.py <pdf_path>

Extracts structured information from an electronic component datasheet PDF
and prints formatted Markdown to stdout.
"""
from __future__ import annotations

import base64
import json
import os
import re
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
    all_inputs  = list(dict.fromkeys(k for row in tt.rows for k in row.inputs))
    all_outputs = list(dict.fromkeys(k for row in tt.rows for k in row.outputs))
    has_notes   = any(row.notes for row in tt.rows)
    headers     = all_inputs + all_outputs + (["Notes"] if has_notes else [])
    lines = [
        f"### {tt.name}", "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in tt.rows:
        cells  = [row.inputs.get(h, "")  for h in all_inputs]
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
        pkg   = ds.package
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

# ── PDF extraction ────────────────────────────────────────────────────────────

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
        skipped  = len(selected) - max_pages
        selected = selected[:max_pages]
        warning  = f"{skipped} additional relevant page(s) skipped (DATASHEET_MAX_PAGES={max_pages})"
    return selected, warning


def _table_to_markdown(table: list[list[str | None]]) -> str:
    if not table:
        return ""
    rows   = [[cell or "" for cell in row] for row in table]
    header, body = rows[0], rows[1:]
    lines  = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in body:
        padded = row + [""] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(padded[:len(header)]) + " |")
    return "\n".join(lines)


def _extract_raw_pages(
    path: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
) -> tuple[list[dict], str | None]:
    """
    Extract raw page data from a PDF.

    Each item contains: page number, label, text, raw tables (list-of-lists),
    char count, diagram flag, and base64 image data for diagram pages.
    Used by both read_pdf() (MCP) and _heuristic_extract() (CLI).
    """
    with pdfplumber.open(path) as pdf:
        pages_text   = [p.extract_text() or "" for p in pdf.pages]
        pages_tables = [p.extract_tables() or [] for p in pdf.pages]
        pages_chars  = [len(p.chars) for p in pdf.pages]

    selected, warning = _select_pages(pages_text, max_pages)
    doc = pymupdf.open(path)
    raw_pages: list[dict] = []

    for idx in selected:
        text       = pages_text[idx].strip()
        char_count = pages_chars[idx]
        is_diagram = char_count < DIAGRAM_CHAR_THRESHOLD
        label      = ", ".join(_detect_page_types(text)) or "header"

        img_data = None
        if is_diagram:
            page     = doc[idx]
            mat      = pymupdf.Matrix(dpi / 72, dpi / 72)
            pix      = page.get_pixmap(matrix=mat, alpha=False)
            img_data = base64.standard_b64encode(BytesIO(pix.tobytes("png")).getvalue()).decode()

        raw_pages.append({
            "page":       idx + 1,
            "label":      label,
            "text":       text,
            "tables":     pages_tables[idx],
            "char_count": char_count,
            "is_diagram": is_diagram,
            "img_data":   img_data,
        })

    doc.close()
    return raw_pages, warning


def read_pdf(
    path: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
) -> tuple[list[dict], str | None]:
    """
    Format raw page data as MCP content items (text strings + base64 images).
    Used by the MCP server.
    """
    raw_pages, warning = _extract_raw_pages(path, max_pages, dpi)
    items: list[dict] = []

    for p in raw_pages:
        if p["is_diagram"]:
            items.append({"type": "image", "page": p["page"], "label": p["label"], "data": p["img_data"]})
        else:
            parts = [f"--- Page {p['page']} [{p['label']}] ---"]
            if p["text"]:
                parts.append(p["text"])
            for i, table in enumerate(p["tables"]):
                md = _table_to_markdown(table)
                if md:
                    parts.append(f"\nTable {i + 1}:\n{md}")
            items.append({"type": "text", "page": p["page"], "label": p["label"], "text": "\n".join(parts)})

    return items, warning

# ── Heuristic extraction (CLI, no AI) ────────────────────────────────────────

def _is_pin_table(header: list[str]) -> bool:
    has_pin  = any("pin" in h or h in ("no", "no.", "#") for h in header)
    has_name = any("name" in h or "signal" in h or "symbol" in h for h in header)
    return has_pin and has_name


def _is_spec_table(header: list[str]) -> bool:
    has_param = any("param" in h or "characteristic" in h or "symbol" in h for h in header)
    has_value = any(h in ("min", "max", "typ", "value") for h in header)
    return has_param and has_value


def _parse_pin_table(table: list[list], header: list[str]) -> list[dict]:
    col      = {h: i for i, h in enumerate(header)}
    num_col  = next((i for h, i in col.items() if "pin" in h or "no" in h), 0)
    name_col = next((i for h, i in col.items() if "name" in h or "signal" in h or "symbol" in h), 1)
    type_col = next((i for h, i in col.items() if "type" in h or "i/o" in h or "dir" in h), None)
    desc_col = next((i for h, i in col.items() if "desc" in h or "function" in h or "comment" in h), None)

    def cell(row: list, c: int | None) -> str:
        return str(row[c] or "").strip() if c is not None and len(row) > c else ""

    pins = []
    for row in table[1:]:
        if not row or not row[num_col]:
            continue
        pins.append({
            "number":      cell(row, num_col),
            "name":        cell(row, name_col),
            "type":        cell(row, type_col),
            "description": cell(row, desc_col),
        })
    return pins


def _parse_spec_table(table: list[list], header: list[str]) -> list[dict]:
    col       = {h: i for i, h in enumerate(header)}
    param_col = next((i for h, i in col.items() if "param" in h or "characteristic" in h or "symbol" in h), 0)

    def gcol(name: str) -> int | None:
        return next((i for h, i in col.items() if name in h), None)

    min_c, typ_c, max_c, unit_c, cond_c = gcol("min"), gcol("typ"), gcol("max"), gcol("unit"), gcol("cond")

    def cell(row: list, c: int | None) -> str | None:
        v = str(row[c] or "").strip() if c is not None and len(row) > c else None
        return v or None

    specs = []
    for row in table[1:]:
        if not row or not row[param_col]:
            continue
        specs.append({
            "parameter":  str(row[param_col] or "").strip(),
            "min":        cell(row, min_c),
            "typ":        cell(row, typ_c),
            "max":        cell(row, max_c),
            "unit":       cell(row, unit_c),
            "conditions": cell(row, cond_c),
        })
    return specs


def _heuristic_extract(raw_pages: list[dict]) -> dict:
    """
    Best-effort schema population from pdfplumber output without AI.
    Used by the CLI. Fills what it can; leaves the rest empty.
    """
    result: dict = {
        "part_number": "", "manufacturer": "", "description": "",
        "features": [], "pins": [], "absolute_max_ratings": [],
        "specs": [], "package": None, "truth_tables": [], "typical_circuits": [],
    }

    for page in raw_pages:
        if page["is_diagram"]:
            continue

        text   = page["text"]
        tables = page["tables"]
        label  = page["label"]
        lines  = [l.strip() for l in text.split("\n") if l.strip()]

        # Part number: first token on early pages matching a component ID pattern
        if not result["part_number"] and page["page"] <= 2:
            for line in lines[:8]:
                m = re.match(r'^([A-Z]{2,}[\w\-]{1,}[0-9][\w\-\/]*)', line)
                if m:
                    result["part_number"] = m.group(1)
                    break

        # Description: first substantial non-bullet line from header pages
        if not result["description"] and "header" in label:
            for line in lines:
                if len(line) > 50 and not re.match(r'^[•\-\*–→▪▸\d\.#]', line):
                    result["description"] = line
                    break

        # Features: lines that look like bullet points
        for line in lines:
            if re.match(r'^[•\-\*–→▪▸]\s+\S', line) and len(line) > 10:
                clean = re.sub(r'^[•\-\*–→▪▸]\s*', '', line).strip()
                if clean and clean not in result["features"]:
                    result["features"].append(clean)

        # Tables
        for table in tables:
            if not table or not table[0]:
                continue
            header = [str(c or "").strip().lower() for c in table[0]]

            if _is_pin_table(header):
                result["pins"].extend(_parse_pin_table(table, header))

            elif _is_spec_table(header):
                target = "absolute_max_ratings" if "abs_max" in label else "specs"
                result[target].extend(_parse_spec_table(table, header))

            elif any("θja" in h or "theta" in h or "thermal" in h for h in header):
                m = re.search(
                    r'\b(SOT-?\d+[A-Z]?|QFN-?\d+|SOIC-?\d+|DIP-?\d+|SOP\w*|TSSOP-?\d+|LQFP-?\d+|TO-\d+)\b',
                    text, re.I,
                )
                if m and not result["package"]:
                    result["package"] = {"name": m.group(1).upper(), "dimensions": None, "theta_ja": None}

    return result

# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]

    try:
        raw_pages, warning = _extract_raw_pages(path)
    except FileNotFoundError:
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error reading PDF: {exc}", file=sys.stderr)
        sys.exit(1)

    raw_dict = _heuristic_extract(raw_pages)

    try:
        ds = Datasheet.model_validate(raw_dict)
    except Exception as exc:
        print(f"Error: Schema validation failed — {exc}", file=sys.stderr)
        sys.exit(1)

    print(render(ds))

    if warning:
        print(f"\nNote: {warning}", file=sys.stderr)


if __name__ == "__main__":
    main()
