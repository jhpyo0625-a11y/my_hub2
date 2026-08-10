"""FastAPI HTTP layer for the KDRI 2025 supplement engine (Phase 2).

Deterministic templating only — no LLM anywhere (권한정책 TB-1). The engine is
imported and used unchanged; this layer validates scope, renders Korean
messages from engine output, and persists reports via the reports.py accessor.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kdri import reports as reports_acc
from kdri.db import KdriBand, make_engine, make_session_factory, Base
from kdri.engine import compute_report
from kdri.lookup import BandNotFound, find_band, resolve_limit
from kdri.models import Profile, SupplementIntake
from kdri.seed import load_engine_inputs, seed_all

KDRI_VERSION = "2025"
DISCLAIMER = (
    "본 결과는 진단·치료 목적이 아니며, 2025 한국인 영양소 섭취기준에 근거한 참고 정보입니다."
)
ENERGY_NOTE = "참고용 — 실제 섭취 열량 정보가 없어 평가하지 않습니다"
COOKIE_SECURE = os.environ.get("KDRI_COOKIE_SECURE") == "1"


# ── request models (lenient: scope errors are first-class, not 422 noise) ─


class ProfileIn(BaseModel):
    age: Optional[int] = None
    sex: Optional[str] = None
    weight_kg: Optional[float] = None
    is_pregnant: bool = False
    is_lactating: bool = False
    goals: list[str] = []


class SupplementIn(BaseModel):
    nutrient_code: str
    form_ko: Optional[str] = None
    dose: Optional[float] = None
    unit: Optional[str] = None
    doses_per_day: float = 1.0
    unresolved: bool = False


class BiomarkerIn(BaseModel):
    code: str
    value: Optional[float] = None
    unit: Optional[str] = None


class ReportRequest(BaseModel):
    profile: ProfileIn
    supplements: list[SupplementIn] = []
    medications: list[str] = []
    biomarkers: list[BiomarkerIn] = []
    parent_id: Optional[int] = None


# ── error envelope ───────────────────────────────────────────────────────


def _err(status: int, code: str, message: str, **extra) -> JSONResponse:
    body = {"code": code, "message": message}
    body.update({k: v for k, v in extra.items() if v is not None})
    return JSONResponse(status_code=status, content={"error": body})


# ── number helpers ───────────────────────────────────────────────────────


def _num(x: Optional[float]) -> Optional[float]:
    if x is None:
        return None
    r = round(float(x), 4)
    return 0.0 if r == 0 else r


def _fmt(x: float) -> str:
    r = round(float(x), 4)
    return str(int(r)) if r == int(r) else str(r)


# ── scope validation ─────────────────────────────────────────────────────


def _validate_scope(req: ReportRequest, in_scope: set[str], profiles: dict):
    p = req.profile
    if p.sex not in ("M", "F"):
        return _err(
            422,
            "SEX_REQUIRED",
            "성별을 입력해 주세요.",
            detail="성인 섭취기준은 성별로 나뉘어 있어 성별 없이는 계산할 수 없습니다.",
            field="profile.sex",
        )
    if p.age is None or p.age < 19:
        return _err(
            422,
            "AGE_OUT_OF_SCOPE",
            "만 19세 이상 성인만 이용할 수 있습니다.",
            detail="소아·청소년 섭취기준은 연령 구간이 달라 별도 검토가 필요합니다.",
            referral="소아청소년과 또는 영양사 상담을 권해 드립니다.",
            field="profile.age",
        )
    if p.is_pregnant or p.is_lactating:
        return _err(
            422,
            "PREGNANCY_OUT_OF_SCOPE",
            "임신·수유 중에는 결과를 제공하지 않습니다.",
            detail="임신부 기준은 별도 가산값이며 수유부 기준은 현재 데이터에 포함되어 있지 않습니다.",
            referral="산부인과 상담을 권해 드립니다.",
            field="profile.is_pregnant",
        )
    for s in req.supplements:
        if s.unresolved:
            return _err(
                422,
                "UNRESOLVED_INTAKE",
                "확인이 필요한 항목이 남아 있습니다. 확인 화면에서 먼저 해결해 주세요.",
                field="supplements",
            )
        if s.nutrient_code not in in_scope:
            return _err(
                422, "INVALID_INTAKE", f"알 수 없는 영양소 코드입니다: {s.nutrient_code}",
                field="supplements",
            )
        if s.dose is None or not math.isfinite(s.dose) or s.dose <= 0:
            return _err(
                422, "INVALID_INTAKE", "섭취량은 0보다 큰 값이어야 합니다.", field="supplements",
            )
        if not (0 < s.doses_per_day <= 24):
            return _err(
                422, "INVALID_INTAKE", "1일 섭취 횟수는 0 초과 24 이하여야 합니다.",
                field="supplements",
            )
        if s.form_ko:
            prof = profiles.get(s.nutrient_code)
            names = {f.name_ko for f in prof.forms} if prof else set()
            if s.form_ko not in names:
                return _err(
                    422, "INVALID_INTAKE", f"해당 영양소에 없는 제형입니다: {s.form_ko}",
                    field="supplements",
                )
    return None


# ── rendering (deterministic templating) ─────────────────────────────────


def _message_ko(status: str, headroom, recommend, over_unit: str, target_unit: str) -> str:
    if status == "OVER":
        over_by = _fmt(abs(headroom)) if headroom is not None else "0"
        return f"현재 보충제 섭취량이 상한섭취량을 {over_by}{over_unit} 초과합니다. 용량을 줄이세요."
    if status == "DEFICIT":
        if recommend and recommend > 0:
            return f"섭취기준에 미달합니다. 하루 {_fmt(recommend)}{target_unit} 보충을 고려해 보세요."
        return "섭취기준에 미달하나 상한섭취량에 근접하여 추가 보충을 권장하지 않습니다."
    if status == "ADEQUATE":
        return "현재 섭취량이 적정 범위입니다. 추가 보충이 필요하지 않습니다."
    return "평가에 필요한 식이 섭취 기준 정보가 없어 이 영양소는 판단하지 않습니다."


def _ser_step(step) -> dict:
    d = {"rule_id": step.rule_id, "inputs": step.inputs, "output": step.output}
    if step.citation is not None:
        d["citation"] = step.citation
    return d


def _render_results(user: Profile, inp) -> tuple[list, dict, dict]:
    results = compute_report(user, inp.bands, inp.limits, inp.profiles)
    out: list = []
    trace_map: dict = {}
    summary = {"over": 0, "deficit": 0, "adequate": 0, "unknown": 0}
    meds = set(user.medications)
    for r in results:
        code = r.nutrient_code
        prof = inp.profiles.get(code)
        n = inp.nutrients.get(code)
        target_unit = prof.target_unit if prof else (n.kdri_unit if n else "")
        ul_unit = prof.ul_unit if prof else "unknown"

        declared = [s.form_ko for s in user.supplements if s.nutrient_code == code]
        limit_obj = None
        try:
            band = find_band(inp.bands, code, user.sex, user.age)
            lim = resolve_limit(inp.limits, band, code, declared, user.age, user.sex, ul_unit)
            if lim is not None:
                limit_obj = {
                    "value": _num(lim.value),
                    "unit": lim.unit,
                    "basis": lim.basis,
                    "source": lim.source,
                }
        except BandNotFound:
            pass

        over_unit = limit_obj["unit"] if limit_obj else target_unit
        interactions = [
            {
                "drug_class": row["drug_class"],
                "severity": row["severity"],
                "action": row["action"],
                "source": row["source"],
            }
            for row in inp.interactions
            if row["nutrient_code"] == code and row["drug_class"] in meds
        ]
        trace = [_ser_step(s) for s in r.trace]
        trace_map[code] = trace
        out.append(
            {
                "nutrient_code": code,
                "nutrient_ko": n.name_ko if n else code,
                "status": r.status,
                "target": _num(r.target),
                "target_unit": target_unit,
                "from_diet": _num(r.from_diet),
                "from_supplements": _num(r.from_supplements),
                "gap": _num(r.gap),
                "headroom": _num(r.headroom),
                "recommend": _num(r.recommend),
                "limit": limit_obj,
                "message_ko": _message_ko(
                    r.status, r.headroom, r.recommend, over_unit, target_unit
                ),
                "interactions": interactions,
                "trace": trace,
            }
        )
        summary[r.status.lower()] += 1
    # Normalise (tuples -> lists) so stored JSON == response JSON byte-for-byte.
    out = json.loads(json.dumps(out, ensure_ascii=False))
    return out, trace_map, summary


def _energy_reference(inp) -> list:
    return [
        {
            "macronutrient": row["macronutrient"],
            "pct_min": float(row["pct_min"]),
            "pct_max": float(row["pct_max"]),
            "note_ko": ENERGY_NOTE,
        }
        for row in inp.energy_ratios
    ]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _envelope(row, results: list, inp) -> dict:
    summary = {"over": 0, "deficit": 0, "adequate": 0, "unknown": 0}
    for r in results:
        summary[r["status"].lower()] += 1
    return {
        "report_id": row.id,
        "version": row.version,
        "parent_id": row.parent_id,
        "created_at": _iso(row.created_at),
        "kdri_version": KDRI_VERSION,
        "demo_data": inp.demo,
        "disclaimer": DISCLAIMER,
        # Echo the stored input snapshot so the report renders block 1 (입력 요약)
        # on any GET/reload/history view — the report is reproducible from its
        # own row (NFR-7), not from client-held state.
        "profile": row.profile_json,
        "summary": summary,
        "results": results,
        "energy_ratios_reference": _energy_reference(inp),
    }


# ── app factory ──────────────────────────────────────────────────────────


def create_app(db_url: str | None = None, demo: bool | None = None) -> FastAPI:
    db_url = db_url or os.environ.get("KDRI_DB", "sqlite:///kdri.db")
    engine = make_engine(db_url)
    Base.metadata.create_all(engine)
    SessionLocal = make_session_factory(engine)

    inp = load_engine_inputs(demo)
    with SessionLocal() as s:
        seed_all(s, inp)  # runs assertions; raises -> startup aborts (PF-04)

    app = FastAPI(title="KDRI 2025 supplement engine")
    app.state.engine = engine
    app.state.SessionLocal = SessionLocal
    app.state.inputs = inp
    app.state.idem = {}

    def get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    @app.middleware("http")
    async def _ensure_sid(request: Request, call_next):
        existing = request.cookies.get("sid")
        request.state.sid = existing or uuid4().hex
        response = await call_next(request)
        if not existing:
            response.set_cookie(
                "sid", request.state.sid, httponly=True,
                samesite="lax", secure=COOKIE_SECURE,
            )
        return response

    def get_sid(request: Request) -> str:
        return request.state.sid

    @app.get("/api/health")
    def health(db: Session = Depends(get_db)):
        band_rows = db.execute(select(func.count()).select_from(KdriBand)).scalar_one()
        return {
            "status": "ok",
            "kdri_version": KDRI_VERSION,
            "band_rows": band_rows,
            "seed_assertions": "passed",
        }

    @app.get("/api/reference")
    def reference():
        inp = app.state.inputs
        nutrients = []
        for code in sorted(inp.in_scope):
            n = inp.nutrients.get(code)
            prof = inp.profiles.get(code)
            if n is None or prof is None:
                continue
            entry = {
                "nutrient_code": code,
                "nutrient_ko": n.name_ko,
                "group_name": n.group,
                "target_unit": prof.target_unit,
                "ul_unit": prof.ul_unit,
                "synonyms": list(n.synonyms),
            }
            if prof.forms:
                entry["forms"] = [
                    {"name_ko": f.name_ko, "elemental_pct": f.elemental_pct}
                    for f in prof.forms
                ]
            nutrients.append(entry)
        seen: dict[str, str] = {}
        for row in inp.interactions:
            seen.setdefault(row["drug_class"], row.get("drug_examples_ko") or row["drug_class"])
        drug_classes = [{"code": c, "label_ko": lbl} for c, lbl in seen.items()]
        return {
            "kdri_version": KDRI_VERSION,
            "nutrients": nutrients,
            "drug_classes": drug_classes,
            "energy_ratios": [
                {
                    "macronutrient": r["macronutrient"],
                    "pct_min": float(r["pct_min"]),
                    "pct_max": float(r["pct_max"]),
                }
                for r in inp.energy_ratios
            ],
        }

    @app.post("/api/reports")
    def create_report(
        req: ReportRequest,
        request: Request,
        db: Session = Depends(get_db),
        sid: str = Depends(get_sid),
    ):
        inp = app.state.inputs
        err = _validate_scope(req, inp.in_scope, inp.profiles)
        if err is not None:
            return err

        idem_key = request.headers.get("Idempotency-Key")
        if idem_key:
            prior = app.state.idem.get((sid, idem_key))
            if prior is not None:
                row = reports_acc.get_report_owned(db, prior, sid)
                if row is not None:
                    return _envelope(row, row.result_json, inp)

        if req.parent_id is not None:
            parent = reports_acc.get_report_owned(db, req.parent_id, sid)
            if parent is None:
                return _err(
                    404, "REPORT_NOT_FOUND", "이전 보고서를 찾을 수 없습니다.",
                    field="parent_id",
                )

        user = Profile(
            age=req.profile.age,
            sex=req.profile.sex,
            supplements=tuple(
                SupplementIntake(
                    nutrient_code=s.nutrient_code,
                    dose=s.dose,
                    doses_per_day=s.doses_per_day,
                    form_ko=s.form_ko,
                )
                for s in req.supplements
            ),
            medications=tuple(req.medications),
            weight_kg=req.profile.weight_kg,
        )
        results, trace_map, _summary = _render_results(user, inp)
        row = reports_acc.create_report(
            db,
            session_key=sid,
            profile_json=req.model_dump(),
            result_json=results,
            trace_json=trace_map,
            parent_id=req.parent_id,
        )
        if idem_key:
            app.state.idem[(sid, idem_key)] = row.id
        return JSONResponse(status_code=201, content=_envelope(row, results, inp))

    @app.get("/api/reports/{report_id}")
    def get_report(
        report_id: int,
        db: Session = Depends(get_db),
        sid: str = Depends(get_sid),
    ):
        row = reports_acc.get_report_owned(db, report_id, sid)
        if row is None:
            return _err(404, "REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.")
        return _envelope(row, row.result_json, app.state.inputs)

    @app.delete("/api/reports/{report_id}", status_code=204)
    def delete_report(
        report_id: int,
        db: Session = Depends(get_db),
        sid: str = Depends(get_sid),
    ):
        ok = reports_acc.delete_report(db, report_id, sid)
        if not ok:
            return _err(404, "REPORT_NOT_FOUND", "보고서를 찾을 수 없습니다.")
        return Response(status_code=204)

    return app


app = create_app()
