"""
Tests for datasheet.py

pdfplumber and pymupdf are stubbed out via sys.modules so they are never
actually imported (the installed versions have a broken _cffi_backend).
All tests exercise the pure-Python logic only.
"""
import sys
from unittest.mock import MagicMock, patch

# Stub broken native deps before importing the module under test
sys.modules.setdefault("pdfplumber", MagicMock())
sys.modules.setdefault("pymupdf", MagicMock())

import pytest
from datasheet import (
    _detect_page_types,
    _select_pages,
    _table_to_markdown,
    _is_pin_table,
    _is_spec_table,
    _parse_pin_table,
    _parse_spec_table,
    _heuristic_extract,
    render,
    read_pdf,
    Datasheet,
    Pin,
    Spec,
    Package,
    TruthTable,
    TruthTableRow,
    Circuit,
)


# ── _detect_page_types ────────────────────────────────────────────────────────

class TestDetectPageTypes:
    def test_pinout_keyword(self):
        assert "pinout" in _detect_page_types("Pinout Description\nVCC GND")

    def test_abs_max_keyword(self):
        assert "abs_max" in _detect_page_types("Absolute Maximum Ratings")

    def test_specs_keyword(self):
        assert "specs" in _detect_page_types("DC Electrical Characteristics")

    def test_truth_table_keyword(self):
        assert "truth_table" in _detect_page_types("Truth Table for mode select")

    def test_circuit_keyword(self):
        assert "circuit" in _detect_page_types("Typical Application Circuit")

    def test_package_keyword(self):
        assert "package" in _detect_page_types("Package Dimensions")

    def test_multiple_labels(self):
        labels = _detect_page_types("Pin Configuration\nAbsolute Maximum Ratings")
        assert "pinout" in labels
        assert "abs_max" in labels

    def test_irrelevant_text(self):
        assert _detect_page_types("Hello world. Nothing to see here.") == []

    def test_case_insensitive(self):
        assert "specs" in _detect_page_types("ELECTRICAL CHARACTERISTICS")

    def test_empty_string(self):
        assert _detect_page_types("") == []


# ── _select_pages ─────────────────────────────────────────────────────────────

class TestSelectPages:
    def test_always_includes_first_two_pages(self):
        pages = ["intro", "overview", "unrelated", "unrelated"]
        selected, _ = _select_pages(pages, max_pages=0)
        assert 0 in selected
        assert 1 in selected

    def test_adds_relevant_pages(self):
        pages = ["intro", "overview", "Pinout Description", "random"]
        selected, _ = _select_pages(pages, max_pages=0)
        assert 2 in selected
        assert 3 not in selected

    def test_no_duplicates(self):
        pages = ["Pinout intro", "overview", "abs max"]
        selected, _ = _select_pages(pages, max_pages=0)
        assert len(selected) == len(set(selected))

    def test_max_pages_cap(self):
        pages = [f"Electrical characteristics page {i}" for i in range(10)]
        selected, warning = _select_pages(pages, max_pages=3)
        assert len(selected) <= 3
        assert warning is not None
        assert "3" in warning

    def test_no_cap_when_zero(self):
        pages = [f"Electrical characteristics {i}" for i in range(6)]
        selected, warning = _select_pages(pages, max_pages=0)
        assert warning is None
        assert len(selected) == 6

    def test_single_page_pdf(self):
        selected, _ = _select_pages(["intro"], max_pages=0)
        assert selected == [0]

    def test_warning_contains_skipped_count(self):
        pages = [f"Electrical characteristics {i}" for i in range(8)]
        selected, warning = _select_pages(pages, max_pages=3)
        skipped = 8 - 3
        assert str(skipped) in warning


# ── _table_to_markdown ────────────────────────────────────────────────────────

class TestTableToMarkdown:
    def test_basic_table(self):
        table = [["Pin", "Name"], ["1", "VCC"], ["2", "GND"]]
        md = _table_to_markdown(table)
        assert "| Pin | Name |" in md
        assert "| --- | --- |" in md
        assert "| 1 | VCC |" in md
        assert "| 2 | GND |" in md

    def test_none_cells_become_empty(self):
        table = [["A", "B"], [None, "x"]]
        md = _table_to_markdown(table)
        assert "|  | x |" in md

    def test_row_shorter_than_header_padded(self):
        table = [["A", "B", "C"], ["1"]]
        md = _table_to_markdown(table)
        assert "| 1 |  |  |" in md

    def test_empty_table_returns_empty_string(self):
        assert _table_to_markdown([]) == ""

    def test_header_only_renders_separator(self):
        table = [["Col1", "Col2"]]
        md = _table_to_markdown(table)
        assert "| Col1 | Col2 |" in md
        assert "| --- | --- |" in md


