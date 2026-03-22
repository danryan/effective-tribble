---
name: extract-datasheet
description: Use when the user provides a PDF datasheet for an electronic component and wants specs, pinout, features, package info, or a summary extracted
---

# Extract Datasheet Skill

Extract structured information from an electronic component datasheet PDF using the `datasheets` MCP server.

## When to use

When the user provides a path to a PDF datasheet and asks about the component — specs, pinout, features, package, summary, etc.

## Workflow

Call `extract_datasheet` with the PDF path:

```
extract_datasheet(path="/path/to/component.pdf")
```

Read all returned content carefully — text pages, Markdown tables, and any diagram images — then produce structured Markdown output in the format below. Write the output to a file named `PART_NUMBER.md` in the current working directory (e.g., `AS2164.md`). Use the primary part number from the datasheet as the filename.

## Output format

```markdown
# PART_NUMBER — Manufacturer

## Description
[one paragraph]

## Features
- feature one
- feature two

## Pin Configuration
| Pin | Name | Type | Description |
|-----|------|------|-------------|

## Absolute Maximum Ratings
| Parameter | Min | Typ | Max | Unit | Conditions |
|-----------|-----|-----|-----|------|------------|

## Electrical Characteristics
| Parameter | Min | Typ | Max | Unit | Conditions |
|-----------|-----|-----|-----|------|------------|

## Truth Tables
### Table Name
| A | B | Y |
|---|---|---|

## Package Information
**Package:** SOIC-8
**Dimensions:** ...
**θJA:** ... °C/W

## Typical Application Circuits
### Circuit Name
[description of schematic]
```

## Verification

After writing the markdown file, verify it before reporting done:

1. **Re-read the written file** and cross-check against the original extracted content
2. **Check for garbled data** — OCR artifacts, merged table cells, nonsensical values, misaligned columns
3. **Spot-check key values** — supply voltage, pin count, and package type must match the source
4. **Confirm section completeness** — every major section present in the PDF should have a corresponding section in the markdown (don't silently drop sections)
5. **Validate table structure** — ensure all table rows have the correct number of columns and no data shifted between columns

Fix any issues found before reporting the file as complete.

## Field guidance

- **pin.type**: `I`, `O`, `I/O`, `Power`, `GND`, or `NC`
- **specs vs absolute max**: Absolute max = never-exceed limits; specs = operating conditions
- **diagram pages**: describe the circuit in plain English under Typical Application Circuits
- Omit sections not found in the datasheet
- **notes/footnotes**: Do not create a separate Notes section. Inline all note content directly into the Conditions column of the relevant parameter row (e.g., "At 1 kHz" not "Note 6")
- If a truncation warning is returned, mention it and offer to re-run with higher `max_pages`
