# Datasheets Extraction Tool

A CLI tool for extracting structured information from electronic component datasheet PDFs. Designed for use with Claude Code.

Uses pdfplumber for clean text and Markdown table extraction, Pydantic for schema validation, and outputs consistent Markdown.

**No API key required.**

## Requirements

- Python 3.11+

## Installation

```bash
git clone <this-repo>
cd effective-tribble
pip install -e .
```

## Usage

### Step 1 — Read a PDF

```bash
python datasheet.py read /path/to/component.pdf
```

Outputs extracted text and Markdown-formatted tables from relevant pages to stdout. Diagram/schematic pages are noted but not extracted (no text to extract).

### Step 2 — Validate and render

```bash
python datasheet.py record '<json>'
```

Pass a JSON string matching the schema below. Pydantic validates it and outputs formatted Markdown.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASHEET_MAX_PAGES` | `20` | Max relevant pages to process (0 = unlimited) |
| `DATASHEET_DPI` | `150` | Render DPI (currently unused; reserved for future image support) |

## Schema

```json
{
  "part_number": "string",
  "manufacturer": "string",
  "description": "string",
  "features": ["string"],
  "pins": [
    { "number": "string", "name": "string", "type": "string", "description": "string" }
  ],
  "absolute_max_ratings": [
    { "parameter": "string", "min": "string|null", "typ": "string|null",
      "max": "string|null", "unit": "string|null", "conditions": "string|null" }
  ],
  "specs": ["same as absolute_max_ratings"],
  "package": { "name": "string", "dimensions": "string|null", "theta_ja": "string|null" },
  "truth_tables": [
    { "name": "string", "rows": [{ "inputs": {}, "outputs": {}, "notes": "string|null" }] }
  ],
  "typical_circuits": [
    { "name": "string", "description": "string" }
  ]
}
```

## Installing the Claude skill

The skill file tells Claude the two-step workflow. Copy it to your personal Claude skills directory:

```bash
cp skills/extract-datasheet.md ~/.claude/skills/
```

Then update the path in the skill file to match where you installed this tool:

```bash
# Edit the script path in the skill file
sed -i 's|/path/to/datasheet.py|'$(pwd)'/datasheet.py|g' ~/.claude/skills/extract-datasheet.md
```

Once installed, Claude automatically runs the two-step workflow when you ask about a component PDF.

## Output format

```markdown
# PART_NUMBER — Manufacturer

## Description
## Features
## Pin Configuration
## Absolute Maximum Ratings
## Electrical Characteristics
## Truth Tables
## Package Information
## Typical Application Circuits
```

Sections not found in the datasheet are omitted.
