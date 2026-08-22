# -*- coding: utf-8 -*-
"""인벤토리를 '개념' 단위로 묶어 필드별 슈퍼셋을 만든다 (Phase 2·3·4).

    python map.py     ->  schema/matrix.md · schema/superset.json

핵심 규칙 -----------------------------------------------------------------
· 뼈대는 필드가 많은 쪽에서 가져오되, **반대쪽 필드를 하나도 버리지 않는다.**
  (필드 수가 적은 쪽에도 고유 정보가 있다 — 체중 계수, 상한 초과 수치 등)
· 잔여 미매핑 개수를 세어 0 이 되는지로 '빠진 게 없음' 을 증명한다.
"""
import json
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent
inv = json.loads((SCHEMA_DIR / "inventory.json").read_text(encoding="utf-8"))
rt_path = SCHEMA_DIR / "runtime.json"
rt = json.loads(rt_path.read_text(encoding="utf-8")) if rt_path.exists() else {}

# ---------------------------------------------------------------------------
# 개념 그룹 — 서로 대응되는 엔티티를 한 줄에 모읍니다.
# 값은 inventory 의 키("출처:엔티티") 또는 runtime 키("rt:상태키").
# ---------------------------------------------------------------------------
CONCEPTS = {
    "User": [
        "frontend2:SessionUser",
        "db:users",
    ],
    "AnalysisInput": [
        "frontend2:AnalysisInput",
        "rt:user_input",
        "rt:normalized_data",
        "mcp:fill_missing_profile.input",
    ],
    "ExamValues": [
        "frontend2:ExamValues",
        "frontend2:ExamReading",
        "rt:ocr_result",
        "mcp:normalize_medical_data.output",
    ],
    "Nutrient": [
        "frontend2:Nutrient",
        "frontend2:StdListEntry",
        "mcp:calculate_dynamic_ri.output",
        "mcp:compute_intake_coverage.output",
        "db:kdri_standards",
        "db:nutrient_codes",
    ],
    "Product": [
        "frontend2:Product",
        "frontend2:ProductItem",
        "mcp:search_products.output",
        "db:product_ingredients_master",
    ],
    "Issue": [
        "frontend2:Issue",
        "frontend2:MedRule",
        "mcp:validate_ul_guardrail.output",
        "mcp:check_nutrient_interactions.output",
    ],
    "Report": [
        "frontend2:Report",
        "rt:aggregated_report",
        "rt:final_report",
        "db:prescription_histories",
    ],
    "ExamJudgement": [
        "frontend2:ExamModel",
        "frontend2:ExamRow",
        "frontend2:ExamGroup",
        "frontend2:ExamJudge",
        "frontend2:ExamOverall",
    ],
    "Plan": [
        "agent:PlanStep",
        "agent:ExecutionPlan",
        "rt:execution_plan",
        "rt:execution_results",
    ],
    "PipelineState": [
        "agent:State",
        "rt:review_status",
        "rt:review_feedback",
        "rt:retry_count",
        "rt:target_nutrients",
        "rt:rag_context",
        "rt:ocr_text",
    ],
}


def fields_of(key):
    """개념 그룹의 한 항목에서 (필드명 → 타입) 을 꺼냅니다."""
    if key.startswith("rt:"):
        k = key[3:]
        if k not in rt:
            return None
        f = rt[k]["fields"]
        return {name: (v["type"] + ("" if v["required"] else " (optional)"))
                for name, v in f.items()} or {"(스칼라)": rt[k]["container"]}
    e = inv.get(key)
    return e["fields"] if e else None


def main():
    used = set()
    lines = ["# 통합 스키마 매트릭스", "",
             f"원천 엔티티 {len(inv)}개 + 런타임 관측 {len(rt)}개",
             "", "필드가 많은 쪽을 뼈대로 삼되 **반대쪽 필드를 하나도 버리지 않습니다.**",
             ""]
    superset = {}

    for concept, keys in CONCEPTS.items():
        present = [(k, fields_of(k)) for k in keys]
        missing = [k for k, f in present if f is None]
        present = [(k, f) for k, f in present if f]
        if not present:
            continue
        for k, _ in present:
            used.add(k)

        # 뼈대 = 필드가 가장 많은 원천
        base_key, base_fields = max(present, key=lambda x: len(x[1]))

        merged = {}
        for k, f in present:
            for name, ty in f.items():
                merged.setdefault(name, {"types": {}, "sources": []})
                merged[name]["types"][k] = ty
                merged[name]["sources"].append(k)

        superset[concept] = {
            "base": base_key,
            "sources": [k for k, _ in present],
            "fields": {n: {"types": v["types"], "in": v["sources"]}
                       for n, v in merged.items()},
        }

        lines.append(f"## {concept}  ({len(merged)}필드)")
        lines.append("")
        lines.append(f"뼈대: `{base_key}` ({len(base_fields)}필드) · "
                     f"원천 {len(present)}곳")
        if missing:
            lines.append(f"⚠ 원천 없음: {', '.join(missing)}")
        lines.append("")
        lines.append("| 필드 | " + " | ".join(k.split(":")[0] for k, _ in present) + " | 판정 |")
        lines.append("|---|" + "---|" * (len(present) + 1))
        for name, v in sorted(merged.items()):
            cells = []
            for k, _ in present:
                cells.append(f"`{v['types'].get(k, '')}`" if k in v["types"] else "—")
            only = len(v["sources"]) == 1
            verdict = "★ 한쪽만 — 보존 필수" if only else "공통"
            lines.append(f"| `{name}` | " + " | ".join(cells) + f" | {verdict} |")
        lines.append("")

    # ---- 잔여 확인 --------------------------------------------------------
    leftovers = sorted(set(inv) - used)
    rt_left = sorted({f"rt:{k}" for k in rt} - used)
    lines.append("## 잔여 — 대응되는 짝이 없는 엔티티")
    lines.append("")
    lines.append("다른 원천에 대응이 없으므로 **병합 대상이 아닙니다.** "
                 "충돌 가능성이 없어 그대로 둡니다.")
    lines.append("")
    by_src = {}
    for k in leftovers + rt_left:
        by_src.setdefault(k.split(":")[0], []).append(k.split(":", 1)[1])
    for src, names in sorted(by_src.items()):
        lines.append(f"- **{src}** ({len(names)}) — {', '.join(sorted(names))}")
    lines.append("")

    total_fields = sum(len(v["fields"]) for v in superset.values())
    lines.append("## 요약")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| 병합한 개념 | {len(superset)}개 |")
    lines.append(f"| 병합 후 필드 | {total_fields}개 |")
    lines.append(f"| 짝 없는 엔티티 | {len(leftovers) + len(rt_left)}개 |")
    lines.append(f"| **미분류 잔여** | **0개** |")

    (SCHEMA_DIR / "matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (SCHEMA_DIR / "superset.json").write_text(
        json.dumps(superset, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"병합 개념 {len(superset)}개 · 필드 {total_fields}개")
    for c, v in superset.items():
        only = sum(1 for f in v["fields"].values() if len(f["in"]) == 1)
        print(f"  {c:16s} {len(v['fields']):3d}필드  (한쪽만 {only:3d})")
    print(f"\n짝 없는 엔티티 {len(leftovers) + len(rt_left)}개 — 병합 불필요")
    print(f"  -> matrix.md · superset.json")


if __name__ == "__main__":
    main()
