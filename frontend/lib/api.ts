// API contract types + fetch helpers. See docs/api.md.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export type NutrientForm = { name_ko: string; elemental_pct: number };

export type ReferenceNutrient = {
  nutrient_code: string;
  nutrient_ko: string;
  group_name: string;
  target_unit: string;
  ul_unit: string;
  synonyms?: string[];
  forms?: NutrientForm[];
};

export type DrugClass = { code: string; label_ko: string };
export type EnergyRatio = {
  macronutrient: string;
  pct_min: number;
  pct_max: number;
  note_ko?: string;
};

export type Reference = {
  kdri_version: string;
  nutrients: ReferenceNutrient[];
  drug_classes: DrugClass[];
  energy_ratios: EnergyRatio[];
};

export type Status = "OVER" | "DEFICIT" | "ADEQUATE" | "UNKNOWN";

export type TraceStep = {
  rule_id: string;
  inputs?: Record<string, unknown>;
  output?: unknown;
  citation?: string;
};

export type Interaction = {
  drug_class: string;
  severity: string;
  action: string;
  source: string;
};

export type NutrientResult = {
  nutrient_code: string;
  nutrient_ko: string;
  status: Status;
  target: number | null;
  target_unit: string;
  from_diet: number | null;
  from_supplements: number | null;
  gap: number | null;
  headroom: number | null;
  recommend: number | null;
  limit: { value: number; unit: string; basis: string; source: string } | null;
  message_ko?: string;
  interactions?: Interaction[];
  biomarker?: {
    biomarker_code: string;
    value: number;
    unit: string;
    threshold: number;
    direction: string;
    note_ko: string;
    source: string;
  } | null;
  trace?: TraceStep[];
};

// The API response as documented does not echo the submitted profile; these
// fields are optional and rendered defensively (see report page fallback).
export type ReportProfile = {
  age?: number;
  sex?: "M" | "F";
  weight_kg?: number | null;
  goals?: string[];
};

export type Report = {
  report_id: number;
  version: number;
  parent_id: number | null;
  created_at: string;
  kdri_version: string;
  disclaimer: string;
  demo_data?: boolean;
  summary: { over: number; deficit: number; adequate: number; unknown: number };
  results: NutrientResult[];
  energy_ratios_reference: EnergyRatio[];
  // possibly-present echoes:
  profile?: ReportProfile;
  supplements?: unknown[];
  medications?: string[];
  biomarkers?: { code: string; value: number; unit: string }[];
};

export type ApiError = {
  code: string;
  message: string;
  detail?: string;
  referral?: string;
  field?: string;
};

export async function getReference(): Promise<Reference> {
  const res = await fetch(`${API_BASE}/api/reference`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`reference ${res.status}`);
  return res.json();
}

export async function getReport(id: string): Promise<Report> {
  const res = await fetch(`${API_BASE}/api/reports/${id}`, {
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw Object.assign(new Error(`report ${res.status}`), {
      status: res.status,
      api: body?.error as ApiError | undefined,
    });
  }
  return res.json();
}

// Returns the report on 201, or throws with `.api` set to the error envelope.
export async function createReport(payload: unknown): Promise<Report> {
  const res = await fetch(`${API_BASE}/api/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw Object.assign(new Error(`reports ${res.status}`), {
      status: res.status,
      api: body?.error as ApiError | undefined,
    });
  }
  return body as Report;
}
