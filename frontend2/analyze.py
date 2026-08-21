"""
analyze.py — Input 을 받아 Report 를 만듭니다  (★ 이 서비스의 핵심)
==============================================================================
'백엔드 연동 규격서' 의 §4 Input → §5 Report 변환이 전부 여기 있습니다.
app.js 의 [E] 목업 블록(약 670줄)을 그대로 옮겨 온 것입니다.

화면(live-app.js)에는 판정 코드가 한 줄도 없습니다. "이 성분이 부족한가",
"상한을 넘었는가", "이 약과 부딪히는가" 는 전부 이 파일이 정합니다.
그래서 기준이 바뀌어도 화면을 다시 배포할 필요가 없습니다.

  판정 '기준' → standards.py · exam.py   (교체지점)
  판정 '방법' → 이 파일

돌려주는 값의 모양이 곧 규격입니다. 화면은 이 값을 계산하지 않고 그대로
그리기만 하므로, 필드 하나가 빠지면 그 자리가 비어 보이거나 렌더가 멈춥니다.
==============================================================================
"""

from datetime import datetime, timezone

from standards import (MASS, MED_RULES, STD_LIST, LEVEL_RANK,
                       find_std, level_of, norm_key)
from exam import compute_exam

# 성분 카드 그리드의 최대 열 수. 화면 CSS 가 1~4 만 알아듣습니다.
MAX_COLS = 4


# =============================================================================
# 작은 부품들 — 자바스크립트와 결과가 같아야 하는 것들
# =============================================================================

def to_number(x) -> float:
    """자바스크립트의 Number(x) 와 같게 읽습니다.

    화면이 보내는 값은 전부 문자열입니다. 그중 함량은 비어 있을 수 있는데,
    JS 에서 Number('') 는 0 입니다. 파이썬의 float('') 는 예외를 던지므로
    여기서 맞춰 줍니다. 이 차이를 놓치면 '함량을 비운 성분'이 목업에서는
    0 으로 합산되고 서버에서는 환산 불가로 빠져, 같은 입력에 다른 결과가
    나옵니다.
    """
    if x is None:
        return float("nan")
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s == "":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return float("nan")


def _finite(v: float) -> bool:
    return v == v and v not in (float("inf"), float("-inf"))


def fmt(n) -> str:
    """숫자를 화면에 보여 줄 문구로. 소수점 첫째 자리까지, 천 단위 쉼표.

    JS 의 Number(n).toLocaleString('ko-KR', {maximumFractionDigits:1}) 과
    같은 결과를 냅니다. None 은 0 으로 봅니다(JS 의 Number(null) 이 0).
    """
    v = to_number(n)
    if not _finite(v):
        return "0"
    r = round(v, 1)
    if r == int(r):
        return f"{int(r):,}"
    return f"{r:,.1f}"


# --- 조사 — 앞말의 받침에 따라 은/는, 이/가, 을/를 을 고릅니다 ----------------
_JONG = {"0": 1, "1": 1, "3": 1, "6": 1, "7": 1, "8": 1,
         "2": 0, "4": 0, "5": 0, "9": 0,
         "l": 1, "m": 1, "n": 1, "r": 1, "L": 1, "M": 1, "N": 1, "R": 1}


def josa(word, with_jong: str, without: str) -> str:
    s = str(word or "").strip()
    if not s:
        return f"{word}{without}"
    c = s[-1]
    code = ord(c)
    if 0xAC00 <= code <= 0xD7A3:          # 한글 음절
        has = (code - 0xAC00) % 28 != 0
    elif c in _JONG:                       # 숫자·영문은 읽는 소리로
        has = bool(_JONG[c])
    else:
        has = False
    return f"{word}{with_jong if has else without}"


def eun(w): return josa(w, "은", "는")
def ga(w):  return josa(w, "이", "가")
def eul(w): return josa(w, "을", "를")


