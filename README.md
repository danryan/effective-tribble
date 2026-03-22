# Datasheets Extraction Tool

An MCP server for extracting structured information from electronic component datasheet PDFs. Returns clean, consistent Markdown.

**No Anthropic API key required** — Claude Code does the interpretation natively. The server handles only the mechanical PDF work.

## How it works

1. `read_datasheet` opens the PDF, extracts text and Markdown-formatted tables (pdfplumber), and renders diagram/schematic pages as images (PyMuPDF)
2. Claude reads the returned content and extracts all component information
3. `record_datasheet` validates Claude's structured JSON against the Pydantic schema and renders consistent Markdown

## What it extracts

- Part number, manufacturer, description
- Feature list
- Pin configuration table
- Absolute maximum ratings
- Electrical characteristics (specs table)
- Truth tables / logic tables
- Package information (type, dimensions, thermal resistance)
- Typical application circuit descriptions

## Requirements

- Python 3.11+

## Installation

```bash
git clone <this-repo>
cd effective-tribble
pip install -e .
```

## MCP Server Setup

Add to your Claude Code MCP config. Edit `~/.claude/settings.json` (user-level) or `.claude/settings.json` (project-level):

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

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATASHEET_MAX_PAGES` | `20` | Default page cap (0 = unlimited) |
| `DATASHEET_DPI` | `150` | PDF render DPI for diagram pages |

## MCP Tools

### `read_datasheet`
Reads the PDF and returns page content (text, tables, images) for Claude to interpret.

```
read_datasheet(path: str, max_pages: int = 20)
```

### `record_datasheet`
Validates Claude's structured extraction and renders it as Markdown.

```
record_datasheet(data: str)  # JSON string matching the Datasheet schema
```

## Installing the Claude Skill

The skill file tells Claude when and how to use both tools. Copy it to your personal Claude skills directory:

```bash
cp skills/extract-datasheet.md ~/.claude/skills/
```

Once installed, Claude automatically invokes the two-step workflow when you ask about a component PDF.

## Usage

In Claude Code (after MCP server is configured and skill is installed):

> "Extract the datasheet at /path/to/TPS62840.pdf"
> "What's the pinout of /path/to/LM358.pdf?"
> "Summarize /path/to/STM32F4.pdf"

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

## Running the server manually

```bash
python server.py
# or
mcp run server.py
```
