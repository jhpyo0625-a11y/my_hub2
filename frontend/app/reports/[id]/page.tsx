"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getReport,
  type Report,
  type NutrientResult,
  type TraceStep,
  type ApiError,
} from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  OVER: "상한 초과",
  DEFICIT: "부족",
  ADEQUATE: "충분",
  UNKNOWN: "판단 보류",
};
const STATUS_CLASS: Record<string, string> = {
  OVER: "over",
  DEFICIT: "deficit",
  ADEQUATE: "adequate",
  UNKNOWN: "unknown",
};
const MACRO_KO: Record<string, string> = {
  carbohydrate: "탄수화물",
  protein: "단백질",
  fat: "지방",
};

// tabular number, drop noise; "—" for null/undefined
function num(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number.isInteger(v) ? String(v) : String(Number(v.toFixed(3)));
}

function Cell({
  label,
  value,
  unit,
  neg,
}: {
  label: string;
  value: string;
  unit?: string;
  neg?: boolean;
}) {
  return (
    <div className={neg ? "neg" : undefined}>
      <dt>{label}</dt>
      <dd>
        {value}
        {unit && value !== "—" ? <small>{unit}</small> : null}
      </dd>
    </div>
  );
}

// Compose a human-readable calc line from a structured trace step.
function traceCalc(step: TraceStep): string {
  const parts: string[] = [];
  if (step.inputs) {
    parts.push(
      Object.entries(step.inputs)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(", ")
    );
  }
  if (step.output !== undefined) {
    const out =
      typeof step.output === "object"
        ? JSON.stringify(step.output)
        : String(step.output);
    parts.push(`→ ${out}`);
  }
  return parts.join(" ");
}