def convert(amount, unit, std):
    """입력 단위를 기준표 단위로 환산합니다. 환산할 수 없으면 None."""
    v = to_number(amount)
    if not _finite(v):
        return None
    if unit == "IU":
        # IU 는 성분마다 계수가 달라, 기준표에 iu 가 있는 성분만 환산합니다.
        return v * std["iu"] if (std and std.get("iu")) else None
    if unit not in MASS:
        return None                        # mL · 억CFU 등은 질량이 아닙니다
    mg = v * MASS[unit]
    return mg / MASS[std["unit"]] if std else mg


# =============================================================================
# 성분 — 자유 입력된 성분들을 하나로 모아 합산하고 판정합니다
# =============================================================================
def compute_nutrients(state: dict) -> list:
    bucket = {}      # key → 합산 상태
    count_meal = bool(state.get("countMeal"))

    # [식사 기준 모드] 식사 평균 추정치로 계산하겠다고 켜 두었으면, 사용자가
    # 영양제를 넣지 않은 성분까지 기준표에서 미리 깔아 둡니다. 이렇게 해야
    # '나는 이 성분을 아예 안 챙기고 있다' 가 카드로 보이고, 추천 목록에도
    # 올라갈 수 있습니다.
    if count_meal:
        for std in STD_LIST:
            if not std.get("meal") or std.get("rda") is None:
                continue               # 식사 추정치나 권장량이 없으면 비교 불가
            bucket[std["name"]] = {
                "std": std, "key": std["name"], "label": std["name"],
                "unit": std["unit"], "supp": 0.0, "sources": [], "unmapped": [],
            }

    for p in (state.get("products") or []):
        pname = p.get("name") or "이름 없는 제품"
        for it in (p.get("items") or []):
            name = it.get("name")
            if not name:
                continue
            std = find_std(name)
            key = std["name"] if std else norm_key(name)
            b = bucket.get(key)
            if b is None:
                unit = it.get("unit") or "mg"
                b = bucket[key] = {
                    "std": std, "key": key,
                    "label": std["name"] if std else name.strip(),
                    "unit": std["unit"] if std else ("mg" if unit in MASS else unit),
                    "supp": 0.0, "sources": [],
                    "unmapped": [],        # 환산하지 못한 입력 (IU · mL · 억CFU 등)
                }
            v = convert(it.get("amount"), it.get("unit"), std)
            if v is None:
                b["unmapped"].append(f"{pname}: {it.get('amount') or '?'}{it.get('unit') or ''}")
            else:
                b["supp"] += v
            if pname not in b["sources"]:
                b["sources"].append(pname)

    out = []
    for b in bucket.values():
        std = b["std"]
        meal = float(std["meal"]) if (count_meal and std and std.get("meal")) else 0.0
        supp = b["supp"]
        total = supp + meal
        level = level_of(supp, total, std)
        rda = std.get("rda") if std else None
        ul = std.get("ul") if std else None
        ul_supp_only = bool(std and std.get("ul_basis") == "supp")

        # ── 막대의 기준 길이 ────────────────────────────────────────────────
        # 막대의 오른쪽 끝은 **상한이 아닙니다.** 상한을 끝에 두면 상한을 넘은
        # 값이 전부 막대 끝에 딱 붙어 버려서, 살짝 넘었는지 두 배로 넘었는지가
        # 구분되지 않습니다. 그래서 눈금 뒤에 항상 여유를 둡니다.
        #
        #   0 ─────────┬──────────┬──────────── 끝
        #             권장       상한      ← 상한 뒤에 남는 자리가 '초과분'
        #
        # 아래 세 후보 중 가장 큰 값이 한 칸 전체가 됩니다.
        #   권장×1.6  권장만 있는 성분도 눈금이 가운데쯤 오도록
        #   상한×1.25 상한 뒤에 20% 정도 자리가 남도록
        #   섭취량×1.15 이미 크게 넘긴 값도 끝에 붙지 않고 다 보이도록
        ul_amount = supp if ul_supp_only else total
        cands = [(total or 0) * 1.15, (ul_amount or 0) * 1.15]
        if rda is not None:
            cands.append(rda * 1.6)
        if ul is not None:
            cands.append(ul * 1.25)
        scale = max([c for c in cands if c and c > 0] or [1.0])

        if not std:
            basis = "표준 기준 미등록"
        elif rda is not None and ul is not None:
            basis = (f"권장 {fmt(rda)} · 상한 {fmt(ul)}{std['unit']}"
                     + (" (영양제 기준)" if ul_supp_only else ""))
        elif ul is not None:
            basis = f"상한 {fmt(ul)}{std['unit']}"
        elif rda is not None:
            basis = f"권장 {fmt(rda)}{std['unit']} 이상"
        else:
            basis = "기준 없음"

        out.append({
            "key": b["key"], "name": b["label"], "unit": b["unit"],
            "rda": rda, "ul": ul, "std": std,
            "supp": supp, "meal": meal, "total": total, "level": level,
            # 상한을 실제로 무엇과 비교했는지. 마그네슘·엽산처럼 영양제분만
            # 비교하는 성분은 total 이 아니라 supp 가 기준입니다.
            "ulAmount": ul_amount,
            "ulSuppOnly": ul_supp_only,
            "sources": b["sources"], "unmapped": b["unmapped"],
            "basis": basis,
            "bar": {
                "supp": min(supp / scale, 1) * 100,
                "meal": max(0.0, min(meal / scale, 1 - supp / scale)) * 100,
                "rdaMark": (rda / scale * 100) if (rda is not None and rda <= scale) else None,
                # 상한 눈금의 위치(%). 예전에는 화면이 늘 오른쪽 끝(100%)에
                # 그렸지만, 이제 끝이 상한이 아니므로 좌표를 함께 내려보냅니다.
                "ulMark": (ul / scale * 100) if (ul is not None and ul <= scale) else None,
            },
            "pct": {
                "rda": (total / rda) if rda else ((total / ul) if ul else None),
                "ul": ((supp if ul_supp_only else total) / ul) if ul else
                      ((total / rda) if rda else None),
            },
        })

    # 1순위 위험한 것부터 · 2순위 실제로 먹고 있는 성분을 앞에 ·
    # 3순위 이름순 (순서가 매번 바뀌지 않게)
    out.sort(key=lambda n: (-LEVEL_RANK[n["level"]], -len(n["sources"]), n["name"]))
    return out


