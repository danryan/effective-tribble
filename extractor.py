"""
Hybrid datasheet extractor.

Strategy:
1. Open PDF with pdfplumber, extract text per page.
2. Label pages by detected content type using keyword signals.
3. Render selected pages to images (PyMuPDF) for Claude vision.
4. Call Claude with tool_use, forcing a Datasheet-shaped JSON response.
5. Parse + validate via Pydantic.
"""
from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any

import anthropic
import fitz  # PyMuPDF
import pdfplumber

from schema import (
    Circuit,
    Datasheet,
    Package,
    Pin,
    Spec,
    TruthTable,
    TruthTableRow,
)

# ---------------------------------------------------------------------------
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------
DEFAULT_MODEL = os.environ.get("DATASHEET_MODEL", "claude-sonnet-4-6")
DEFAULT_DPI = int(os.environ.get("DATASHEET_DPI", "150"))
DEFAULT_MAX_PAGES = int(os.environ.get("DATASHEET_MAX_PAGES", "20"))

# ---------------------------------------------------------------------------
# Page signal detection
# ---------------------------------------------------------------------------
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


def _label_page(text: str) -> list[str]:
    lower = text.lower()
    labels: list[str] = []
    for label, signals in PAGE_SIGNALS.items():
        if any(sig in lower for sig in signals):
            labels.append(label)
    return labels


def _select_pages(
    pages_text: list[str],
    section_filter: str | None,
    max_pages: int,
) -> tuple[list[int], str | None]:
    """Return (selected_page_indices, truncation_warning_or_None)."""
    selected: list[int] = []

    # Always include first 2 pages (header / description / features)
    header_pages = list(range(min(2, len(pages_text))))
    selected.extend(header_pages)

    for i, text in enumerate(pages_text):
        if i in selected:
            continue
        labels = _label_page(text)
        if not labels:
            continue
        if section_filter is None or section_filter in labels:
            selected.append(i)

    selected = sorted(set(selected))

    warning = None
    if max_pages > 0 and len(selected) > max_pages:
        skipped = len(selected) - max_pages
        selected = selected[:max_pages]
        warning = f"Truncated: {skipped} additional relevant page(s) not processed (max_pages={max_pages})"

    return selected, warning


def _render_page_base64(doc: fitz.Document, page_index: int, dpi: int) -> str:
    """Render a PDF page to a PNG and return base64-encoded bytes."""
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    buf = BytesIO(pix.tobytes("png"))
    return base64.standard_b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# Claude extraction tool schema
# ---------------------------------------------------------------------------
EXTRACTION_TOOL: dict[str, Any] = {
    "name": "record_datasheet",
    "description": (
        "Record all extracted information from the datasheet pages provided. "
        "Fill every field you can find. Use empty lists/null for missing data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "part_number": {"type": "string"},
            "manufacturer": {"type": "string"},
            "description": {"type": "string"},
            "features": {"type": "array", "items": {"type": "string"}},
            "pins": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {"type": "string"},
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["number", "name"],
                },
            },
            "absolute_max_ratings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameter": {"type": "string"},
                        "min": {"type": ["string", "null"]},
                        "typ": {"type": ["string", "null"]},
                        "max": {"type": ["string", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "conditions": {"type": ["string", "null"]},
                    },
                    "required": ["parameter"],
                },
            },
            "specs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameter": {"type": "string"},
                        "min": {"type": ["string", "null"]},
                        "typ": {"type": ["string", "null"]},
                        "max": {"type": ["string", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "conditions": {"type": ["string", "null"]},
                    },
                    "required": ["parameter"],
                },
            },
            "package": {
                "type": ["object", "null"],
                "properties": {
                    "name": {"type": "string"},
                    "dimensions": {"type": ["string", "null"]},
                    "theta_ja": {"type": ["string", "null"]},
                },
                "required": ["name"],
            },
            "truth_tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                                    "outputs": {"type": "object", "additionalProperties": {"type": "string"}},
                                    "notes": {"type": ["string", "null"]},
                                },
                            },
                        },
                    },
                    "required": ["name", "rows"],
                },
            },
            "typical_circuits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["name", "description"],
                },
            },
        },
        "required": ["part_number"],
    },
}


def _build_message_content(
    pages_text: list[str],
    selected_indices: list[int],
    doc: fitz.Document,
    dpi: int,
) -> list[dict[str, Any]]:
    """Build the content list for the Claude API message."""
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "You are extracting structured data from an electronic component datasheet. "
                "The following pages have been selected as relevant. "
                "Call the record_datasheet tool with all information you can extract."
            ),
        }
    ]

    for idx in selected_indices:
        page_num = idx + 1
        text = pages_text[idx].strip()
        img_b64 = _render_page_base64(doc, idx, dpi)

        content.append({
            "type": "text",
            "text": f"\n--- Page {page_num} (extracted text) ---\n{text}\n",
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_b64,
            },
        })

    return content


def _parse_datasheet(raw: dict[str, Any]) -> Datasheet:
    """Parse Claude's tool call input into a validated Datasheet."""
    pins = [Pin(**p) for p in raw.get("pins", [])]

    def parse_specs(items: list[dict]) -> list[Spec]:
        return [Spec(**s) for s in items]

    truth_tables = []
    for tt in raw.get("truth_tables", []):
        rows = [TruthTableRow(**r) for r in tt.get("rows", [])]
        truth_tables.append(TruthTable(name=tt["name"], rows=rows))

    circuits = [Circuit(**c) for c in raw.get("typical_circuits", [])]

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
        typical_circuits=circuits,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(
    path: str,
    section_filter: str | None = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
    model: str = DEFAULT_MODEL,
) -> tuple[Datasheet, str | None]:
    """
    Extract a Datasheet from a PDF file.

    Returns (datasheet, truncation_warning_or_None).
    `section_filter` restricts page selection to pages matching a specific content type
    (e.g. "pinout", "specs", "abs_max", "truth_table", "circuit", "package").
    """
    client = anthropic.Anthropic()

    # 1. Extract text per page
    pages_text: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")

    # 2. Select relevant pages
    selected_indices, truncation_warning = _select_pages(
        pages_text, section_filter, max_pages
    )

    if not selected_indices:
        return Datasheet(), truncation_warning

    # 3. Render pages as images
    doc = fitz.open(path)

    # 4. Build message and call Claude
    content = _build_message_content(pages_text, selected_indices, doc, dpi)
    doc.close()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": content}],
    )

    # 5. Parse tool call result
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_datasheet":
            return _parse_datasheet(block.input), truncation_warning

    # Fallback: no tool call in response
    return Datasheet(), truncation_warning
