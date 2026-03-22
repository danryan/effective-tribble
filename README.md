# Datasheets Extraction Tool

Extracts structured information from electronic component datasheet PDFs and renders consistent Markdown. Works as a standalone CLI or as an MCP server for Claude Code.

**No Anthropic API key required.**

## How it works

1. `read` / `read_datasheet` — pdfplumber extracts text and Markdown tables; PyMuPDF renders diagram pages as images
2. Claude reads the content and extracts all component information
3. `record` / `record_datasheet` — Pydantic validates Claude's structured JSON, renders consistent Markdown

## Requirements

- Python 3.11+

## Installation

```bash
git clone <this-repo>
cd effective-tribble
pip install -e .
```

## CLI usage

```bash
# Step 1 — extract text and tables from PDF
python datasheet.py read /path/to/component.pdf

# Step 2 — validate and render structured extraction
python datasheet.py record '{"part_number": "LM358", "manufacturer": "TI", ...}'
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASHEET_MAX_PAGES` | `20` | Max relevant pages to process (0 = unlimited) |
| `DATASHEET_DPI` | `150` | DPI for rendering diagram pages as images |

## MCP server setup (Claude Code)

Add to `~/.claude/settings.json`:

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

## Install the Claude skill

```bash
cp skills/extract-datasheet.md ~/.claude/skills/
```

Claude will then automatically run the two-step workflow when you ask about a component PDF.

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