# =============================================================================
# 점검 — 상호작용 · 성분 중복 · 환산 실패
# =============================================================================
def compute_issues(state: dict, nutrients: list) -> list:
    out = []

    for n in nutrients:
        if n["level"] == "over":
            out.append({
                "kind": "상한 초과", "tone": "red",
                "text": (f"{n['name']} {'영양제 섭취량' if n['ulSuppOnly'] else '합산량'} "
                         f"{fmt(n['ulAmount'])}{n['unit']}이 상한 {fmt(n['ul'])}{n['unit']}을 "
                         f"넘습니다. 제품 구성을 조정해 보세요."),
            })
        elif n["level"] == "near":
            out.append({
                "kind": "상한 근접", "tone": "orange",
                "text": (f"{ga(n['name'])} 상한의 70%를 넘었습니다. "
                         f"같은 성분이 든 제품을 더하면 초과할 수 있습니다."),
            })

    for n in nutrients:
        if len(n["sources"]) > 1:
            out.append({"kind": "성분 중복", "tone": "blue",
                        "text": f"{ga(n['name'])} {' · '.join(n['sources'])} 에 함께 들어 있습니다."})

    for m in (state.get("meds") or []):
        mname = m.get("name") or ""
        for r in MED_RULES:
            hit = any(norm_key(k) in norm_key(mname) for k in r["med"])
            if hit and any(n["name"] == r["nut"] for n in nutrients):
                # med 를 함께 담아 보냅니다 — 화면이 '이 경고가 어느 약에서
                # 나왔는지'를 이 값으로 이어 붙입니다(문구 비교가 아니라).
                out.append({"kind": r["kind"], "tone": r["tone"], "med": mname,
                            "text": f"{mname} · {r['text']}"})

    for n in nutrients:
        if n["unmapped"]:
            out.append({"kind": "환산 불가", "tone": "gray",
                        "text": (f"{n['name']}의 {', '.join(n['unmapped'])} — "
                                 f"단위를 환산할 수 없어 합산에서 제외했습니다.")})

    unknown = [n["name"] for n in nutrients if not n["std"]]
    if unknown:
        out.append({"kind": "기준 미등록", "tone": "gray",
                    "text": (f"{eun(', '.join(unknown))} 기준값이 등록되어 있지 않아 "
                             f"비율을 계산하지 못했습니다.")})

    return out


