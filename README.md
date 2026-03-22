# Datasheets Extraction Tool

Extracts structured information from electronic component datasheet PDFs.

- **MCP server** — returns PDF content (text, tables, diagram images) for Claude to interpret and format
- **CLI** — standalone heuristic extraction using pdfplumber, no AI required

**No Anthropic API key required.**

## Requirements

- Python 3.11+

## Installation

```bash
git clone <this-repo>
cd effective-tribble
pip install -e .
```

## MCP server (Claude Code)

### 1. Add to `~/.claude/settings.json`

```json
{
  "mcpServers": {
    "datasheets": {
      "command": "python",
      "args": ["/absolute/path/to/effective-tribble/server.py"],
      "env": {
        "DATASHEET_MAX_PAGES": "20",
        "DATASHEET_DPI": "150"
      }
    }
  }
}
```

Restart Claude Code after saving.

### 2. Install the skill

```bash
cp skills/extract-datasheet.md ~/.claude/skills/
```

Claude will automatically call `extract_datasheet` and produce structured Markdown when you ask about a component PDF.

### Tool

**`extract_datasheet(path, max_pages=20)`** — returns page text, Markdown-formatted tables, and images for diagram/schematic pages.

## CLI (standalone, no AI)

Uses pdfplumber heuristics to extract what it can — pinout tables, spec tables, bullet-point features, part number. No AI, best-effort.

```bash
python datasheet.py /path/to/component.pdf
```

Prints formatted Markdown to stdout.

> Diagram/schematic pages are skipped in CLI mode. Use the MCP server for full extraction including schematics.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASHEET_MAX_PAGES` | `20` | Max relevant pages to process (0 = unlimited) |
| `DATASHEET_DPI` | `150` | DPI for rendering diagram pages as images (MCP only) |

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

Sections absent from the datasheet are omitted.