# ── _is_pin_table / _is_spec_table ───────────────────────────────────────────

class TestIsTableClassifiers:
    def test_pin_table_pin_name(self):
        assert _is_pin_table(["pin", "name", "type"])

    def test_pin_table_no_signal(self):
        assert _is_pin_table(["no.", "signal", "description"])

    def test_pin_table_hash_symbol(self):
        assert _is_pin_table(["#", "symbol", "function"])

    def test_pin_table_false_for_spec(self):
        assert not _is_pin_table(["parameter", "min", "max"])

    def test_spec_table_min_max(self):
        assert _is_spec_table(["parameter", "min", "typ", "max", "unit"])

    def test_spec_table_characteristic_value(self):
        assert _is_spec_table(["characteristic", "value"])

    def test_spec_table_symbol_min(self):
        assert _is_spec_table(["symbol", "min", "max"])

    def test_spec_table_false_for_pin(self):
        assert not _is_spec_table(["pin", "name", "type"])


# ── _parse_pin_table ──────────────────────────────────────────────────────────

class TestParsePinTable:
    def _make_table(self, rows):
        return rows

    def test_basic_extraction(self):
        table = [
            ["pin", "name", "type", "description"],
            ["1", "VCC", "Power", "Supply voltage"],
            ["2", "GND", "GND", "Ground"],
        ]
        header = [c.lower() for c in table[0]]
        pins = _parse_pin_table(table, header)
        assert len(pins) == 2
        assert pins[0]["number"] == "1"
        assert pins[0]["name"] == "VCC"
        assert pins[0]["type"] == "Power"
        assert pins[0]["description"] == "Supply voltage"

    def test_skips_empty_pin_number(self):
        table = [
            ["pin", "name"],
            ["1", "VCC"],
            [None, "continued"],
            ["", "also skipped"],
        ]
        header = [c.lower() for c in table[0]]
        pins = _parse_pin_table(table, header)
        assert len(pins) == 1

    def test_no_type_or_desc_columns(self):
        table = [
            ["pin", "name"],
            ["1", "CLK"],
        ]
        header = [c.lower() for c in table[0]]
        pins = _parse_pin_table(table, header)
        assert pins[0]["type"] == ""
        assert pins[0]["description"] == ""

    def test_signal_column_used_as_name(self):
        table = [
            ["no.", "signal"],
            ["1", "RESET"],
        ]
        header = [c.lower() for c in table[0]]
        pins = _parse_pin_table(table, header)
        assert pins[0]["name"] == "RESET"


# ── _parse_spec_table ─────────────────────────────────────────────────────────

class TestParseSpecTable:
    def test_basic_extraction(self):
        table = [
            ["parameter", "min", "typ", "max", "unit", "conditions"],
            ["Supply Voltage", "3.0", "3.3", "3.6", "V", "Normal op"],
        ]
        header = [c.lower() for c in table[0]]
        specs = _parse_spec_table(table, header)
        assert len(specs) == 1
        assert specs[0]["parameter"] == "Supply Voltage"
        assert specs[0]["min"] == "3.0"
        assert specs[0]["typ"] == "3.3"
        assert specs[0]["max"] == "3.6"
        assert specs[0]["unit"] == "V"
        assert specs[0]["conditions"] == "Normal op"

    def test_empty_cells_become_none(self):
        table = [
            ["parameter", "min", "typ", "max"],
            ["Input High", None, None, "5.0"],
        ]
        header = [c.lower() for c in table[0]]
        specs = _parse_spec_table(table, header)
        assert specs[0]["min"] is None
        assert specs[0]["typ"] is None
        assert specs[0]["max"] == "5.0"

    def test_skips_empty_parameter(self):
        table = [
            ["parameter", "min", "max"],
            ["Valid", "0", "5"],
            [None, "1", "2"],
            ["", "3", "4"],
        ]
        header = [c.lower() for c in table[0]]
        specs = _parse_spec_table(table, header)
        assert len(specs) == 1

    def test_missing_optional_columns_are_none(self):
        table = [
            ["parameter", "value"],
            ["Output Current", "50"],
        ]
        header = [c.lower() for c in table[0]]
        specs = _parse_spec_table(table, header)
        assert specs[0]["min"] is None
        assert specs[0]["unit"] is None