# =============================================================================
# 추천 — 무엇을 더 챙기면 좋을지
# -----------------------------------------------------------------------------
# ★ 여기 규칙은 '숫자로 설명되는 것'만 다룹니다.
#     · 지금 섭취량(식사 + 영양제)이 권장량에 못 미치는 성분을 고릅니다.
#     · 이미 충분하거나 상한에 가까운 성분은 뺍니다.
#     · 복용 중인 약과 부딪히는 성분은 빼지 않고 '주의' 표시만 붙입니다.
#       (임의로 빼 버리면 사용자가 이유를 알 수 없습니다.)
#
# ★ 일부러 하지 않은 것 —
#   '혈압이 경계니까 이 성분을 드세요' 같은 검진 결과와 성분의 연결은 임상
#   근거가 필요한 판단이라 지어내지 않았습니다. 검진 입력은 '함께 고려했다'는
#   표시와, 이상 소견이 있을 때 전문가 상담 권고 문구로만 반영합니다.
#   이 판단을 넣으려면 반드시 전문가 검토를 거치세요. (규격서 7장)
# =============================================================================
def compute_recommend(state: dict, nutrients: list, exam: dict) -> dict:
    products = state.get("products") or []
    meds = state.get("meds") or []
    has_products = len(products) > 0

    # 약 이름 안에 상호작용 규칙이 걸리는 성분을 미리 모아 둡니다
    caution_of = {}
    for m in meds:
        mname = m.get("name") or ""
        for r in MED_RULES:
            if any(norm_key(k) in norm_key(mname) for k in r["med"]):
                caution_of.setdefault(r["nut"], []).append(f"{mname} · {r['kind']}")

    shortfall = [n for n in nutrients
                 if n["std"] and n["rda"] is not None and n["level"] in ("low", "none")]

    scored = []
    for n in shortfall:
        gap = max(0.0, n["rda"] - n["total"])
        ratio = (n["total"] / n["rda"]) if n["rda"] else 0.0
        caution = caution_of.get(n["name"])
        scored.append((ratio, {
            "name": n["name"],
            "amount": f"{fmt(gap)}{n['unit']} 더",
            "reason": (
                f"지금 {fmt(n['total'])}{n['unit']}로 권장량의 {round(ratio * 100)}%입니다. "
                f"영양제를 함께 넣어도 모자랍니다."
                if n["supp"] > 0 else
                f"식사 추정치로 {fmt(n['total'])}{n['unit']}, 권장량 {fmt(n['rda'])}{n['unit']}의 "
                f"{round(ratio * 100)}%입니다."
            ),
            # 많이 모자라면 주황, 조금 모자라면 파랑. 빨강은 쓰지 않습니다 —
            # '부족'은 위험이 아니라 채울 여지이기 때문입니다.
            "tone": "orange" if ratio < 0.5 else "blue",
            "caution": (f"복용 중인 {caution[0]} — 시작 전 의사·약사와 상의하세요."
                        if caution else ""),
        }))

    scored.sort(key=lambda t: t[0])          # 가장 많이 모자란 것부터
    items = [d for _, d in scored[:6]]

    # 무엇을 근거로 골랐는지 사용자에게 그대로 밝힙니다
    basis = ["식사 평균 추정치" if state.get("countMeal") else "입력하신 영양제"]
    if has_products and state.get("countMeal"):
        basis.append("복용 중인 영양제")
    if meds:
        basis.append(f"복용 중인 약 {len(meds)}건")
    if exam["filled"]:
        basis.append(f"검진 {exam['filled']}개 항목")

    enough = len([n for n in nutrients if n["level"] == "met"])
    basis_ko = eul(" · ".join(basis))

    if not items:
        desc = f"{basis_ko} 기준으로 보면 권장량에 못 미치는 성분이 없습니다."
        if enough:
            desc += f" {enough}개 성분이 권장 범위 안에 있습니다."
    else:
        desc = f"{basis_ko} 기준으로, 권장량에 못 미치는 성분을 모자란 순서로 골랐습니다."
        if has_products:
            desc += " 이미 드시는 영양제로 채워지는 성분은 뺐습니다."

    # 검진에 이상 소견이 있으면 추천보다 상담이 먼저입니다
    advice = (f"건강검진에서 {len(exam['abnormal'])}개 항목이 기준을 벗어났습니다. "
              f"영양제를 고르기 전에 의사·약사와 상의하시기를 권합니다."
              if exam["abnormal"] else "")

    # 상위 6개만 보여주므로, 나머지가 있으면 그 사실을 밝힙니다.
    # 밝히지 않으면 '부족한 건 이 6개뿐' 으로 읽힙니다.
    more = max(0, len(shortfall) - len(items))

    return {
        "title": "이런 성분을 더 챙겨 보세요" if items else "지금은 더 챙길 성분이 없습니다",
        "desc": desc,
        "items": items,
        "advice": advice,
        "more": more,
        "moreText": (f"이 밖에 {more}개 성분도 권장량에 못 미칩니다. "
                     f"아래 섭취량 카드에서 모두 확인하실 수 있습니다." if more else ""),
        "note": ("권장섭취량에 견준 계산 결과일 뿐, 특정 제품이나 복용을 권하는 것이 "
                 "아닙니다. 복용을 시작하기 전에 의사·약사와 상의하세요."),
    }


