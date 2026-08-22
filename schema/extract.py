# -*- coding: utf-8 -*-
"""8개 원천에서 데이터 모델을 전부 긁어 하나의 인벤토리로 모은다.

    uv run --directory ../agent python ../schema/extract.py
    (agent 가상환경이 필요합니다 — DB·Pydantic 을 씁니다)

왜 자동 추출인가 -----------------------------------------------------------
손으로 훑으면 "눈에 띄는 것부터" 집게 되고, 실제로 그렇게 해서 30% 만
덮은 적이 있습니다. 기계로 전부 뽑아 놓고 하나씩 지워야 '빠진 게 없다' 를
잔여 개수 0 으로 증명할 수 있습니다.

출력: schema/inventory.json  (엔티티 → 필드 → 타입 · 원천)
"""
import ast
import json
import re
import sys
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parent
ROOT = SCHEMA_DIR.parent
AGENT = ROOT / "agent"
MCP = ROOT / "mcp"
FRONT = ROOT / "frontend2"

sys.path.insert(0, str(AGENT))

inventory = {}   # "출처:엔티티" -> {"source":…, "kind":…, "fields":{name: type}}


def put(source, entity, fields, kind="model", note=""):
    key = f"{source}:{entity}"
    inventory[key] = {
        "source": source, "entity": entity, "kind": kind,
        "note": note, "fields": fields,
    }


# ===========================================================================
# 1. frontend2/inputData.js — JSDoc @typedef
# ===========================================================================
def extract_jsdoc():
    text = (FRONT / "inputData.js").read_text(encoding="utf-8")
    # /** … */ 블록 단위로 끊어서 @typedef 가 있는 것만 봅니다.
    for block in re.findall(r"/\*\*(.*?)\*/", text, re.S):
        m = re.search(r"@typedef\s+(?:\{([^}]*)\}\s+)?(\w+)", block)
        if not m:
            continue
        union, name = m.group(1), m.group(2)
        # 유니온 타입 별칭 (@typedef {'a'|'b'} Level)
        if union and "Object" not in union:
            put("frontend2", name, {"(값)": union.strip()}, kind="enum")
            continue
        fields = {}
        for pm in re.finditer(r"@property\s+\{([^}]*)\}\s+(\[?[\w.]+\]?)", block):
            ftype, fname = pm.group(1).strip(), pm.group(2)
            optional = fname.startswith("[")
            fname = fname.strip("[]")
            fields[fname] = ftype + (" (optional)" if optional else "")
        if fields:
            put("frontend2", name, fields)


# ===========================================================================
# 2. agent/schemas/*.py — TypedDict + Pydantic
# ===========================================================================
def extract_agent_schemas():
    for py in sorted((AGENT / "schemas").glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(b) for b in node.bases]
            fields = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields[stmt.target.id] = ast.unparse(stmt.annotation)
            if fields:
                put("agent", node.name, fields,
                    kind="TypedDict" if any("TypedDict" in b for b in bases) else "Pydantic",
                    note=f"{py.name} · bases={bases}")
        # ToolName 같은 모듈 수준 Literal 별칭
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                t = node.targets[0]
                src = ast.unparse(node.value)
                if isinstance(t, ast.Name) and src.startswith("Literal["):
                    put("agent", t.id, {"(값)": src}, kind="enum", note=py.name)


# ===========================================================================
# 3. agent/nodes/*.py — state["x"] = {…} 로 조립되는 딕셔너리
#    정적으로 읽히는 리터럴만 뽑습니다. 동적으로 채워지는 부분은
#    runtime_sample.py 가 실행 결과로 보완합니다.
# ===========================================================================
def extract_node_dicts():
    for py in sorted((AGENT / "nodes").glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                if not (isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Name) and tgt.value.id == "state"):
                    continue
                try:
                    key = ast.literal_eval(tgt.slice)
                except Exception:
                    continue
                if isinstance(node.value, ast.Dict):
                    fields = {}
                    for k, v in zip(node.value.keys, node.value.values):
                        try:
                            fk = ast.literal_eval(k)
                        except Exception:
                            continue
                        fields[fk] = f"(리터럴) {ast.unparse(v)[:60]}"
                    if fields:
                        put("agent-node", key, fields, kind="dict",
                            note=f"{py.name} · 정적 추출")


# ===========================================================================
# 4. mcp/mcp_tools_specs.json — JSON Schema
# ===========================================================================
def _json_schema_fields(sch, prefix=""):
    out = {}
    for k, v in (sch.get("properties") or {}).items():
        ty = v.get("type")
        if isinstance(ty, list):
            ty = "|".join(ty)
        extra = ""
        if v.get("enum"):
            extra = f" enum={v['enum']}"
        if v.get("const"):
            extra = f" const={v['const']}"
        out[prefix + k] = f"{ty}{extra}"
        if v.get("type") == "object" and v.get("properties"):
            out.update(_json_schema_fields(v, prefix + k + "."))
        if v.get("type") == "array" and isinstance(v.get("items"), dict):
            it = v["items"]
            if it.get("properties"):
                out.update(_json_schema_fields(it, prefix + k + "[]."))
            elif it.get("type"):
                out[prefix + k] += f" of {it['type']}"
        if v.get("additionalProperties", {}) and isinstance(v["additionalProperties"], dict):
            ap = v["additionalProperties"].get("type")
            if ap:
                out[prefix + k] += f" (map→{ap})"
    return out


