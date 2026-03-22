# Extract Datasheet Skill

Use the `datasheets` MCP server to extract structured information from electronic component datasheets.

## When to use this skill

Use this skill when the user:
- Provides a path to a PDF datasheet and asks about the component
- Asks for specs, pinout, or features of a component and has a local PDF
- Wants to understand or summarize a datasheet

## Tools available

The `datasheets` MCP server provides two tools:

### `extract_datasheet`
Extracts all sections from a datasheet PDF and returns formatted Markdown.

```
extract_datasheet(path: str, max_pages: int = 20)
```

Use this for a comprehensive extraction when the user wants full information.

### `extract_datasheet_section`
Extracts only a specific section — faster for targeted questions.

```
extract_datasheet_section(path: str, section: str, max_pages: int = 20)
```

Valid section values:
- `pinout` — pin configuration table
- `specs` — electrical characteristics (operating conditions)
- `abs_max` — absolute maximum ratings
- `features` — feature bullet list
- `description` — component description
- `circuits` — typical application circuit descriptions
- `package` — package type, dimensions, thermal resistance
- `truth_tables` — logic truth tables / function tables

## Usage examples

**User asks:** "What's the pinout of this IC?" (provides a PDF path)
```
extract_datasheet_section(path="/path/to/datasheet.pdf", section="pinout")
```

**User asks:** "Give me a summary of this datasheet"
```
extract_datasheet(path="/path/to/datasheet.pdf")
```

**User asks:** "What are the absolute max ratings?"
```
extract_datasheet_section(path="/path/to/datasheet.pdf", section="abs_max")
```

## Tips

- If the user says "this datasheet" without a path, ask them for the PDF file path.
- For large datasheets (>50 pages), you can increase `max_pages` if important sections seem missing.
- The tool returns Markdown — you can present it directly or summarize key points.
- If a section returns "*(not found)*", that section likely isn't in the datasheet or wasn't detected.
