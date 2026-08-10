from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Sex = Literal["M", "F"]
Basis = Literal["total_intake", "supplemental_only"]
Status = Literal["DEFICIT", "ADEQUATE", "OVER", "UNKNOWN"]


@dataclass(frozen=True)
class Nutrient:
    code: str
    name_ko: str
    group: str
    kdri_unit: str
    synonyms: tuple[str, ...]
    has_rni: bool
    has_ai: bool
    has_ul: bool


@dataclass(frozen=True)
class KdriRow:
    nutrient_code: str
    age_min: int
    age_max: int
    gender: str
    ri_base: Optional[float]
    ul_limit: Optional[float]


@dataclass(frozen=True)
class Limit:
    nutrient_code: str
    applies_to_form: Optional[str]
    age_min: int
    age_max: int
    sex: str
    value: float
    unit: str
    basis: Basis
    source: str


@dataclass(frozen=True)
class Form:
    nutrient_code: str
    name_ko: str
    elemental_pct: float
    target_factor: float
    ul_factor: float
    source: str


@dataclass(frozen=True)
class NutrientProfile:
    nutrient_code: str
    target_unit: str
    ul_unit: str
    diet_baseline_pct: Optional[float]
    diet_baseline_source: Optional[str]
    forms: tuple[Form, ...] = ()


@dataclass(frozen=True)
class SupplementIntake:
    nutrient_code: str
    dose: float
    doses_per_day: float = 1.0
    form_ko: Optional[str] = None


@dataclass(frozen=True)
class Biomarker:
    """A health-checkup value the user supplies (e.g. hemoglobin 11.2 g/dL)."""
    code: str
    value: float
    unit: Optional[str] = None


@dataclass(frozen=True)
class BiomarkerRef:
    """Curated, cited reference bound mapping a biomarker to a nutrient.

    A value below `low` flags the nutrient for priority — it never changes a
    target. `sex` is 'M', 'F', or 'ALL'.
    """
    biomarker_code: str
    nutrient_code: str
    sex: str
    low: Optional[float]
    high: Optional[float]
    unit: str
    source: str


@dataclass(frozen=True)
class BiomarkerFlag:
    """Attached to a NutrientResult when a biomarker is out of range. Context
    and priority only — the dosing numbers are untouched."""
    biomarker_code: str
    nutrient_code: str
    value: float
    unit: str
    threshold: float
    direction: str  # "low" (below reference) — "high" reserved for later
    source: str


@dataclass(frozen=True)
class Profile:
    age: int
    sex: Sex
    supplements: tuple[SupplementIntake, ...] = ()
    medications: tuple[str, ...] = ()
    biomarkers: tuple[Biomarker, ...] = ()
    weight_kg: Optional[float] = None


@dataclass(frozen=True)
class TraceStep:
    rule_id: str
    inputs: dict[str, Any]
    output: Any
    citation: Optional[str] = None


@dataclass
class NutrientResult:
    nutrient_code: str
    status: Status
    target: Optional[float]
    from_diet: float
    from_supplements: float
    gap: float
    headroom: Optional[float]
    recommend: float
    priority_score: float = 0.0
    biomarker_flag: Optional["BiomarkerFlag"] = None
    trace: list[TraceStep] = field(default_factory=list)