# =============================================================================
# 조립 — Report 한 덩어리로
# =============================================================================
def _note_of(n: dict) -> dict:
    """성분 카드 아래 코멘트.

    ※ 실제 서비스에서는 이 자리에 AI 가 쓴 문장이 들어갑니다. 지금은
      규칙으로 만든 문장이라 짧고 딱딱합니다.
    """
    lv = n["level"]
    if lv == "over":
        return {"title": "상한 초과.",
                "body": (f"{'영양제로만 ' if n['ulSuppOnly'] else ''}"
                         f"{fmt(n['ulAmount'])}{n['unit']}, 상한 {fmt(n['ul'])}{n['unit']}을 "
                         f"넘었습니다. 제품 수를 줄이거나 함량이 낮은 제품으로 바꿔 보세요.")}
    if lv == "near":
        return {"title": "상한 근접.", "body": "여기에 같은 성분이 든 제품을 더하면 초과할 수 있습니다."}
    if lv == "met":
        return {"title": "충분합니다.", "body": "현재 구성을 유지해도 괜찮습니다."}
    if lv == "low":
        if n["sources"]:
            return {"title": "권장량에 못 미칩니다.",
                    "body": "식사에서 보충하거나 제품의 함량을 확인해 보세요."}
        gap = max(0.0, (n["rda"] or 0) - n["total"])
        return {"title": "식사만으로는 모자랍니다.",
                "body": (f"권장량 {fmt(n['rda'])}{n['unit']}까지 {fmt(gap)}{n['unit']}이 "
                         f"부족합니다. 위의 추천을 참고해 보세요.")}
    if lv == "none":
        return {"title": "섭취량이 없습니다.", "body": "등록한 제품에 이 성분이 들어 있지 않습니다."}
    # unknown
    if n["unmapped"]:
        return {"title": "기준값이 없습니다.",
                "body": f"{', '.join(n['unmapped'])} — 이 단위는 환산 규칙이 없어 합산하지 않았습니다."}
    return {"title": "기준값이 없습니다.", "body": "기준표에 없는 성분이라 합산량만 표시합니다."}


