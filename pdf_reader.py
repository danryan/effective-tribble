"""
Mechanical PDF reader for electronic component datasheets.

Responsibilities:
- Extract text and tables from PDF pages using pdfplumber
- Format tables as Markdown
- Detect relevant pages via keyword signals
- Render diagram/schematic pages as images (PyMuPDF) when text is sparse
- Return a list of MCP-compatible content items (text strings or base64 images)

No AI calls are made here. Claude handles all interpretation.
"""
from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

DEFAULT_DPI = int(os.environ.get("DATASHEET_DPI", "150"))
DEFAULT_MAX_PAGES = int(os.environ.get("DATASHEET_MAX_PAGES", "20"))

# Minimum char count below which a page is treated as a diagram/image page
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


def _select_pages(
    pages_text: list[str],
    max_pages: int,
) -> tuple[list[int], str | None]:
    selected: list[int] = list(range(min(2, len(pages_text))))  # always include first 2

    for i, text in enumerate(pages_text):
        if i not in selected and _detect_page_types(text):
            selected.append(i)

    selected = sorted(set(selected))

    warning = None
    if max_pages > 0 and len(selected) > max_pages:
        skipped = len(selected) - max_pages
        selected = selected[:max_pages]
        warning = f"Truncated: {skipped} additional relevant page(s) skipped (max_pages={max_pages})"

    return selected, warning


def _table_to_markdown(table: list[list[str | None]]) -> str:
    if not table:
        return ""
    # Use first row as header if it looks like one, otherwise generate indices
    rows = [[cell or "" for cell in row] for row in table]
    header = rows[0]
    sep = ["---"] * len(header)
    body = rows[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in body:
        # Pad short rows
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded) + " |")
    return "\n".join(lines)


def _render_page_image(doc: fitz.Document, page_index: int, dpi: int) -> str:
    """Render a PDF page to PNG, return base64-encoded string."""
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    buf = BytesIO(pix.tobytes("png"))
    return base64.standard_b64encode(buf.getvalue()).decode()


def read_pdf(
    path: str,
    max_pages: int = DEFAULT_MAX_PAGES,
    dpi: int = DEFAULT_DPI,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Read a datasheet PDF and return a list of content items for Claude.

    Each item is either:
      {"type": "text", "text": "..."}   — text + markdown tables from the page
      {"type": "image", "data": "..."}  — base64 PNG for diagram-only pages

    Returns (content_items, truncation_warning_or_None).
    """
    with pdfplumber.open(path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
        pages_tables = [p.extract_tables() or [] for p in pdf.pages]
        pages_chars = [len(p.chars) for p in pdf.pages]

    selected, warning = _select_pages(pages_text, max_pages)

    doc = fitz.open(path)
    content_items: list[dict[str, Any]] = []

    for idx in selected:
        text = pages_text[idx].strip()
        tables = pages_tables[idx]
        char_count = pages_chars[idx]
        page_types = _detect_page_types(text)
        label = ", ".join(page_types) if page_types else "header"

        if char_count < DIAGRAM_CHAR_THRESHOLD:
            # Diagram/schematic page — return as image
            img_b64 = _render_page_image(doc, idx, dpi)
            content_items.append({
                "type": "image",
                "page": idx + 1,
                "label": label,
                "data": img_b64,
            })
        else:
            # Text-rich page — return formatted text + markdown tables
            parts = [f"--- Page {idx + 1} [{label}] ---", "", text]
            for i, table in enumerate(tables):
                md = _table_to_markdown(table)
                if md:
                    parts.append(f"\n**Table {i + 1}:**\n{md}")
            content_items.append({
                "type": "text",
                "page": idx + 1,
                "label": label,
                "text": "\n".join(parts),
            })

    doc.close()
    return content_items, warning