function Trace({ steps }: { steps?: TraceStep[] }) {
  if (!steps?.length) return null;
  return (
    <details className="trace">
      <summary>이 숫자는 어떻게 나왔나요?</summary>
      <div className="trace-body">
        {steps.map((s, i) => (
          <div className="trace-step" key={i}>
            <span className="rule">{s.rule_id}</span>{" "}
            <span className="calc">{traceCalc(s)}</span>
            {s.citation && (
              <>
                <br />
                <span className="cite">{s.citation}</span>
              </>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function NutrientCard({ r }: { r: NutrientResult }) {
  const unit = r.target_unit;
  // 4th cell varies by status
  let fourth: { label: string; value: string; neg?: boolean };
  if (r.status === "OVER") {
    fourth = { label: "상한 여유", value: num(r.headroom), neg: (r.headroom ?? 0) < 0 };
  } else if (r.status === "DEFICIT") {
    fourth = { label: "부족량", value: num(r.gap) };
  } else if (r.status === "UNKNOWN") {
    fourth = { label: "추천량", value: "—" };
  } else {
    // ADEQUATE
    fourth =
      r.limit != null
        ? { label: "상한 여유", value: num(r.headroom) }
        : { label: "부족량", value: num(r.gap) };
  }

  return (
    <div className={`nutrient${r.status === "OVER" ? " is-over" : ""}`}>
      <div className="nutrient-head">
        <span className="name">{r.nutrient_ko}</span>
        <span className={`pill ${STATUS_CLASS[r.status]}`}>
          {STATUS_LABEL[r.status]}
        </span>
      </div>

      {r.message_ko && (
        <div className={`callout${r.status === "OVER" ? "" : " info"}`}>
          {r.message_ko}
        </div>
      )}

      <dl className="numbers">
        <Cell label="목표 섭취량" value={num(r.target)} unit={unit} />
        <Cell label="식품 기여" value={num(r.from_diet)} unit={unit} />
        <Cell label="보충제 기여" value={num(r.from_supplements)} unit={unit} />
        <Cell
          label={fourth.label}
          value={fourth.value}
          unit={unit}
          neg={fourth.neg}
        />
      </dl>

      <Trace steps={r.trace} />
    </div>
  );
}

// ── Block 3: recommendation card per nutrient ──
function RecoCard({ r }: { r: NutrientResult }) {
  const unit = r.target_unit;
  if (r.status === "OVER") {
    return (
      <div className="nutrient is-over">
        <div className="nutrient-head">
          <span className="name">{r.nutrient_ko} — 줄이세요</span>
          <span className="pill over">감량</span>
        </div>
        {r.message_ko && <p style={{ margin: "0 0 10px" }}>{r.message_ko}</p>}
        {r.limit && (
          <div className="ref-row">
            <span className="k">상한섭취량</span>
            <span className="v">
              {num(r.limit.value)} {r.limit.unit}
            </span>
          </div>
        )}
        {r.interactions?.map((it, i) => (
          <div
            className="callout warn"
            key={i}
            style={{ marginTop: 12, marginBottom: 0 }}
          >
            <strong>약물 상호작용 주의 ({it.drug_class})</strong> — {it.action}.
            <small style={{ display: "block", fontWeight: 400 }}>
              {it.source}
            </small>
          </div>
        ))}
      </div>
    );
  }

  if (r.status === "DEFICIT" && (r.recommend ?? 0) > 0) {
    return (
      <div className="nutrient">
        <div className="nutrient-head">
          <span className="name">
            {r.nutrient_ko} — 하루 {num(r.recommend)}
            {unit} 추가
          </span>
          <span className="pill deficit">추가 권장</span>
        </div>
        <div className="ref-row">
          <span className="k">추천 섭취량</span>
          <span className="v">
            {num(r.recommend)} {unit}/일
          </span>
        </div>
        {r.limit && (
          <div className="ref-row">
            <span className="k">상한 여유</span>
            <span className="v">
              {num(r.headroom)} {unit}
            </span>
          </div>
        )}
        {r.interactions?.map((it, i) => (
          <div
            className="callout warn"
            key={i}
            style={{ marginTop: 12, marginBottom: 0 }}
          >
            <strong>약물 상호작용 주의 ({it.drug_class})</strong> — {it.action}.
          </div>
        ))}
      </div>
    );
  }

  if (r.status === "ADEQUATE") {
    return (
      <div className="nutrient">
        <div className="nutrient-head">
          <span className="name">{r.nutrient_ko} — 추가 불필요</span>
          <span className="pill adequate">유지</span>
        </div>
        <p style={{ margin: 0 }}>
          현재 섭취량으로 목표에 도달했습니다. 추가 보충은 필요하지 않습니다.
        </p>
      </div>
    );
  }

  return null;
}

type Stash = {
  profile?: { age?: number; sex?: string; weight_kg?: number | null };
  medLabels?: string[];
  goalLabel?: string;
  supplementCount?: number;
  biomarkers?: { code: string; value: number; unit: string }[];
};

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<ApiError | { code: string; message: string } | null>(
    null
  );
  const [stash, setStash] = useState<Stash | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    getReport(id)
      .then(setReport)
      .catch((e: { api?: ApiError; status?: number }) =>
        setError(
          e.api ?? {
            code: "ERROR",
            message:
              e.status === 404
                ? "요청하신 리포트를 찾을 수 없습니다."
                : "리포트를 불러오지 못했습니다.",
          }
        )
      );
    try {
      const raw = sessionStorage.getItem(`intake:${id}`);
      if (raw) setStash(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, [id]);

  if (error) {
    return (
      <main className="wrap">
        <div className="card" role="alert">
          <div className="block-head">
            <span className="block-num">!</span>
            <h2>리포트를 표시할 수 없습니다</h2>
          </div>
          <div className="callout warn" style={{ marginBottom: 0 }}>
            {error.message}
          </div>
          <div className="actions">
            <Link className="btn btn-primary" href="/intake">
              입력으로 돌아가기
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="wrap">
        <p className="lede">리포트를 불러오는 중입니다…</p>
      </main>
    );
  }

  const profile = report.profile ?? stash?.profile;
  const sexKo = profile?.sex === "F" ? "여성" : profile?.sex === "M" ? "남성" : "—";
  const medLabels =
    stash?.medLabels ?? report.medications ?? [];
  const suppCount = stash?.supplementCount ?? report.supplements?.length;
  const biomarkers = report.biomarkers ?? stash?.biomarkers ?? [];

  const s = report.summary;
  const created = new Date(report.created_at).toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const VISIBLE = 4;
  const results = report.results;
  const shown = showAll ? results : results.slice(0, VISIBLE);
  const hidden = results.length - shown.length;

  const recos = results.filter(
    (r) =>
      r.status === "OVER" ||
      (r.status === "DEFICIT" && (r.recommend ?? 0) > 0) ||
      r.status === "ADEQUATE"
  );

  return (
    <main className="wrap">
      <span className="screen-tag">
        S-07 · /reports/{report.report_id} · v{report.version}
      </span>
      <h1>영양 상태 분석 결과</h1>
      <p className="lede">
        {created} · 2025 한국인 영양소 섭취기준 기준 · {results.length}개 영양소
        분석
      </p>

      {report.demo_data && (
        <div className="banner">
          예시 데이터 — 식이 기여 추정치는 시연용입니다.
        </div>
      )}

      {/* ── BLOCK 1 ── */}
      <section className="card">
        <div className="block-head">
          <span className="block-num">1</span>
          <h2>입력 요약</h2>
          <Link
            className="btn btn-ghost btn-sm hint"
            href="/intake"
            style={{ marginLeft: "auto" }}
          >
            입력 수정
          </Link>
        </div>

        <div className="grid-2">
          <div>
            <div className="ref-row">
              <span className="k">나이 · 성별</span>
              <span className="v">
                {profile?.age ? `${profile.age}세` : "—"} · {sexKo}
              </span>
            </div>
            <div className="ref-row">
              <span className="k">체중</span>
              <span className="v">
                {profile?.weight_kg ? `${profile.weight_kg} kg` : "미입력"}{" "}
                <small>— 결과 미반영</small>
              </span>
            </div>
            <div className="ref-row">
              <span className="k">목표</span>
              <span className="v">{stash?.goalLabel || "선택 안 함"}</span>
            </div>
          </div>
          <div>
            <div className="ref-row">
              <span className="k">복용 중인 영양제</span>
              <span className="v">
                {suppCount !== undefined ? `${suppCount}건` : "—"}
              </span>
            </div>
            <div className="ref-row">
              <span className="k">복용 중인 약</span>
              <span className="v">
                {medLabels.length ? medLabels.join(", ") : "해당 없음"}
              </span>
            </div>
            <div className="ref-row">
              <span className="k">검진 수치</span>
              <span className="v">
                {biomarkers.length
                  ? biomarkers
                      .map((b) => `${b.code} ${b.value} ${b.unit}`)
                      .join(", ")
                  : "미입력"}
              </span>
            </div>
          </div>
        </div>

        <div
          className="callout info"
          style={{ marginTop: 16, marginBottom: 0 }}
        >
          체중은 저장되었지만 이번 결과에는 반영되지 않았습니다. 2025 섭취기준의
          비타민·무기질 항목에는 체중 기반 산출값이 없습니다.
        </div>
      </section>

      {/* ── BLOCK 2 ── */}
      <section className="card">
        <div className="block-head">
          <span className="block-num">2</span>
          <h2>현재 상태 분석</h2>
          <span className="hint">
            상한 초과 {s.over} · 부족 {s.deficit} · 충분 {s.adequate} · 판단
            보류 {s.unknown}
          </span>
        </div>

        {shown.map((r) => (
          <NutrientCard key={r.nutrient_code} r={r} />
        ))}

        {results.length > VISIBLE && (
          <div style={{ textAlign: "center", marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll ? "접기 ▴" : `나머지 ${hidden}개 영양소 보기 ▾`}
            </button>
          </div>
        )}
      </section>

      {/* ── BLOCK 3 ── */}
      <section className="card">
        <div className="block-head">
          <span className="block-num">3</span>
          <h2>추천</h2>
          <span className="hint">현재 복용 중인 약을 반영했습니다</span>
        </div>
        {recos.length ? (
          recos.map((r) => <RecoCard key={r.nutrient_code} r={r} />)
        ) : (
          <p style={{ margin: 0 }}>표시할 추천 항목이 없습니다.</p>
        )}
      </section>

      {/* ── BLOCK 4 ── (no trace, intentional) */}
      <section className="card">
        <div className="block-head">
          <span className="block-num">4</span>
          <h2>참고 — 2025 에너지 적정비율</h2>
          <span className="hint">계산하지 않은 참고 정보</span>
        </div>

        {report.energy_ratios_reference?.map((e) => (
          <div className="ref-row" key={e.macronutrient}>
            <span className="k">{MACRO_KO[e.macronutrient] ?? e.macronutrient}</span>
            <span className="v">
              {e.pct_min} – {e.pct_max} %
              {e.note_ko && <small> · {e.note_ko}</small>}
            </span>
          </div>
        ))}

        <div className="callout info" style={{ marginTop: 16, marginBottom: 0 }}>
          <strong>이 항목은 평가하지 않았습니다.</strong> 에너지 적정비율은 실제
          섭취 열량에 대한 비율이며, 이 서비스는 식단을 기록하지 않으므로 분모가
          없습니다. 국가 기준값을 참고용으로만 표시합니다.
        </div>
      </section>

      <div className="actions">
        <Link className="btn btn-ghost" href="/intake">
          입력 수정
        </Link>
      </div>

      <p className="disclaimer">
        {report.disclaimer}{" "}
        표시된 모든 수치는 계산 근거를 펼쳐 확인할 수 있습니다.
      </p>
    </main>
  );
}