# ── _heuristic_extract ────────────────────────────────────────────────────────

def _make_page(page_num, text, tables=None, label="header", is_diagram=False):
    return {
        "page": page_num,
        "label": label,
        "text": text,
        "tables": tables or [],
        "char_count": len(text),
        "is_diagram": is_diagram,
        "img_data": None,
    }


class TestHeuristicExtract:
    def test_part_number_detected(self):
        page = _make_page(1, "LM358\nDual Operational Amplifier\nTexas Instruments")
        result = _heuristic_extract([page])
        assert result["part_number"] == "LM358"

    def test_part_number_alphanumeric(self):
        page = _make_page(1, "74HC00\nQuad 2-Input NAND Gate")
        result = _heuristic_extract([page])
        assert result["part_number"] == "74HC00"

    def test_part_number_only_from_early_pages(self):
        page3 = _make_page(3, "SN74LS00\nsome other text", label="pinout")
        result = _heuristic_extract([page3])
        assert result["part_number"] == ""

    def test_description_first_long_line(self):
        text = "LM358\n" + "A" * 60
        page = _make_page(1, text)
        result = _heuristic_extract([page])
        assert result["description"] == "A" * 60

    def test_description_skips_bullet_lines(self):
        text = "• Short bullet\n" + "Long description line: " + "x" * 40
        page = _make_page(1, text)
        result = _heuristic_extract([page])
        assert result["description"].startswith("Long description")

    def test_features_extracted(self):
        text = "• Low power consumption\n• Wide voltage range"
        page = _make_page(1, text)
        result = _heuristic_extract([page])
        assert "Low power consumption" in result["features"]
        assert "Wide voltage range" in result["features"]

    def test_features_deduplicated(self):
        text = "• Same feature\n• Same feature"
        page = _make_page(1, text)
        result = _heuristic_extract([page])
        assert result["features"].count("Same feature") == 1

    def test_diagram_pages_skipped(self):
        page = _make_page(1, "LM741", is_diagram=True)
        result = _heuristic_extract([page])
        assert result["part_number"] == ""

    def test_pin_table_parsed(self):
        table = [
            ["pin", "name", "type"],
            ["1", "VCC", "Power"],
            ["2", "GND", "GND"],
        ]
        page = _make_page(1, "Pin Description", tables=[table], label="pinout")
        result = _heuristic_extract([page])
        assert len(result["pins"]) == 2
        assert result["pins"][0]["name"] == "VCC"

    def test_spec_table_goes_to_specs(self):
        table = [
            ["parameter", "min", "max"],
            ["Voltage", "0", "5"],
        ]
        page = _make_page(2, "Electrical Characteristics", tables=[table], label="specs")
        result = _heuristic_extract([page])
        assert len(result["specs"]) == 1

    def test_spec_table_on_abs_max_page(self):
        table = [
            ["parameter", "min", "max"],
            ["Supply Voltage", "−0.3", "6"],
        ]
        page = _make_page(2, "Absolute Maximum Ratings", tables=[table], label="abs_max")
        result = _heuristic_extract([page])
        assert len(result["absolute_max_ratings"]) == 1
        assert result["specs"] == []


# ── render ────────────────────────────────────────────────────────────────────