def _caption_of(n: dict) -> str:
    """카드 위 작은 설명 — 어느 제품에서 얼마씩 왔는지."""
    if not n["sources"]:
        return f"식사 평균 추정 {fmt(n['meal'])}{n['unit']} · 등록한 제품 없음"
    s = " · ".join(n["sources"])
    if n["supp"] > 0:
        s += f" · 영양제 {fmt(n['supp'])}{n['unit']}"
    if n["meal"]:
        s += f" + 식사 {fmt(n['meal'])}{n['unit']}"
    return s


def _names(items: list) -> str:
    a = [x["name"] for x in items]
    if len(a) > 3:
        return f"{', '.join(a[:3])} 외 {len(a) - 3}개"
    return ", ".join(a)


def to_report(state: dict, *, engine: str = "python (예시 기준값)") -> dict:
    """Input → Report. 규격서 §5 의 모양 그대로 돌려줍니다."""
    exam = compute_exam(state)
    nutrients_raw = compute_nutrients(state)
    issues = compute_issues(state, nutrients_raw)
    recommend = compute_recommend(state, nutrients_raw, exam)

    worst = "met"
    for n in nutrients_raw:
        if LEVEL_RANK[n["level"]] > LEVEL_RANK[worst]:
            worst = n["level"]

    products = state.get("products") or []
    meds = state.get("meds") or []
    has_supp = len(nutrients_raw) > 0
    meal_only = len(products) == 0

    # 화면에 넘길 성분 카드 — std(기준표 원본)는 빼고 hasStd 로만 알려 줍니다.
    nutrients = [{
        "key": n["key"], "name": n["name"], "unit": n["unit"], "level": n["level"],
        "supp": n["supp"], "meal": n["meal"], "total": n["total"],
        "rda": n["rda"], "ul": n["ul"],
        "hasStd": bool(n["std"]),
        "ulSuppOnly": n["ulSuppOnly"],
        "ulAmount": n["ulAmount"],
        "sources": n["sources"],
        "unmapped": n["unmapped"],
        "basis": n["basis"],
        "bar": n["bar"],
        "gauge": n["pct"],                 # {rda, ul} — 각 탭의 게이지 비율
        "caption": _caption_of(n),
        "note": _note_of(n),
    } for n in nutrients_raw]

    # --- 종합 소견 문장 ------------------------------------------------------
    def pick(levels):
        return [n for n in nutrients if n["level"] in levels]

    over, near = pick(["over"]), pick(["near"])
    low, met = pick(["low", "none"]), pick(["met"])

    exam_line = (f"건강검진 종합 판정은 '{exam['overall']['label']}' 입니다. "
                 if exam["filled"] else "")

    if not has_supp:
        text = exam_line + "계산할 성분이 없습니다. 영양제를 넣거나 식사 평균 추정치 계산을 켜 주세요."
    else:
        parts = [
            f"식사 평균 추정치를 기준으로 {len(nutrients)}개 성분을 살펴봤습니다."
            if meal_only else
            (f"등록한 {len(products)}개 제품"
             f"{'과 식사 평균 추정치' if state.get('countMeal') else ''}에서 "
             f"{len(nutrients)}개 성분을 확인했습니다.")
        ]
        if over:
            parts.append(f"{eun(_names(over))} 상한을 넘어 조정이 필요합니다.")
        if near:
            parts.append(f"{eun(_names(near))} 상한에 가까워 추가 섭취에 주의가 필요합니다.")
        if low:
            parts.append(f"{eun(_names(low))} 권장량에 미치지 못합니다.")
        if met:
            parts.append(f"나머지 {len(met)}개 성분은 권장 범위 안에 있습니다.")
        if issues:
            parts.append(f"점검에서 {len(issues)}건이 확인됐습니다.")
        text = exam_line + " ".join(parts)

    chips = []
    if over:
        chips.append({"text": f"상한 초과 {len(over)}", "tone": "red"})
    if near:
        chips.append({"text": f"상한 근접 {len(near)}", "tone": "orange"})
    if met:
        chips.append({"text": f"적정 {len(met)}", "tone": "green"})
    if low:
        chips.append({"text": f"부족 {len(low)}", "tone": "blue"})
    if not chips:
        chips.append({"text": "데이터 없음", "tone": "gray"})

    # --- 프로필 헤더의 요약 배지 --------------------------------------------
    badges = []
    if exam["filled"]:
        badges.append({"text": exam["overall"]["label"], "tone": exam["overall"]["tone"]})
    if meds:
        badges.append({"text": f"복약 {len(meds)}건", "tone": "orange"})
    if products:
        badges.append({"text": f"영양제 {len(products)}종", "tone": "green"})
    elif has_supp:
        badges.append({"text": "식사 기준", "tone": "gray"})
    if worst == "over":
        badges.append({"text": "성분 상한 초과", "tone": "red"})
    if recommend["items"]:
        badges.append({"text": f"보충 권장 {len(recommend['items'])}", "tone": "blue"})
    if not badges:
        badges.append({"text": "입력 대기", "tone": "gray"})

    return {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "server",
            "engine": engine,
        },
        # ★ 받은 Input 을 그대로 되돌려 줍니다. 화면이 '입력 수정' 으로 돌아갈
        #   때 이 값을 씁니다. 빈 배열까지 그대로 넣어야 화면이 안 깨집니다.
        "input": state,
        "hasSupp": has_supp,
        "mealOnly": meal_only,
        "cols": min(max(len(nutrients), 1), MAX_COLS),
        "worst": worst,
        "badges": badges,
        "exam": exam,
        "nutrients": nutrients,
        "issues": issues,
        "recommend": recommend,
        "summary": {"text": text, "chips": chips},
    }


