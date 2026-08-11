"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getReference,
  createReport,
  type Reference,
  type ReferenceNutrient,
  type ApiError,
} from "@/lib/api";

type SuppRow = {
  nutrient_code: string;
  form_ko: string;
  dose: string;
  doses_per_day: string;
};

const GOALS: { value: string; label: string }[] = [
  { value: "", label: "선택 안 함" },
  { value: "sleep", label: "수면·이완" },
  { value: "fatigue", label: "피로 개선" },
  { value: "bone", label: "뼈 건강" },
  { value: "anemia", label: "빈혈 개선" },
];

function emptyRow(): SuppRow {
  return { nutrient_code: "", form_ko: "", dose: "", doses_per_day: "1" };
}

export default function IntakePage() {
  const router = useRouter();
  const [ref, setRef] = useState<Reference | null>(null);
  const [refError, setRefError] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Step 1 state
  const [age, setAge] = useState("34");
  const [sex, setSex] = useState<"M" | "F" | null>(null);
  const [weight, setWeight] = useState("");
  const [goal, setGoal] = useState("");
  const [isPregnant, setIsPregnant] = useState(false);
  const [isLactating, setIsLactating] = useState(false);
  const [meds, setMeds] = useState<Set<string>>(new Set());
  const [noMeds, setNoMeds] = useState(false);
  const [hb, setHb] = useState("");
  const [vitd, setVitd] = useState("");

  // Step 2 state
  const [rows, setRows] = useState<SuppRow[]>([emptyRow()]);

  useEffect(() => {
    getReference()
      .then(setRef)
      .catch(() => setRefError(true));
  }, []);

  function nutrientOf(code: string): ReferenceNutrient | undefined {
    return ref?.nutrients.find((n) => n.nutrient_code === code);
  }

  function toggleMed(code: string) {
    setNoMeds(false);
    setMeds((prev) => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  function updateRow(i: number, patch: Partial<SuppRow>) {
    setRows((prev) =>
      prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r))
    );
  }

  function buildPayload(withSupplements: boolean) {
    const biomarkers: { code: string; value: number; unit: string }[] = [];
    if (hb.trim())
      biomarkers.push({ code: "hemoglobin", value: Number(hb), unit: "g/dL" });
    if (vitd.trim())
      biomarkers.push({ code: "vitamin_d", value: Number(vitd), unit: "ng/mL" });

    const supplements = withSupplements
      ? rows
          .filter((r) => r.nutrient_code && r.dose.trim())
          .map((r) => {
            const n = nutrientOf(r.nutrient_code);
            const row: Record<string, unknown> = {
              nutrient_code: r.nutrient_code,
              dose: Number(r.dose),
              unit: n?.target_unit ?? "",
              doses_per_day: Number(r.doses_per_day || "1"),
            };
            if (r.form_ko) row.form_ko = r.form_ko;
            return row;
          })
      : [];

    return {
      profile: {
        age: Number(age),
        sex,
        weight_kg: weight.trim() ? Number(weight) : null,
        is_pregnant: isPregnant,
        is_lactating: isLactating,
        goals: goal ? [goal] : [],
      },
      supplements,
      medications: noMeds ? [] : Array.from(meds),
      biomarkers,
    };
  }

  function validateStep1(): boolean {
    setFormError(null);
    if (!age.trim() || Number(age) < 19) {
      setFormError("나이를 만 19세 이상으로 입력해 주세요.");
      return false;
    }
    if (!sex) {
      setFormError("성별은 건너뛸 수 없는 항목입니다. 선택해 주세요.");
      return false;
    }
    return true;
  }

  async function submit(withSupplements: boolean) {
    if (!validateStep1()) {
      setStep(1);
      return;
    }
    setSubmitting(true);
    setApiError(null);
    setFormError(null);
    try {
      const payload = buildPayload(withSupplements);
      // Stash a summary so the report page can render 입력 요약 even though the
      // API response does not echo the submitted profile.
      const report = await createReport(payload);
      try {
        sessionStorage.setItem(
          `intake:${report.report_id}`,
          JSON.stringify({
            ...payload,
            medLabels: (payload.medications as string[]).map(
              (c) =>
                ref?.drug_classes.find((d) => d.code === c)?.label_ko ?? c
            ),
            goalLabel: GOALS.find((g) => g.value === goal)?.label ?? "",
            supplementCount: (payload.supplements as unknown[]).length,
          })
        );
      } catch {
        /* sessionStorage unavailable — report page degrades gracefully */
      }
      router.push(`/reports/${report.report_id}`);
    } catch (e) {
      const err = e as { api?: ApiError };
      if (err.api) setApiError(err.api);
      else setFormError("요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  return (
    <main className="wrap">
      <span className="screen-tag">S-02 · /intake</span>
      <h1>{step === 1 ? "기본 정보를 입력해 주세요" : "복용 중인 영양제를 입력해 주세요"}</h1>
      <p className="lede">
        {step === 1
          ? "입력하신 정보만으로 계산합니다. 비워 두신 항목은 국가 기준값을 적용합니다."
          : "복용 중인 영양제가 있으면 추가해 주세요. 없으면 건너뛸 수 있습니다."}
      </p>

      <div className="steps">
        <span className={step === 1 ? "on" : ""}>1 기본 정보</span>
        <i>›</i>
        <span className={step === 2 ? "on" : ""}>2 복용 중인 영양제</span>
        <i>›</i>
        <span>3 리포트</span>
      </div>

      {refError && (
        <div className="callout warn">
          기준 데이터를 불러오지 못했습니다. 백엔드(API)가 실행 중인지 확인해
          주세요.
        </div>
      )}

      {apiError && (
        <div className="card" role="alert">
          <div className="block-head">
            <span className="block-num">!</span>
            <h2>결과를 제공할 수 없습니다</h2>
          </div>
          <div className="callout warn" style={{ marginBottom: 12 }}>
            {apiError.message}
          </div>
          {apiError.detail && (
            <p style={{ margin: "0 0 8px", color: "var(--ink-dim)" }}>
              {apiError.detail}
            </p>
          )}
          {apiError.referral && (
            <p style={{ margin: 0, fontWeight: 600 }}>{apiError.referral}</p>
          )}
        </div>
      )}

      {formError && <div className="callout warn">{formError}</div>}

      {step === 1 && (
        <>
          <section className="card">
            <div className="grid-2">
              <div className="field">
                <label htmlFor="age">
                  나이 <span className="req">*</span>
                </label>
                <input
                  type="number"
                  id="age"
                  value={age}
                  min={19}
                  max={120}
                  onChange={(e) => setAge(e.target.value)}
                />
                <p className="why">
                  만 19세 이상 성인만 이용할 수 있습니다. 소아·청소년은 연령
                  구간 기준이 달라 별도 검토가 필요합니다.
                </p>
              </div>

              <div className="field">
                <label id="sex-label">
                  성별 <span className="req">*</span>
                </label>
                <div className="seg" role="group" aria-labelledby="sex-label">
                  <button
                    type="button"
                    aria-pressed={sex === "M"}
                    onClick={() => setSex("M")}
                  >
                    남성
                  </button>
                  <button
                    type="button"
                    aria-pressed={sex === "F"}
                    onClick={() => setSex("F")}
                  >
                    여성
                  </button>
                </div>
                <p className="why">
                  <strong>건너뛸 수 없는 항목입니다.</strong> 2025 섭취기준에는
                  성인 구간에 성별 공통 기준이 없습니다. 예를 들어 철은 여성
                  12mg, 남성 8mg으로 기준 자체가 다릅니다.
                </p>
              </div>
            </div>

            <div className="grid-2">
              <div className="field">
                <label htmlFor="weight">체중 (kg)</label>
                <input
                  type="number"
                  id="weight"
                  value={weight}
                  placeholder="선택 입력"
                  onChange={(e) => setWeight(e.target.value)}
                />
                <p className="why">
                  저장은 하지만{" "}
                  <strong>현재 추천 결과에는 반영되지 않습니다.</strong> 2025
                  섭취기준의 비타민·무기질 항목에는 체중 기반 산출값이 없습니다.
                </p>
              </div>

              <div className="field">
                <label htmlFor="goal">관심 있는 목표</label>
                <select
                  id="goal"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                >
                  {GOALS.map((g) => (
                    <option key={g.value} value={g.value}>
                      {g.label}
                    </option>
                  ))}
                </select>
                <p className="why">
                  추천 순서에만 반영되며, 용량 계산에는 영향을 주지 않습니다.
                </p>
              </div>
            </div>
          </section>

          <section className="card">
            <h2>해당되는 항목이 있으신가요?</h2>
            <div className="checks">
              <label>
                <input
                  type="checkbox"
                  checked={isPregnant}
                  onChange={(e) => setIsPregnant(e.target.checked)}
                />{" "}
                임신 중
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={isLactating}
                  onChange={(e) => setIsLactating(e.target.checked)}
                />{" "}
                수유 중
              </label>
            </div>
            <div className="callout warn" style={{ marginTop: 14 }}>
              임신·수유 중에는 결과를 제공하지 않고 산부인과 상담을 안내합니다.
              임신부 기준은 별도 가산값이며, 수유부 기준은 현재 데이터에
              포함되어 있지 않습니다.
            </div>
          </section>

          <section className="card">
            <h2>복용 중인 약</h2>
            <p className="lede" style={{ marginBottom: 14 }}>
              영양제와 함께 복용할 때 간격을 두어야 하는 약이 있습니다.
            </p>
            <div className="checks">
              {ref?.drug_classes.map((d) => (
                <label key={d.code}>
                  <input
                    type="checkbox"
                    checked={meds.has(d.code)}
                    onChange={() => toggleMed(d.code)}
                  />{" "}
                  {d.label_ko}
                </label>
              ))}
              <label>
                <input
                  type="checkbox"
                  checked={noMeds}
                  onChange={(e) => {
                    setNoMeds(e.target.checked);
                    if (e.target.checked) setMeds(new Set());
                  }}
                />{" "}
                해당 없음
              </label>
            </div>
            <p className="why" style={{ marginTop: 12 }}>
              목록에 없는 약은 <strong>평가되지 않음</strong>으로 표시되며,
              약사 상담을 안내합니다.
            </p>
          </section>

          <section className="card">
            <h2>
              건강검진 수치{" "}
              <span
                style={{
                  fontWeight: 400,
                  color: "var(--ink-faint)",
                  fontSize: 13,
                }}
              >
                선택
              </span>
            </h2>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="hb">헤모글로빈 (g/dL)</label>
                <input
                  type="number"
                  id="hb"
                  value={hb}
                  step={0.1}
                  placeholder="선택 입력"
                  onChange={(e) => setHb(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="vd">비타민 D (ng/mL)</label>
                <input
                  type="number"
                  id="vd"
                  value={vitd}
                  step={0.1}
                  placeholder="선택 입력"
                  onChange={(e) => setVitd(e.target.value)}
                />
              </div>
            </div>
            <div className="callout info">
              검진 수치는 <strong>우선순위 판단에만</strong> 사용됩니다. 목표
              섭취량을 올리지 않습니다. 수치 이상에 대한 치료 용량은 의료
              영역이며 이 서비스의 범위가 아닙니다.
            </div>
          </section>

          <div className="actions">
            <span className="spacer"></span>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                if (validateStep1()) setStep(2);
              }}
            >
              다음 — 복용 중인 영양제
            </button>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <section className="card">
            <h2>복용 중인 영양제</h2>
            <p className="lede" style={{ marginBottom: 14 }}>
              영양소, 형태, 용량을 선택해 주세요. 형태는 원소량 환산에
              사용됩니다.
            </p>

            {rows.map((r, i) => {
              const n = nutrientOf(r.nutrient_code);
              return (
                <div className="supp-row" key={i}>
                  <div className="field">
                    <label>영양소</label>
                    <select
                      value={r.nutrient_code}
                      onChange={(e) =>
                        updateRow(i, {
                          nutrient_code: e.target.value,
                          form_ko: "",
                        })
                      }
                    >
                      <option value="">선택</option>
                      {ref?.nutrients.map((nn) => (
                        <option key={nn.nutrient_code} value={nn.nutrient_code}>
                          {nn.nutrient_ko}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label>형태</label>
                    <select
                      value={r.form_ko}
                      disabled={!n?.forms?.length}
                      onChange={(e) => updateRow(i, { form_ko: e.target.value })}
                    >
                      <option value="">
                        {n?.forms?.length ? "선택 안 함" : "형태 없음"}
                      </option>
                      {n?.forms?.map((f) => (
                        <option key={f.name_ko} value={f.name_ko}>
                          {f.name_ko}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label>용량</label>
                    <input
                      type="number"
                      value={r.dose}
                      min={0}
                      onChange={(e) => updateRow(i, { dose: e.target.value })}
                    />
                  </div>

                  <div className="field">
                    <label>단위</label>
                    <div className="unit-box">{n?.target_unit ?? "—"}</div>
                  </div>

                  <div className="field">
                    <label>1일 횟수</label>
                    <input
                      type="number"
                      value={r.doses_per_day}
                      min={1}
                      max={24}
                      onChange={(e) =>
                        updateRow(i, { doses_per_day: e.target.value })
                      }
                    />
                  </div>

                  <button
                    type="button"
                    className="rm"
                    aria-label="행 삭제"
                    onClick={() =>
                      setRows((prev) =>
                        prev.length === 1
                          ? [emptyRow()]
                          : prev.filter((_, idx) => idx !== i)
                      )
                    }
                  >
                    삭제
                  </button>
                </div>
              );
            })}

            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setRows((prev) => [...prev, emptyRow()])}
            >
              + 영양제 추가
            </button>
          </section>

          <div className="actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setStep(1)}
            >
              이전
            </button>
            <span className="spacer"></span>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={submitting}
              onClick={() => submit(false)}
            >
              영양제 입력 건너뛰기
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={submitting}
              onClick={() => submit(true)}
            >
              {submitting ? "분석 중…" : "분석하기"}
            </button>
          </div>
        </>
      )}

      <p className="disclaimer">
        본 서비스는 진단·치료를 목적으로 하지 않으며, 2025 한국인 영양소
        섭취기준에 근거한 참고 정보를 제공합니다. 질환이 있거나 약을 복용
        중이신 경우 의사·약사와 상담하세요.
      </p>
    </main>
  );
}
