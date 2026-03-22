# Extract Datasheet Skill

Extract structured information from an electronic component datasheet PDF using the `datasheets` MCP server.

## When to use

When the user provides a path to a PDF datasheet and asks about the component — specs, pinout, features, package, summary, etc.

## Workflow

Call `extract_datasheet` with the PDF path:

```
extract_datasheet(path="/path/to/component.pdf")
```

Read all returned content carefully — text pages, Markdown tables, and any diagram images — then produce structured Markdown output in the format below.

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

## Field guidance

- **pin.type**: `I`, `O`, `I/O`, `Power`, `GND`, or `NC`
- **specs vs absolute max**: Absolute max = never-exceed limits; specs = operating conditions
- **diagram pages**: describe the circuit in plain English under Typical Application Circuits
- Omit sections not found in the datasheet
- If a truncation warning is returned, mention it and offer to re-run with higher `max_pages`