def extract_mcp():
    spec = json.loads((MCP / "mcp_tools_specs.json").read_text(encoding="utf-8"))
    for tool in spec.get("tools", []):
        nm = tool["name"]
        for side in ("input", "output"):
            sch = tool.get(side) or {}
            fields = _json_schema_fields(sch)
            if fields:
                req = sch.get("required", [])
                for f in list(fields):
                    if f in req:
                        fields[f] += " *필수"
                put("mcp", f"{nm}.{side}", fields, kind="JSONSchema")


# ===========================================================================
# 5. mcp/main.py — 실제 파이썬 시그니처 (스펙과 어긋나는지 확인용)
# ===========================================================================
def extract_mcp_signatures():
    tree = ast.parse((MCP / "main.py").read_text(encoding="utf-8"))
    spec = json.loads((MCP / "mcp_tools_specs.json").read_text(encoding="utf-8"))
    names = {t["name"] for t in spec.get("tools", [])}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            fields = {}
            for a in node.args.args:
                fields[a.arg] = ast.unparse(a.annotation) if a.annotation else "?"
            put("mcp-impl", f"{node.name}.signature", fields, kind="signature",
                note="main.py 실제 구현")


# ===========================================================================
# 6. frontend2/standards.py — 상수 테이블 구조
# ===========================================================================
def extract_standards():
    sys.path.insert(0, str(FRONT))
    try:
        import standards
    except Exception as e:
        put("frontend2", "standards(로드실패)", {"error": str(e)[:80]}, kind="error")
        return
    if getattr(standards, "STD_LIST", None):
        keys = {}
        for entry in standards.STD_LIST:
            for k, v in entry.items():
                keys.setdefault(k, type(v).__name__)
        put("frontend2", "StdListEntry", keys, kind="const",
            note=f"standards.STD_LIST · {len(standards.STD_LIST)}종")
    if getattr(standards, "MED_RULES", None):
        keys = {}
        for entry in standards.MED_RULES:
            for k, v in entry.items():
                keys.setdefault(k, type(v).__name__)
        put("frontend2", "MedRule", keys, kind="const",
            note=f"standards.MED_RULES · {len(standards.MED_RULES)}건")
    for nm in ("LEVEL_RANK", "CHRONIC", "UNITS"):
        val = getattr(standards, nm, None)
        if val is not None:
            put("frontend2", nm, {"(값)": str(val)[:120]}, kind="enum", note="standards.py")


# ===========================================================================
# 7. DB — information_schema (실제 컬럼)
# ===========================================================================
def extract_db():
    try:
        from config import DATABASE_URL
        import psycopg
        from psycopg.rows import dict_row
    except Exception as e:
        put("db", "(접속 불가)", {"error": str(e)[:80]}, kind="error")
        return
    if not DATABASE_URL:
        put("db", "(DATABASE_URL 없음)", {"error": ".env 확인"}, kind="error")
        return
    try:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name, column_name, data_type,
                           character_maximum_length AS len, is_nullable
                      FROM information_schema.columns
                     WHERE table_schema = 'public'
                     ORDER BY table_name, ordinal_position
                """)
                tables = {}
                for r in cur.fetchall():
                    ln = f"({r['len']})" if r["len"] else ""
                    null = "" if r["is_nullable"] == "NO" else " nullable"
                    tables.setdefault(r["table_name"], {})[r["column_name"]] = \
                        f"{r['data_type']}{ln}{null}"
                for t, cols in tables.items():
                    put("db", t, cols, kind="table")
    except Exception as e:
        put("db", "(쿼리 실패)", {"error": f"{type(e).__name__}: {str(e)[:70]}"}, kind="error")


# ===========================================================================
def main():
    steps = [
        ("frontend2 JSDoc", extract_jsdoc),
        ("agent schemas", extract_agent_schemas),
        ("agent nodes", extract_node_dicts),
        ("mcp specs", extract_mcp),
        ("mcp signatures", extract_mcp_signatures),
        ("frontend2 standards", extract_standards),
        ("DB columns", extract_db),
    ]
    for label, fn in steps:
        before = len(inventory)
        try:
            fn()
        except Exception as e:
            print(f"  [FAIL] {label}: {type(e).__name__}: {e}")
            continue
        print(f"  [ OK ] {label:22s} +{len(inventory) - before}개")

    total_fields = sum(len(v["fields"]) for v in inventory.values())
    print(f"\n엔티티 {len(inventory)}개 · 필드 {total_fields}개")

    out = SCHEMA_DIR / "inventory.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"  -> {out}")

    by_src = {}
    for v in inventory.values():
        by_src[v["source"]] = by_src.get(v["source"], 0) + len(v["fields"])
    print("\n원천별 필드 수:")
    for k, n in sorted(by_src.items(), key=lambda x: -x[1]):
        print(f"  {k:14s} {n:4d}")


if __name__ == "__main__":
    main()
