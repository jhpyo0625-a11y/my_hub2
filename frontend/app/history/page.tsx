"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listReports, type ReportListItem } from "@/lib/api";

const GOAL_KO: Record<string, string> = {
  sleep: "수면·이완",
  fatigue: "피로 개선",
  bone: "뼈 건강",
  anemia: "빈혈 개선",
};

function goalLabel(goals: string[]): string {
  const named = goals.map((g) => GOAL_KO[g] ?? g).filter(Boolean);
  return named.length ? named.join(" · ") : "목표 미선택";
}

function when(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPage() {
  const [reports, setReports] = useState<ReportListItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <main className="wrap">
        <span className="screen-tag">S-09 · /history</span>
        <h1>지난 결과</h1>
        <div className="callout warn">
          히스토리를 불러오지 못했습니다. 백엔드(API)가 실행 중인지 확인해 주세요.
        </div>
      </main>
    );
  }

  if (!reports) {
    return (
      <main className="wrap">
        <span className="screen-tag">S-09 · /history</span>
        <h1>지난 결과</h1>
        <p className="lede">불러오는 중입니다…</p>
      </main>
    );
  }

  return (
    <main className="wrap">
      <span className="screen-tag">S-09 · /history</span>
      <h1>지난 결과</h1>
      <p className="lede">
        입력을 수정할 때마다 새 버전이 만들어집니다. 이전 버전은 지워지지
        않습니다.
      </p>

      {reports.length === 0 ? (
        <section className="card">
          <p style={{ margin: "0 0 16px" }}>
            아직 저장된 분석 결과가 없습니다. 첫 분석을 시작해 보세요.
          </p>
          <div className="actions">
            <Link className="btn btn-primary" href="/intake">
              새로 분석하기
            </Link>
          </div>
        </section>
      ) : (
        <section className="card">
          <div className="chain">
            {reports.map((r) => {
              const s = r.summary;
              return (
                <div className="chain-item" key={r.report_id}>
                  <div className="ver">
                    v{r.version}
                    {s.over > 0 ? (
                      <span className="pill over" style={{ marginLeft: 6 }}>
                        상한 초과 {s.over}
                      </span>
                    ) : (
                      <span className="pill adequate" style={{ marginLeft: 6 }}>
                        상한 초과 0
                      </span>
                    )}
                  </div>
                  <div className="meta">
                    {when(r.created_at)} · {goalLabel(r.goals)} · 영양제{" "}
                    {r.supplement_count}건 · 부족 {s.deficit} · 판단 보류{" "}
                    {s.unknown}
                    {r.parent_id != null && " · 이전 입력에서 수정됨"}
                  </div>
                  <div className="actions" style={{ marginTop: 8 }}>
                    <Link
                      className="btn btn-ghost btn-sm"
                      href={`/reports/${r.report_id}`}
                    >
                      리포트 보기
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <div className="callout info">
        각 버전은 계산 당시의 입력과 근거를 그대로 보관합니다. 기준이 개정되어도
        과거 리포트의 숫자와 설명은 바뀌지 않습니다.
      </div>

      <div className="actions">
        <Link className="btn btn-primary" href="/intake">
          새로 분석하기
        </Link>
      </div>

      <p className="disclaimer">
        저장된 건강 정보는 본인만 조회할 수 있습니다.
      </p>
    </main>
  );
}
