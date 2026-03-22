from __future__ import annotations

from pydantic import BaseModel, Field


class Pin(BaseModel):
    number: str
    name: str
    type: str = ""  # "I", "O", "I/O", "Power", "GND", "NC"
    description: str = ""


class Spec(BaseModel):
    parameter: str
    min: str | None = None
    typ: str | None = None
    max: str | None = None
    unit: str | None = None
    conditions: str | None = None


class Package(BaseModel):
    name: str
    dimensions: str | None = None
    theta_ja: str | None = None  # thermal resistance junction-to-ambient (°C/W)


class TruthTableRow(BaseModel):
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    notes: str | None = None


class TruthTable(BaseModel):
    name: str
    rows: list[TruthTableRow] = Field(default_factory=list)


class Circuit(BaseModel):
    name: str
    description: str  # Claude's interpretation of the schematic


class Datasheet(BaseModel):
    part_number: str = ""
    manufacturer: str = ""
    description: str = ""
    features: list[str] = Field(default_factory=list)
    pins: list[Pin] = Field(default_factory=list)
    absolute_max_ratings: list[Spec] = Field(default_factory=list)
    specs: list[Spec] = Field(default_factory=list)
    package: Package | None = None
    truth_tables: list[TruthTable] = Field(default_factory=list)
    typical_circuits: list[Circuit] = Field(default_factory=list)
