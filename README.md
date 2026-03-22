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

## Usage without MCP (Claude Code + Bash tool)

If you'd rather not configure an MCP server, Claude Code can run the CLI directly via its Bash tool. Tell Claude:

> "Use `python /path/to/datasheet.py` to extract `/path/to/component.pdf`"

Or install the skill (`cp skills/extract-datasheet.md ~/.claude/skills/`) and update the path at the top — Claude will handle the two-step workflow automatically whenever you ask about a datasheet.

### Step 1 — extract text and tables

```bash
python datasheet.py read /path/to/component.pdf
```

Prints extracted text and Markdown-formatted tables to stdout. Diagram/schematic pages are noted but skipped (images can't be printed to terminal — use MCP for those).

### Step 2 — validate and render

```bash
python datasheet.py record '<json>'
```

Pass a JSON string with the extracted data. Pydantic validates it and prints formatted Markdown to stdout.

**Example:**
```bash
python datasheet.py record '{
  "part_number": "LM358",
  "manufacturer": "Texas Instruments",
  "description": "Dual general-purpose operational amplifier",
  "features": ["Wide supply voltage range", "Low supply current drain"],
  "pins": [{"number": "1", "name": "OUT1", "type": "O", "description": "Output 1"}],
  "absolute_max_ratings": [],
  "specs": [],
  "package": {"name": "SOIC-8", "dimensions": null, "theta_ja": null},
  "truth_tables": [],
  "typical_circuits": []
}'
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASHEET_MAX_PAGES` | `20` | Max relevant pages to process (0 = unlimited) |
| `DATASHEET_DPI` | `150` | DPI for rendering diagram pages as images (MCP only) |

> **Note:** Diagram page images are only available via the MCP server. The CLI notes which pages are diagrams but cannot render them.

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