class TestRender:
    def test_title_with_manufacturer(self):
        ds = Datasheet(part_number="LM358", manufacturer="TI")
        assert "# LM358 — TI" in render(ds)

    def test_title_without_manufacturer(self):
        ds = Datasheet(part_number="LM358")
        assert "# LM358" in render(ds)
        assert "—" not in render(ds)

    def test_unknown_part_fallback(self):
        ds = Datasheet()
        assert "# Unknown Part" in render(ds)

    def test_description_section(self):
        ds = Datasheet(part_number="X", description="Dual op-amp")
        out = render(ds)
        assert "## Description" in out
        assert "Dual op-amp" in out

    def test_no_description_section_when_empty(self):
        ds = Datasheet(part_number="X")
        assert "## Description" not in render(ds)

    def test_features_section(self):
        ds = Datasheet(part_number="X", features=["Low power", "Fast switching"])
        out = render(ds)
        assert "## Features" in out
        assert "- Low power" in out
        assert "- Fast switching" in out

    def test_pin_configuration_section(self):
        ds = Datasheet(part_number="X", pins=[Pin(number="1", name="VCC", type="Power")])
        out = render(ds)
        assert "## Pin Configuration" in out
        assert "| 1 | VCC | Power |" in out

    def test_no_pin_section_when_empty(self):
        ds = Datasheet(part_number="X")
        assert "## Pin Configuration" not in render(ds)

    def test_abs_max_section(self):
        ds = Datasheet(part_number="X", absolute_max_ratings=[Spec(parameter="Vcc", max="6")])
        out = render(ds)
        assert "## Absolute Maximum Ratings" in out
        assert "Vcc" in out

    def test_electrical_chars_section(self):
        ds = Datasheet(part_number="X", specs=[Spec(parameter="Ib", typ="100", unit="nA")])
        out = render(ds)
        assert "## Electrical Characteristics" in out
        assert "Ib" in out

    def test_truth_table_section(self):
        tt = TruthTable(
            name="Mode Select",
            rows=[TruthTableRow(inputs={"A": "0", "B": "0"}, outputs={"Y": "0"})],
        )
        ds = Datasheet(part_number="X", truth_tables=[tt])
        out = render(ds)
        assert "## Truth Tables" in out
        assert "### Mode Select" in out
        assert "| A | B | Y |" in out

    def test_truth_table_with_notes(self):
        tt = TruthTable(
            name="T",
            rows=[TruthTableRow(inputs={"A": "1"}, outputs={"Y": "0"}, notes="see text")],
        )
        ds = Datasheet(part_number="X", truth_tables=[tt])
        out = render(ds)
        assert "Notes" in out
        assert "see text" in out

    def test_package_section(self):
        ds = Datasheet(part_number="X", package=Package(name="SOIC-8", theta_ja="125"))
        out = render(ds)
        assert "## Package Information" in out
        assert "SOIC-8" in out
        assert "125" in out

    def test_typical_circuits_section(self):
        ds = Datasheet(
            part_number="X",
            typical_circuits=[Circuit(name="Inverting Amp", description="Gain = −R2/R1")]
        )
        out = render(ds)
        assert "## Typical Application Circuits" in out
        assert "Inverting Amp" in out


# ── read_pdf ──────────────────────────────────────────────────────────────────

class TestReadPdf:
    def _raw_text_page(self, page_num=1, label="header", text="Sample text", tables=None):
        return {
            "page": page_num,
            "label": label,
            "text": text,
            "tables": tables or [],
            "char_count": len(text),
            "is_diagram": False,
            "img_data": None,
        }

    def _raw_diagram_page(self, page_num=2, label="circuit"):
        return {
            "page": page_num,
            "label": label,
            "text": "",
            "tables": [],
            "char_count": 0,
            "is_diagram": True,
            "img_data": "base64encodeddata==",
        }

    def test_text_page_produces_text_item(self):
        raw = [self._raw_text_page()]
        with patch("datasheet._extract_raw_pages", return_value=(raw, None)):
            items, warning = read_pdf("fake.pdf")
        assert len(items) == 1
        assert items[0]["type"] == "text"
        assert "--- Page 1 [header] ---" in items[0]["text"]
        assert warning is None

    def test_diagram_page_produces_image_item(self):
        raw = [self._raw_diagram_page()]
        with patch("datasheet._extract_raw_pages", return_value=(raw, None)):
            items, warning = read_pdf("fake.pdf")
        assert items[0]["type"] == "image"
        assert items[0]["data"] == "base64encodeddata=="

    def test_table_included_in_text_item(self):
        table = [["Pin", "Name"], ["1", "VCC"]]
        raw = [self._raw_text_page(tables=[table])]
        with patch("datasheet._extract_raw_pages", return_value=(raw, None)):
            items, _ = read_pdf("fake.pdf")
        assert "Table 1:" in items[0]["text"]
        assert "| Pin | Name |" in items[0]["text"]

    def test_warning_passed_through(self):
        raw = [self._raw_text_page()]
        with patch("datasheet._extract_raw_pages", return_value=(raw, "5 pages skipped")):
            items, warning = read_pdf("fake.pdf")
        assert warning == "5 pages skipped"

    def test_empty_raw_pages(self):
        with patch("datasheet._extract_raw_pages", return_value=([], None)):
            items, _ = read_pdf("fake.pdf")
        assert items == []

    def test_mixed_pages(self):
        raw = [self._raw_text_page(page_num=1), self._raw_diagram_page(page_num=2)]
        with patch("datasheet._extract_raw_pages", return_value=(raw, None)):
            items, _ = read_pdf("fake.pdf")
        assert items[0]["type"] == "text"
        assert items[1]["type"] == "image"