def summary_line(report: dict) -> str:
    """목록 화면에 한 줄로 보여 줄 요약. /api/reports 가 씁니다."""
    badges = report.get("badges") or []
    head = badges[0]["text"] if badges else "리포트"
    return f"{head} · 성분 {len(report.get('nutrients') or [])}개"


def report_info(report: dict) -> dict:
    """목록 카드에 '무엇을 넣고 뽑은 리포트인지' 보여 주기 위한 요약.

    날짜와 배지만 있으면 목록에서 리포트를 구분할 수 없습니다 — 같은 날
    여러 번 돌리면 전부 똑같아 보여서, 열어 보기 전에는 어느 것이 어느
    것인지 알 수 없습니다. 그래서 '무엇을 입력했는지'를 함께 내려보냅니다.

    성분 카드 전체를 담지는 않습니다. 목록은 가벼워야 하므로 이름과 개수만
    담고, 자세한 내용은 리포트를 열 때(getReport) 받습니다.
    """
    s = report.get("input") or {}
    products = s.get("products") or []
    meds = s.get("meds") or []
    exam = s.get("exam") or {}
    nutrients = report.get("nutrients") or []

    return {
        "name": s.get("name") or "",
        "age": s.get("age") or "",
        "sex": s.get("sex") or "",
        "date": s.get("date") or "",
        "countMeal": bool(s.get("countMeal")),
        "chronic": s.get("chronic") or [],
        # 이름은 앞 3개까지만. 나머지는 개수로 알려 줍니다.
        "products": [p.get("name") or "이름 없는 제품" for p in products][:3],
        "productCount": len(products),
        "meds": [m.get("name") or "" for m in meds if m.get("name")][:3],
        "medCount": len(meds),
        "examCount": len([v for v in exam.values() if v not in ("", None)]),
        "examOverall": ((report.get("exam") or {}).get("overall") or {}).get("label", ""),
        "nutrientCount": len(nutrients),
    }
