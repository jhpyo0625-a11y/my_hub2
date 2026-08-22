# -*- coding: utf-8 -*-
"""파이프라인을 실제로 돌려 state 각 키의 실제 형태를 역추론한다.

    uv run --directory ../agent python ../schema/runtime_sample.py

왜 필요한가 ---------------------------------------------------------------
nodes/*.py 는 딕셔너리를 코드로 조립하므로 타입 선언이 없습니다. 정적
추출로는 14개 state 키 중 4개밖에 못 잡았습니다. 나머지는 돌려 봐야
압니다.

★ 입력을 여러 개 넣습니다. 한 번만 돌리면 어떤 필드가 '항상 있는지'와
  '가끔만 있는지'를 구분할 수 없어, Optional 을 필수로 잘못 판단합니다.

출력: schema/runtime.json
"""
import asyncio
import json
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent
AGENT = SCHEMA_DIR.parent / "agent"
sys.path.insert(0, str(AGENT))

from graph.workflow import graph  # noqa: E402


# 서로 다른 경로를 밟도록 만든 입력들. qa/cases 의 설계를 따릅니다.
SAMPLES = [
    ("최소입력", {"name": "이수진", "age": 45, "gender": "female",
                  "weight_kg": 54.0, "current_supplements": []}),
    ("성별·나이 누락", {"name": None, "age": None, "gender": None,
                       "weight_kg": None, "current_supplements": []}),
    ("고령·저체중", {"name": "최명숙", "age": 78, "gender": "female",
                    "weight_kg": 44.0, "current_supplements": []}),
    ("남성·고체중", {"name": "박정호", "age": 58, "gender": "male",
                    "weight_kg": 92.0, "current_supplements": []}),
]


def infer(value, depth=0):
    """값 하나에서 타입 문자열을 만듭니다. 중첩은 2단까지만."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        if not value:
            return "array(비어 있음)"
        return f"array<{infer(value[0], depth + 1)}>"
    if isinstance(value, dict):
        if depth >= 2:
            return "object"
        inner = ", ".join(f"{k}:{infer(v, depth + 1)}" for k, v in list(value.items())[:6])
        more = "…" if len(value) > 6 else ""
        return f"{{{inner}{more}}}"
    return type(value).__name__


async def main():
    # key -> field -> {"types": set, "seen": int}
    seen = {}
    runs = 0

    for label, user_input in SAMPLES:
        print(f"\n--- {label} ---")
        try:
            final = await graph.ainvoke({"user_input": user_input, "retry_count": 0})
        except Exception as e:
            print(f"  실패: {type(e).__name__}: {str(e)[:100]}")
            continue
        runs += 1
        for key, value in final.items():
            slot = seen.setdefault(key, {"__type": set(), "fields": {}, "seen": 0})
            slot["seen"] += 1
            slot["__type"].add(infer(value))
            if isinstance(value, dict):
                for fk, fv in value.items():
                    f = slot["fields"].setdefault(fk, {"types": set(), "seen": 0})
                    f["types"].add(infer(fv))
                    f["seen"] += 1
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                for item in value:
                    for fk, fv in item.items():
                        f = slot["fields"].setdefault(f"[].{fk}", {"types": set(), "seen": 0})
                        f["types"].add(infer(fv))
                        f["seen"] += 1
        print(f"  state 키 {len(final)}개 관측")

    if not runs:
        print("\n실행이 한 번도 성공하지 못했습니다. DB·MCP 상태를 확인하세요.")
        return

    out = {}
    for key, slot in sorted(seen.items()):
        fields = {}
        for fk, f in sorted(slot["fields"].items()):
            # 모든 실행에서 보였으면 필수, 아니면 선택으로 봅니다.
            always = f["seen"] >= slot["seen"]
            fields[fk] = {
                "type": " | ".join(sorted(f["types"])),
                "required": always,
                "seen": f"{f['seen']}/{slot['seen']}",
            }
        out[key] = {
            "container": " | ".join(sorted(slot["__type"]))[:200],
            "seen_in_runs": f"{slot['seen']}/{runs}",
            "fields": fields,
        }

    p = SCHEMA_DIR / "runtime.json"
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n=== 관측된 state 키 {len(out)}개 (실행 {runs}회) ===")
    for k, v in out.items():
        opt = sum(1 for x in v["fields"].values() if not x["required"])
        print(f"  {k:22s} 필드 {len(v['fields']):3d}개"
              + (f"  (선택 {opt}개)" if opt else "")
              + f"  [{v['seen_in_runs']}]")
    print(f"\n  -> {p}")


if __name__ == "__main__":
    asyncio.run(main())
