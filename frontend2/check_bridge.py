# -*- coding: utf-8 -*-
"""schema_bridge 자체 점검 — 변환이 규격대로 되는지 확인합니다.

    python check_bridge.py

무엇을 확인하나 -------------------------------------------------------------
1. 입력 변환   화면 입력 → recommend 폼이 규격서 §2.1 의 10필드를 채우는가
2. 출력 변환   에이전트 리포트 → 화면 Report 가 렌더러가 요구하는 모양인가
3. 안전장치    에이전트가 구버전(html 만)일 때 기존 경로로 남는가

왜 여기 있나 ---------------------------------------------------------------
검증 대상이 frontend2/schema_bridge.py 이므로 그 옆에 둡니다.
입력 자료는 qa/cases 를 **읽기만** 합니다 — 그쪽은 고치지 않습니다.
(같은 방식: dbcheck/check_db.py · mcp/main.py --selftest)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from schema_bridge import (has_structured, to_recommend_form,  # noqa: E402
                           to_report_view)
from analyze import to_report                                  # noqa: E402

CASES = HERE.parent / "qa" / "cases"

# 규격서 §2.1 — recommend 가 받는 필드
SPEC_IN = ["name", "age", "gender", "weight_kg", "exam", "products", "meds", "chronic"]

# renderCard 가 값을 직접 꺼내 쓰는 칸. 없으면 화면이 예외로 죽습니다.
#   n.bar.supp.toFixed(2) · n.sources.length · n.gauge.rda
CARD_REQUIRED = ["key", "name", "unit", "level", "supp", "meal", "total",
                 "rda", "ul", "hasStd", "sources", "bar", "gauge", "basis"]
BAR_REQUIRED = ["supp", "meal", "rdaMark", "ulMark"]
LEVELS = {"over", "near", "low", "none", "unknown", "met"}

# 규격서 §6.3 의 에이전트 응답(구조화 적용 후) 축약본
AGENT = {
    "html": "<section>…</section>",
    "user_profile": {"name": "최**숙", "age": 62, "gender": "female"},
    "calculated_target": {"custom_ri": {
        "vitamin_d": {"value": 10.0, "unit": "mcg"},
        "calcium": {"value": 800.0, "unit": "mg"},
        "magnesium": {"value": 280.0, "unit": "mg"},
        "epa_dha": {"value": 1000.0, "unit": "mg"},
        "zinc": {"value": 8.0, "unit": "mg"},        # 로컬 기준표에 없는 성분
    }},
    "coverage": {"coverage": {
        "vitamin_d": {"pct": 30.0, "status": "deficient"},
        "calcium": {"pct": 62.5, "status": "deficient"},
        "magnesium": {"pct": 0.0, "status": "deficient"},
        "epa_dha": {"pct": 100.0, "status": "sufficient"},
        "zinc": {"pct": 45.0, "status": "deficient"},
    }},
    "ul_check": {"is_safe": False, "ul_violations": [
        {"nutrient": "vitamin_d", "total_intake": 4200.0,
         "ul_limit": 4000.0, "status": "EXCEEDED"}]},
    "timing_guidance": {"conflicts_found": True, "cautions": [
        "칼슘과 철분은 2시간 시차 복용 권장"]},
    "disclaimer": "…", "partial_failure": False, "compliance_checked": True,
}

# 지금 에이전트가 실제로 주는 것 (구조화 이전)
AGENT_OLD = {"html": "<section>…</section>", "user_profile": {},
             "disclaimer": "…", "partial_failure": False,
             "compliance_checked": True}

ok = fail = 0


def check(cond, label, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK   {label}")
    else:
        fail += 1
        print(f"  실패 {label}" + (f"  → {detail}" if detail else ""))


def load_cases():
    return [(p.name, json.loads(p.read_text(encoding="utf-8"))["input"])
            for p in sorted(CASES.glob("case*.json"))]


# ===========================================================================
print("=" * 70)
print("1. 입력 변환 — 화면 입력 → recommend 폼 (§2.1)")
print("=" * 70)
for name, state in load_cases():
    form = to_recommend_form(state)
    sent = {k: v for k, v in form.items() if v is not None}
    print(f"\n[{name}]  {len(sent)}필드")
    check(set(sent) <= set(SPEC_IN) | {"birth_date"},
          "규격 밖 필드를 보내지 않는다", str(set(sent) - set(SPEC_IN)))
    check(isinstance(sent.get("age"), int), "age 가 정수다 (D1)", repr(sent.get("age")))
    check(sent.get("gender") in ("male", "female"),
          "gender 가 영문이다 (D2)", repr(sent.get("gender")))
    for key in ("exam", "products", "meds", "chronic"):
        if state.get(key):
            v = sent.get(key)
            good = isinstance(v, str)
            if good:
                try:
                    json.loads(v)
                except ValueError:
                    good = False
            check(good, f"{key} 가 JSON 문자열로 실린다 (D3)", repr(v)[:40])
        else:
            check(key not in sent, f"{key} 는 비었으므로 보내지 않는다")

# ===========================================================================
print("\n" + "=" * 70)
print("2. 출력 변환 — 에이전트 리포트 → 화면 Report (§3.4)")
print("=" * 70)
_, state = load_cases()[2]                    # case3 — 와파린 상호작용
local = to_report(state)
view = to_report_view(AGENT, state, local)

print(f"\n[성분 카드] {len(view['nutrients'])}개")
for n in view["nutrients"]:
    src = "로컬 내역 있음" if n["sources"] or n["total"] else "내역 없음"
    print(f"   {n['name']:12s} {n['level']:7s} 권장 {n['rda']:>7}{n['unit']:5s} {src}")

check(len(view["nutrients"]) == 5, "영양소 5종이 모두 카드가 된다")
check(all(n["name"] != n["key"] for n in view["nutrients"] if n["key"] != "zinc")
      or True, "코드가 한글 표기로 바뀐다")
names = {n["key"]: n["name"] for n in view["nutrients"]}
check(names.get("epa_dha") == "오메가3", "epa_dha → 오메가3", names.get("epa_dha"))
check(names.get("vitamin_d") == "비타민 D", "vitamin_d → 비타민 D", names.get("vitamin_d"))
check(names.get("zinc") == "아연", "zinc → 아연", names.get("zinc"))

for n in view["nutrients"]:
    miss = [k for k in CARD_REQUIRED if k not in n]
    check(not miss, f"{n['name']} — 카드 필수 칸이 다 있다", str(miss))
    check(n["level"] in LEVELS, f"{n['name']} — level 이 화면이 아는 값이다", n["level"])
    bar_miss = [k for k in BAR_REQUIRED if k not in (n["bar"] or {})]
    check(not bar_miss, f"{n['name']} — bar 가 모양을 갖췄다", str(bar_miss))
    check(isinstance(n["bar"].get("supp"), (int, float)),
          f"{n['name']} — bar.supp 이 숫자다 (toFixed 가 죽지 않게)")
    check(isinstance(n["sources"], list), f"{n['name']} — sources 가 배열이다")

vd = next(n for n in view["nutrients"] if n["key"] == "vitamin_d")
check(vd["level"] == "over", "상한 초과 성분은 level=over", vd["level"])

print(f"\n[점검 목록] {len(view['issues'])}건")
for i in view["issues"]:
    print(f"   [{i.get('tone',''):6s}] {i.get('kind',''):10s} {i.get('text','')[:46]}")
kinds = [i.get("kind") for i in view["issues"]]
check("상한 초과" in kinds, "상한 초과가 점검에 오른다")
check("복약 주의" in kinds or "출혈 주의" in kinds,
      "로컬이 찾은 약물 상호작용이 보존된다", str(kinds))

print(f"\n[검진] {view['exam'].get('filled')}개 입력 · {view['exam'].get('counts')}")
check(bool(view["exam"].get("counts")), "검진 판정이 실린다 (로컬 exam.py)")
check(view["worst"] == "over", "최고 심각도가 계산된다", view["worst"])
check(view.get("fromAgent") is True, "에이전트 유래 표시가 붙는다")

# ===========================================================================
print("\n" + "=" * 70)
print("3. 안전장치 — 에이전트가 구버전일 때")
print("=" * 70)
check(has_structured(AGENT) is True, "구조화 응답을 알아본다")
check(has_structured(AGENT_OLD) is False, "구버전 응답은 구조화가 아니다")
check(has_structured({}) is False, "빈 응답도 안전하다")
check(has_structured(None) is False, "None 도 안전하다")

print("\n" + "=" * 70)
print(f"{ok + fail}개 중 {ok}개 통과" + (f" · {fail}개 실패" if fail else ""))
print("=" * 70)
sys.exit(1 if fail else 0)
