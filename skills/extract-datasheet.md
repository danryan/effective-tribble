# Extract Datasheet Skill

Extract structured information from an electronic component datasheet PDF using the `datasheets` MCP server.

## When to use

When the user provides a path to a PDF datasheet and asks about the component — specs, pinout, features, package, summary, etc.

## Workflow

### Step 1 — Read the PDF

```
read_datasheet(path="/path/to/component.pdf")
```

Returns page text, Markdown-formatted tables, and images for diagram/schematic pages. Read all content carefully.

### Step 2 — Record the extraction

```
record_datasheet(data='{ ... }')
```

Pass a JSON string with everything you extracted. Pydantic validates it and returns consistent Markdown. **Always call this — never format the output yourself.**

## JSON schema

```json
{
  "part_number": "LM358",
  "manufacturer": "Texas Instruments",
  "description": "Dual operational amplifier...",
  "features": ["Internally frequency compensated", "Wide supply voltage range: 3V to 32V"],
  "pins": [
    { "number": "1", "name": "OUT1", "type": "O", "description": "Output of amplifier 1" }
  ],
  "absolute_max_ratings": [
    { "parameter": "Supply Voltage", "min": null, "typ": null, "max": "36", "unit": "V", "conditions": null }
  ],
  "specs": [
    { "parameter": "Input Offset Voltage", "min": null, "typ": "2", "max": "7", "unit": "mV", "conditions": "VS=5V" }
  ],
  "package": { "name": "SOIC-8", "dimensions": "4.9mm x 3.9mm", "theta_ja": "125" },
  "truth_tables": [
    { "name": "Logic Function Table", "rows": [{ "inputs": {"A": "L"}, "outputs": {"Y": "H"}, "notes": null }] }
  ],
  "typical_circuits": [
    { "name": "Typical Application", "description": "Non-inverting amplifier with R1/R2 feedback..." }
  ]
}
```

## Field notes

- **pin.type**: `"I"`, `"O"`, `"I/O"`, `"Power"`, `"GND"`, or `"NC"`
- **specs vs absolute_max_ratings**: Absolute max = never-exceed limits; specs = operating conditions
- **typical_circuits**: For diagram image pages, describe the circuit in plain English
- **All numeric values as strings**: `"3.3"` not `3.3`
- **Missing sections**: `[]` for lists, `null` for scalars
- If `read_datasheet` returns a truncation warning, mention it and offer to re-run with higher `max_pages`
