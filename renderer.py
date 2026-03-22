from __future__ import annotations

from schema import Datasheet, Spec, TruthTable


def _spec_table(specs: list[Spec]) -> str:
    if not specs:
        return ""
    rows = ["| Parameter | Min | Typ | Max | Unit | Conditions |",
            "|-----------|-----|-----|-----|------|------------|"]
    for s in specs:
        rows.append(
            f"| {s.parameter} | {s.min or ''} | {s.typ or ''} | {s.max or ''} "
            f"| {s.unit or ''} | {s.conditions or ''} |"
        )
    return "\n".join(rows)


def _truth_table_md(tt: TruthTable) -> str:
    if not tt.rows:
        return f"### {tt.name}\n\n*(no rows)*"
    all_inputs = list(dict.fromkeys(k for row in tt.rows for k in row.inputs))
    all_outputs = list(dict.fromkeys(k for row in tt.rows for k in row.outputs))
    has_notes = any(row.notes for row in tt.rows)

    headers = all_inputs + all_outputs + (["Notes"] if has_notes else [])
    sep = ["---"] * len(headers)
    lines = [f"### {tt.name}", "", "| " + " | ".join(headers) + " |",
             "| " + " | ".join(sep) + " |"]
    for row in tt.rows:
        cells = [row.inputs.get(h, "") for h in all_inputs]
        cells += [row.outputs.get(h, "") for h in all_outputs]
        if has_notes:
            cells.append(row.notes or "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render(ds: Datasheet, truncation_warning: str | None = None) -> str:
    parts: list[str] = []

    title = ds.part_number or "Unknown Part"
    if ds.manufacturer:
        title += f" — {ds.manufacturer}"
    parts.append(f"# {title}")

    if ds.description:
        parts.append(f"\n## Description\n\n{ds.description}")

    if ds.features:
        feat_lines = "\n".join(f"- {f}" for f in ds.features)
        parts.append(f"\n## Features\n\n{feat_lines}")

    if ds.pins:
        rows = ["| Pin | Name | Type | Description |",
                "|-----|------|------|-------------|"]
        for p in ds.pins:
            rows.append(f"| {p.number} | {p.name} | {p.type} | {p.description} |")
        parts.append("\n## Pin Configuration\n\n" + "\n".join(rows))

    if ds.absolute_max_ratings:
        parts.append("\n## Absolute Maximum Ratings\n\n" + _spec_table(ds.absolute_max_ratings))

    if ds.specs:
        parts.append("\n## Electrical Characteristics\n\n" + _spec_table(ds.specs))

    if ds.truth_tables:
        tt_blocks = "\n\n".join(_truth_table_md(tt) for tt in ds.truth_tables)
        parts.append(f"\n## Truth Tables\n\n{tt_blocks}")

    if ds.package:
        pkg = ds.package
        lines = [f"**Package:** {pkg.name}"]
        if pkg.dimensions:
            lines.append(f"**Dimensions:** {pkg.dimensions}")
        if pkg.theta_ja:
            lines.append(f"**θJA:** {pkg.theta_ja} °C/W")
        parts.append("\n## Package Information\n\n" + "\n\n".join(lines))

    if ds.typical_circuits:
        circuit_blocks = []
        for c in ds.typical_circuits:
            circuit_blocks.append(f"### {c.name}\n\n{c.description}")
        parts.append("\n## Typical Application Circuits\n\n" + "\n\n".join(circuit_blocks))

    if truncation_warning:
        parts.append(f"\n> ⚠️ {truncation_warning}")

    return "\n".join(parts)
