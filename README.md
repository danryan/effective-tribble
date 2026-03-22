# Datasheets Extraction Tool

An MCP server that extracts structured information from electronic component datasheet PDFs and returns clean Markdown. Uses a hybrid approach: pdfplumber for fast text extraction and Claude vision for complex tables, pinouts, and schematics.

## What it extracts

- Part number, manufacturer, description
- Feature list
- Pin configuration (pinout table)
- Absolute maximum ratings
- Electrical characteristics (specs table)
- Truth tables / logic tables
- Package information (type, dimensions, thermal resistance)
- Typical application circuit descriptions

## Requirements

- Python 3.11+
- An Anthropic API key (`ANTHROPIC_API_KEY`)

## Installation

```bash
git clone <this-repo>
cd effective-tribble
pip install -e .
```

## MCP Server Setup (Claude Code)

Add the server to your Claude Code MCP configuration. Edit `~/.claude/settings.json` (user-level) or `.claude/settings.json` (project-level):

```json
{
  "mcpServers": {
    "datasheets": {
      "command": "python",
      "args": ["/absolute/path/to/effective-tribble/server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "DATASHEET_MAX_PAGES": "20",
        "DATASHEET_DPI": "150",
        "DATASHEET_MODEL": "claude-sonnet-4-6"
      }
    }
  }
}
```

After saving, restart Claude Code. You should see `datasheets` in your MCP servers list.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `DATASHEET_MAX_PAGES` | `20` | Default page cap for Claude vision calls |
| `DATASHEET_DPI` | `150` | PDF render resolution (increase for dense tables) |
| `DATASHEET_MODEL` | `claude-sonnet-4-6` | Claude model to use for extraction |

## Available MCP Tools

### `extract_datasheet`

Full extraction — all sections from the PDF.

```
extract_datasheet(path: str, max_pages: int = 20) -> str
```

### `extract_datasheet_section`

Targeted extraction — only a specific section. Faster and cheaper.

```
extract_datasheet_section(path: str, section: str, max_pages: int = 20) -> str
```

Valid `section` values: `pinout`, `specs`, `abs_max`, `features`, `description`, `circuits`, `package`, `truth_tables`

## Installing the Claude Skill

The `skills/extract-datasheet.md` file teaches Claude when and how to use this tool. Copy it to your personal Claude skills directory:

```bash
cp skills/extract-datasheet.md ~/.claude/skills/
```

Once installed, Claude will automatically invoke the MCP tool when you hand it a PDF and ask about a component.

## Usage example

In Claude Code (after MCP server is configured):

> "Extract the datasheet at /path/to/TPS62840.pdf"

Or more specifically:

> "What's the pinout of /path/to/LM358.pdf?"

## Running the server manually (for testing)

```bash
# Start the server in stdio mode (as Claude Code expects)
python server.py

# Or using the mcp CLI
mcp run server.py
```

## Output format

The tool returns Markdown with this structure (sections omitted if not found):

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
