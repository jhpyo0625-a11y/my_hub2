# -*- coding: utf-8 -*-
"""케이스 4개를 frontend2 판정 엔진에 통과시키고 기대값과 대조한다.

    python run_local.py            → out/before/ 에 저장
    python run_local.py --after    → out/after/  에 저장 (개선 후)

콘솔 출력은 요약만 하고, 자세한 것은 파일로 남깁니다.
(이 환경 콘솔이 CP949 라서 출력에 기대면 깨집니다)
"""
import sys
from pathlib import Path

import engine
from engine import QA_DIR

STAGE = "after" if "--after" in sys.argv else "before"
OUT = QA_DIR / "out" / STAGE


# ---------------------------------------------------------------------------
# 판정 결과 뽑아내기
# ---------------------------------------------------------------------------
def levels_by_name(report):
    return {n["name"]: n["level"] for n in report["nutrients"]}


def judges_by_key(report):
    """exam 결과에서 항목별 판정 코드를 꺼냅니다.

    judge 는 {"code","text","tone"} 중첩 dict 입니다.
    미입력(J("N"))은 code 가 빈 문자열로 나오므로, 기대값에서 쓰는 "N" 으로
    되돌려 둡니다 — 빈 문자열은 '판정 없음'과 구분이 안 되기 때문입니다.
    """
    out = {}
    for row in report.get("exam", {}).get("rows", []):
        key = row.get("key")
        if not key:
            continue
        code = (row.get("judge") or {}).get("code", "")
        out[key] = code if code else "N"
    return out


def issue_kinds(report):
    return [i.get("kind", "") for i in report.get("issues", [])]


def unmapped_names(report):
    names = []
    for n in report["nutrients"]:
        for u in (n.get("unmapped") or []):
            names.append(u if isinstance(u, str) else u.get("name", ""))
    return [x for x in names if x]


# ---------------------------------------------------------------------------
# 채점
# ---------------------------------------------------------------------------
class Result:
    def __init__(self):
        self.rows = []          # (구분, 항목, 기대, 실제, 통과여부)

    def check(self, group, item, want, got):
        self.rows.append((group, item, want, got, want == got))

    def check_in(self, group, item, want_list, got_list):
        ok = all(w in got_list for w in want_list)
        self.rows.append((group, item, ", ".join(map(str, want_list)) or "(없음)",
                          ", ".join(map(str, got_list)) or "(없음)", ok))

    def check_min(self, group, item, minimum, got):
        self.rows.append((group, item, f">= {minimum}", str(got), got >= minimum))

    @property
    def passed(self):
        return sum(1 for r in self.rows if r[4])

    @property
    def total(self):
        return len(self.rows)


def score_case(case, exp, report):
    r = Result()
    lv = levels_by_name(report)
    jd = judges_by_key(report)
    kinds = issue_kinds(report)

    for key, want in (exp.get("exam_judges") or {}).items():
        r.check("검진 판정", key, want, jd.get(key, "(항목없음)"))

    for name, want in (exp.get("nutrient_levels") or {}).items():
        r.check("성분 레벨", name, want, lv.get(name, "(성분없음)"))

    if "worst" in exp:
        r.check("종합", "worst", exp["worst"], report.get("worst"))

    if "issues_kinds" in exp:
        r.check_in("점검 항목", "필수 포함", exp["issues_kinds"], kinds)

    if "issues_min_count" in exp:
        r.check_min("점검 항목", "건수", exp["issues_min_count"], len(kinds))

    if "exam_abnormal_count" in exp:
        r.check("검진", "이상 소견 수",
                exp["exam_abnormal_count"], len(report.get("exam", {}).get("abnormal") or []))

    if "exam_abnormal_min" in exp:
        r.check_min("검진", "이상 소견 수",
                    exp["exam_abnormal_min"], len(report.get("exam", {}).get("abnormal") or []))

    if "unmapped_names" in exp:
        # unmapped 는 '이 성분이 무엇인지 모른다'가 아니라 '양을 환산하지
        # 못했다'는 뜻입니다. 문자열이 "제품명: 100억CFU" 형태라 성분명
        # 포함 여부로 봅니다.
        blob = " ".join(unmapped_names(report))
        for want in exp["unmapped_names"]:
            r.rows.append(("환산 실패", want, "기록됨", blob[:50] or "(없음)", want in blob or "CFU" in blob))

    if "unknown_level_names" in exp:
        # 기준표에 없는 성분이 조용히 사라지지 않고 목록에 남는지.
        lv_all = levels_by_name(report)
        for want in exp["unknown_level_names"]:
            r.check("기준 없음", want, "unknown", lv_all.get(want, "★ 목록에서 사라짐"))

    if "duplicate_nutrient" in exp:
        dup = [i for i in report.get("issues", []) if i.get("kind") == "성분 중복"]
        text = " ".join(i.get("text", "") for i in dup)
        r.rows.append(("점검 항목", "중복 성분명",
                       exp["duplicate_nutrient"], text[:60] or "(없음)",
                       exp["duplicate_nutrient"] in text))
    return r


