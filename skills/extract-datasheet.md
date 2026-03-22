# Extract Datasheet Skill

Use the `datasheets` MCP server to extract structured information from electronic component datasheets and produce consistent Markdown output.

## When to use

Use this skill when the user:
- Provides a path to a PDF datasheet and asks about the component
- Asks for specs, pinout, features, or any other datasheet information
- Wants to summarize or understand a component from a local PDF

## Workflow

Always follow this two-step process:

### Step 1 — Read the PDF

Call `read_datasheet` with the PDF path:

```
read_datasheet(path="/path/to/component.pdf")
```

This returns page content — text, Markdown tables, and images for diagram pages. Read everything carefully.

### Step 2 — Record the extraction

Once you've read and understood the content, call `record_datasheet` with a JSON string containing everything you extracted. This validates the data and produces consistent Markdown output.

```
record_datasheet(data='{ ... }')
```

**Always call `record_datasheet` — never format the output yourself.** This ensures consistent structure across all datasheets.

## JSON schema for record_datasheet

```json
{
  "part_number": "LM358",
  "manufacturer": "Texas Instruments",
  "description": "Dual operational amplifier...",
  "features": [
    "Internally frequency compensated for unity gain",
    "Wide supply voltage range: 3V to 32V single supply"
  ],
  "pins": [
    { "number": "1", "name": "OUT1", "type": "O", "description": "Output of amplifier 1" },
    { "number": "8", "name": "VCC", "type": "Power", "description": "Positive supply voltage" }
  ],
  "absolute_max_ratings": [
    { "parameter": "Supply Voltage", "min": null, "typ": null, "max": "36", "unit": "V", "conditions": null }
  ],
  "specs": [
    { "parameter": "Input Offset Voltage", "min": null, "typ": "2", "max": "7", "unit": "mV", "conditions": "VS=5V" }
  ],
  "package": {
    "name": "SOIC-8",
    "dimensions": "4.9mm x 3.9mm",
    "theta_ja": "125"
  },
  "truth_tables": [
    {
      "name": "Logic Function Table",
      "rows": [
        { "inputs": { "A": "L", "B": "L" }, "outputs": { "Y": "L" }, "notes": null }
      ]
    }
  ],
  "typical_circuits": [
    {
      "name": "Typical Application Circuit",
      "description": "Non-inverting amplifier configuration with gain set by R1/R2 feedback network..."
    }
  ]
}
```

## Field guidance

- **pin.type**: Use `"I"` (input), `"O"` (output), `"I/O"` (bidirectional), `"Power"`, `"GND"`, or `"NC"` (no connect)
- **specs vs absolute_max_ratings**: Absolute max are the never-exceed limits; specs are the operating/recommended conditions
- **typical_circuits**: For diagram/schematic image pages, describe the circuit in plain English — component values, topology, signal flow
- **Omit empty fields**: Use empty lists `[]` for missing sections; use `null` for optional scalar fields
- **All values as strings**: Even numeric values like `"3.3"` or `"100"` should be strings in the JSON

## Tips

- If the user asks for a specific section only (e.g. "just the pinout"), still call both tools but mention only the relevant section in your response
- If `read_datasheet` returns a truncation warning, mention it to the user and offer to re-run with a higher `max_pages`
- Part numbers are usually on the first page, often in a large font or header
- Features are typically a bullet list near the top of the first page
- If a table header row is ambiguous, use your best judgment for column names
