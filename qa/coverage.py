# -*- coding: utf-8 -*-
"""사용자가 입력한 것 중 얼마나 리포트에 반영되는가.

    python coverage.py

배경 ---------------------------------------------------------------------
결과보기는 frontend2 가 직접 계산하지 않고 에이전트(/api/v1/recommend)에
넘깁니다. 그런데 그 API 가 받는 인자는 name·birth_date·age·gender·
weight_kg·file 여섯 개뿐입니다. 영양제·복용약·검진 수치를 받을 자리가
아예 없습니다.

이 스크립트는 '입력한 것'과 '전달되는 것'을 세어서, 무엇이 어디서
사라지는지 숫자로 보여 줍니다. 에이전트를 띄우지 않아도 됩니다 —
전달 규칙은 frontend2/server.py 의 analyze() 에 적혀 있고 여기서 그대로
따라 하기 때문입니다.
"""
import engine
from engine import QA_DIR

# frontend2/server.py 의 analyze() 가 실제로 채워 보내는 필드.
AGENT_FIELDS = ["name", "age", "gender", "weight_kg"]
AGENT_OPTIONAL = ["file", "birth_date"]


def count_input(state):
    exam = {k: v for k, v in (state.get("exam") or {}).items() if str(v).strip()}
    products = state.get("products") or []
    ingredients = sum(len(p.get("items") or []) for p in products)
    meds = state.get("meds") or []
    chronic = state.get("chronic") or []

    basic = [k for k in ("name", "age", "sex", "date") if str(state.get(k) or "").strip()]

    return {
        "기본정보": len(basic),
        "검진수치": len(exam),
        "영양제 성분": ingredients,
        "복용 약": len(meds),
        "만성질환": len(chronic),
        "식사반영": 1 if state.get("countMeal") else 0,
        "_products": len(products),
    }


def count_delivered(state):
    """에이전트에 실제로 실려 가는 값의 개수."""
    exam = state.get("exam") or {}
    sent = 0
    if str(state.get("name") or "").strip():
        sent += 1
    if str(state.get("age") or "").strip():
        sent += 1
    if state.get("sex") in ("남성", "여성"):
        sent += 1
    # weight 는 숫자로 읽히는 경우에만 (server.py 의 _as_number 와 같은 규칙)
    try:
        float(str(exam.get("weight", "")).strip())
        sent += 1
    except (TypeError, ValueError):
        pass
    return sent


def findings(report):
    """로컬 엔진이 찾아낸 것 — 에이전트 경로에서는 나올 수 없는 항목들."""
    over = [n["name"] for n in report["nutrients"] if n["level"] == "over"]
    near = [n["name"] for n in report["nutrients"] if n["level"] == "near"]
    issues = [(i.get("kind"), i.get("text", "")[:60]) for i in report.get("issues", [])]
    abnormal = [(a["name"], (a.get("judge") or {}).get("code", ""))
                for a in (report.get("exam", {}).get("abnormal") or [])]
    return {"over": over, "near": near, "issues": issues, "abnormal": abnormal}


def main():
    cases = engine.load_cases()
    rows = []
    detail = []

    for case in cases:
        state = case["input"]
        report = engine.to_report(state)
        c = count_input(state)
        total_in = sum(v for k, v in c.items() if not k.startswith("_"))
        sent = count_delivered(state)
        f = findings(report)

        rows.append({
            "id": case["id"], "title": case["title"],
            "total_in": total_in, "sent": sent,
            "rate": round(sent / total_in * 100) if total_in else 0,
            "counts": c, "f": f,
        })

        detail.append((case, c, sent, f))

    # ---- 마크다운 리포트 -------------------------------------------------
    L = []
    L.append("# 입력 반영률 — 사용자가 넣은 것 중 리포트에 쓰이는 비율")
    L.append("")
    L.append("결과보기는 에이전트(`POST /api/v1/recommend`)가 처리합니다.")
    L.append("그 API 가 받는 인자는 `name` `birth_date` `age` `gender` `weight_kg` `file` 뿐이라,")
    L.append("**영양제·복용약·검진수치는 전달할 자리가 없습니다.**")
    L.append("")
    L.append("| 케이스 | 입력 항목 | 전달 | 반영률 | 버려지는 것 |")
    L.append("|---|---|---|---|---|")
    for r in rows:
        c = r["counts"]
        dropped = []
        if c["검진수치"]:
            dropped.append(f"검진 {c['검진수치']}")
        if c["영양제 성분"]:
            dropped.append(f"성분 {c['영양제 성분']}")
        if c["복용 약"]:
            dropped.append(f"약 {c['복용 약']}")
        if c["만성질환"]:
            dropped.append(f"질환 {c['만성질환']}")
        L.append(f"| {r['id']} | {r['total_in']} | {r['sent']} | **{r['rate']}%** | "
                 f"{', '.join(dropped) or '—'} |")

    L.append("")
    L.append("## 리포트에서 사라지는 판정")
    L.append("")
    L.append("로컬 엔진(같은 입력)은 아래를 찾아냅니다. 에이전트 경로에서는")
    L.append("입력 자체가 전달되지 않으므로 **구조적으로 나올 수 없습니다.**")
    L.append("")

    tot_over = tot_issue = tot_abn = 0
    for case, c, sent, f in detail:
        L.append(f"### {case['id']} — {case['title']}")
        L.append("")
        if f["over"]:
            L.append(f"- **상한 초과**: {', '.join(f['over'])}")
            tot_over += len(f["over"])
        if f["near"]:
            L.append(f"- 상한 근접: {', '.join(f['near'])}")
        for kind, text in f["issues"]:
            L.append(f"- **{kind}**: {text}")
        tot_issue += len(f["issues"])
        if f["abnormal"]:
            names = ", ".join(f"{n}({c2})" for n, c2 in f["abnormal"])
            L.append(f"- **검진 이상 소견 {len(f['abnormal'])}건**: {names}")
            tot_abn += len(f["abnormal"])
        if not (f["over"] or f["near"] or f["issues"] or f["abnormal"]):
            L.append("- (특이 소견 없음)")
        L.append("")

    L.append("## 합계")
    L.append("")
    L.append(f"- 상한 초과 **{tot_over}건**")
    L.append(f"- 상호작용·중복 점검 **{tot_issue}건**")
    L.append(f"- 검진 이상 소견 **{tot_abn}건**")
    L.append("")
    L.append("모두 사용자가 입력했지만 리포트에 반영되지 않습니다.")

    engine.write_text(QA_DIR / "out" / "coverage.md", "\n".join(L) + "\n")
    engine.write_json(QA_DIR / "out" / "coverage.json", rows)

    print("입력 반영률")
    for r in rows:
        print(f"   {r['id']}  {r['sent']}/{r['total_in']}  ({r['rate']}%)")
    print(f"\n미반영: 상한초과 {tot_over} · 점검 {tot_issue} · 검진이상 {tot_abn}")
    print(f"-> {QA_DIR / 'out' / 'coverage.md'}")


if __name__ == "__main__":
    main()
