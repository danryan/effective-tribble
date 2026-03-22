# Extract Datasheet Skill

Extract structured information from an electronic component datasheet PDF using a two-step CLI workflow.

## When to use

When the user provides a path to a PDF datasheet and asks about the component — specs, pinout, features, summary, etc.

## Workflow

### Step 1 — Read the PDF

```bash
python /path/to/datasheet.py read /path/to/component.pdf
```

This outputs extracted text and Markdown-formatted tables from relevant pages. Read the output carefully — it contains all the raw information you need.

### Step 2 — Record the extraction

Build a JSON object from what you read, then validate and render it:

```bash
python /path/to/datasheet.py record '<json>'
```

**Always call `record` — never format the output yourself.** This validates the data with Pydantic and ensures consistent Markdown structure.

## JSON schema

```json
{
  "part_number": "LM358",
  "manufacturer": "Texas Instruments",
  "description": "Dual operational amplifier...",
  "features": [
    "Internally frequency compensated for unity gain",
    "Wide supply voltage range: 3V to 32V"
  ],
  "pins": [
    { "number": "1", "name": "OUT1", "type": "O", "description": "Output of amplifier 1" }
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
      "description": "Non-inverting amplifier with gain set by R1/R2 feedback network..."
    }
  ]
}
```

## Field notes

- **pin.type**: `"I"`, `"O"`, `"I/O"`, `"Power"`, `"GND"`, or `"NC"`
- **specs vs absolute_max_ratings**: Absolute max = never-exceed limits; specs = operating conditions
- **typical_circuits**: If a page is marked as a diagram, describe the circuit in plain English
- **All numeric values as strings**: `"3.3"` not `3.3`
- **Missing sections**: Use `[]` for missing lists, `null` for missing scalars — don't omit fields
- If `read` prints a truncation warning, mention it to the user and offer to re-run with `DATASHEET_MAX_PAGES=<higher>`