# ---------------------------------------------------------------------------
# 사람이 읽을 리포트 (HTML)
# ---------------------------------------------------------------------------
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def case_html(case, report, result):
    lv = levels_by_name(report)
    badge = {"over": "#B91C1C", "near": "#C2410C", "low": "#1D4ED8",
             "met": "#047857", "none": "#6B7280", "unknown": "#6B7280"}
    rows = "".join(
        f"<tr><td>{esc(n['name'])}</td><td>{esc(n['level'])}</td>"
        f"<td>{esc(n['supp'])}</td><td>{esc(n['meal'])}</td><td>{esc(n['total'])}</td>"
        f"<td>{esc(n['rda'])}</td><td>{esc(n['ul'])}</td>"
        f"<td>{esc(n.get('caption', ''))}</td></tr>"
        for n in report["nutrients"]
    )
    issues = "".join(
        f"<li><b>{esc(i.get('kind'))}</b> — {esc(i.get('text'))}</li>"
        for i in report.get("issues", [])
    ) or "<li>(없음)</li>"
    checks = "".join(
        f"<tr class='{'ok' if ok else 'ng'}'><td>{esc(g)}</td><td>{esc(it)}</td>"
        f"<td>{esc(w)}</td><td>{esc(got)}</td><td>{'통과' if ok else '실패'}</td></tr>"
        for g, it, w, got, ok in result.rows
    )
    return f"""<!doctype html><meta charset="utf-8">
<title>{esc(case['id'])} · {esc(case['title'])}</title>
<style>
 body{{font:14px/1.7 system-ui,'Malgun Gothic',sans-serif;margin:32px;max-width:1100px;color:#111}}
 h1{{font-size:20px}} h2{{font-size:15px;margin-top:28px;border-top:1px solid #ddd;padding-top:14px}}
 table{{border-collapse:collapse;width:100%;font-size:12.5px}}
 th,td{{border:1px solid #ddd;padding:6px 8px;text-align:left}}
 th{{background:#f5f7fa}}
 tr.ok td{{background:#f0fdf4}} tr.ng td{{background:#fef2f2}}
 .p{{color:#555}}
</style>
<h1>{esc(case['id'])} · {esc(case['title'])}</h1>
<p class="p">{esc(case['persona'])}</p>
<h2>채점 {result.passed}/{result.total}</h2>
<table><tr><th>구분</th><th>항목</th><th>기대</th><th>실제</th><th>결과</th></tr>{checks}</table>
<h2>점검 항목 (상호작용 · 중복)</h2><ul>{issues}</ul>
<h2>성분 {len(report['nutrients'])}개</h2>
<table><tr><th>성분</th><th>레벨</th><th>영양제</th><th>식사</th><th>합계</th>
<th>권장</th><th>상한</th><th>설명</th></tr>{rows}</table>
"""


# ---------------------------------------------------------------------------
def main():
    cases = engine.load_cases()
    expected = engine.load_expected()

    # 기준값이 기대값 작성 시점과 달라졌는지 먼저 확인합니다.
    fp_path = QA_DIR / "baseline_standards.json"
    now_fp = engine.standards_fingerprint()
    drift = []
    if fp_path.exists():
        old = engine.read_json(fp_path)
        for name, cur in now_fp.items():
            if name in old and old[name] != cur:
                drift.append((name, old[name], cur))
        for name in old:
            if name not in now_fp:
                drift.append((name, old[name], "(삭제됨)"))
    else:
        engine.write_json(fp_path, now_fp)

    lines = ["# 판정 엔진 채점 결과 (%s)" % STAGE, ""]
    if drift:
        lines += ["## ⚠ 기준값이 바뀌었습니다", "",
                  "기대값은 작성 시점의 standards.py 를 보고 손계산한 것입니다.",
                  "아래 항목이 달라졌으므로 expected.json 재검토가 필요합니다.", ""]
        for name, o, n in drift:
            lines.append(f"- **{name}**: `{o}` → `{n}`")
        lines.append("")

    total_p = total_n = 0
    summary = []
    for case in cases:
        exp = expected.get(case["id"], {})
        report = engine.to_report(case["input"])
        result = score_case(case, exp, report)
        total_p += result.passed
        total_n += result.total

        engine.write_json(OUT / f"{case['id']}.json", report)
        engine.write_text(OUT / f"{case['id']}.html", case_html(case, report, result))
        summary.append((case, result))

    lines += ["## 요약", "",
              f"**{total_p}/{total_n} 통과**", "",
              "| 케이스 | 제목 | 통과 | 취약 |", "|---|---|---|---|"]
    for case, result in summary:
        mark = "★ 경계" if case.get("brittle") else ""
        lines.append(f"| {case['id']} | {case['title']} | {result.passed}/{result.total} | {mark} |")

    lines += ["", "## 실패 항목", ""]
    any_fail = False
    for case, result in summary:
        fails = [r for r in result.rows if not r[4]]
        if not fails:
            continue
        any_fail = True
        lines.append(f"### {case['id']} — {case['title']}")
        lines.append("")
        lines.append("| 구분 | 항목 | 기대 | 실제 |")
        lines.append("|---|---|---|---|")
        for g, it, w, got, _ in fails:
            lines.append(f"| {g} | {it} | `{w}` | `{got}` |")
        lines.append("")
    if not any_fail:
        lines.append("없음 — 전 항목 통과")

    engine.write_text(OUT / "score.md", "\n".join(lines) + "\n")
    print(f"[{STAGE}] {total_p}/{total_n} 통과  ->  {OUT}")
    for case, result in summary:
        print(f"   {case['id']}  {result.passed}/{result.total}")


if __name__ == "__main__":
    main()
