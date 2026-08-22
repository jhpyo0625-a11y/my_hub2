# 에이전트 하네스 가드레일 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** agent/ 파이프라인의 각 LangGraph 노드에 얇은 하네스 가드레일을 붙여, 노드 출력이 established rule에서 이탈하면 flag/차단한다.

**Architecture:** `guard()` 래퍼가 각 노드를 감싼다. 실행 전 `pre()`(전제조건 검증 + LLM 노드는 `.md` 룰을 프롬프트에 주입), 실행 후 `post()`(이탈이면 flag). 룰은 노드별 `.md`에 산문으로, 실제 체크는 그 `.md`를 반영한 얇은 손코딩 함수. 위반 시 기본 차단 → `server.py`가 안전 거부 응답.

**Tech Stack:** Python 3.11, LangGraph, pydantic(이미 설치), stdlib. 새 의존성 없음.

## Global Constraints

- 새 의존성 추가 금지. pydantic/stdlib만.
- post 체크는 결정적 손코딩 assert. 런타임 LLM 판정 금지.
- 노드 코드(`nodes/*.py`)는 순수 유지. 검증은 `guardrails/`에 격리. (예외: `planner.py`는 프롬프트에 spec 주입 1줄 허용.)
- 테스트는 `test_pipeline.py`와 동일하게 프레임워크 없는 assert 스크립트, `uv run python <file>`로 실행.
- 모든 명령은 `agent/`에서 실행. Windows 콘솔은 cp949 → `PYTHONIOENCODING=utf-8` 붙인다.
- 4개 tool_name Literal: `calculate_dynamic_ri`, `validate_ul_guardrail`, `check_nutrient_interactions`, `search_products`.
- `MAX_RETRIES = 3` (`nodes/reviewer.py`).
- disclaimer 정문구는 `nodes/compliance.py`의 `DISCLAIMER`.

---

### Task 1: 하네스 코어 (harness.py)

**Files:**
- Create: `agent/guardrails/__init__.py`
- Create: `agent/guardrails/harness.py`
- Test: `agent/test_guardrails.py`

**Interfaces:**
- Produces:
  - `GuardViolation(node: str, problems: list[str])` — Exception, 속성 `.node`, `.problems`
  - `load_spec(name: str, base: Path = GUARD_DIR) -> str` — `guardrails/<name>.md` 텍스트(없으면 "")
  - `flag(node: str, spec_md: str, problems: list[str]) -> None` — 서버 로그 출력
  - `guard(fn, name, spec_md, pre=None, post=None, on_violation="block")` — async 노드 래퍼. `pre`/`post`는 `state -> list[str]`(이탈 목록).

- [ ] **Step 1: `agent/guardrails/__init__.py` 생성 (빈 파일)**

```python
```

- [ ] **Step 2: 실패 테스트 작성 — `agent/test_guardrails.py`**

```python
"""가드레일 self-check. `uv run python test_guardrails.py`."""
import asyncio
from pathlib import Path

from guardrails.harness import guard, GuardViolation, load_spec


async def test_harness():
    async def node(state):
        state["ran"] = True
        return state

    # post 이탈 없음 → 통과
    g = guard(node, "t", "x.md", post=lambda s: [])
    out = await g({})
    assert out["ran"] is True

    # post 이탈 + block → GuardViolation
    g = guard(node, "t", "x.md", post=lambda s: ["bad"])
    try:
        await g({})
        assert False, "should raise"
    except GuardViolation as e:
        assert e.node == "t" and e.problems == ["bad"]

    # log 모드 → raise 안 함
    g = guard(node, "t", "x.md", post=lambda s: ["bad"], on_violation="log")
    out = await g({})
    assert out["ran"] is True

    # pre 이탈 → 노드 실행 전 차단
    g = guard(node, "t", "x.md", pre=lambda s: ["pre-bad"])
    try:
        await g({})
        assert False
    except GuardViolation as e:
        assert e.problems == ["pre-bad"]

    # load_spec
    tmp = Path(__file__).resolve().parent / "guardrails"
    txt = load_spec("__missing__")
    assert txt == ""
    print("  harness OK")


async def main():
    await test_harness()
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'guardrails.harness'`

- [ ] **Step 4: `agent/guardrails/harness.py` 구현**

```python
"""노드 래퍼 하네스. 각 노드 출력을 그 노드 spec과 대조해 이탈을 flag/차단."""
from pathlib import Path

GUARD_DIR = Path(__file__).resolve().parent


class GuardViolation(Exception):
    def __init__(self, node: str, problems: list[str]):
        self.node = node
        self.problems = problems
        super().__init__(f"{node}: {problems}")


def load_spec(name: str, base: Path = GUARD_DIR) -> str:
    """guardrails/<name>.md 텍스트. 없으면 빈 문자열."""
    p = Path(base) / f"{name}.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def flag(node: str, spec_md: str, problems: list[str]) -> None:
    print(f"[GUARDRAIL] {node} 이탈 (spec={spec_md}): {problems}")


def _check(name, spec_md, problems, on_violation):
    if problems:
        flag(name, spec_md, problems)
        if on_violation == "block":
            raise GuardViolation(name, problems)


def guard(fn, name, spec_md, pre=None, post=None, on_violation="block"):
    """fn(async node)을 감싼다. pre/post는 state->list[str](이탈 목록)."""
    async def wrapped(state):
        if pre:
            _check(name, spec_md, pre(state) or [], on_violation)
        state = await fn(state)
        if post:
            _check(name, spec_md, post(state) or [], on_violation)
        return state
    return wrapped
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `harness OK` / `ALL PASS`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/__init__.py agent/guardrails/harness.py agent/test_guardrails.py
git commit -m "feat(guardrails): 하네스 코어 guard/GuardViolation/load_spec"
```

---

### Task 2: Normalizer 가드레일

**Files:**
- Create: `agent/guardrails/normalizer.md`
- Create: `agent/guardrails/checks.py`
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_normalizer(state) -> list[str]`, `post_normalizer(state) -> list[str]` in `guardrails/checks.py`
- Consumes: `normalized_data`(dict: age,gender,gender_defaulted,is_pii), `target_nutrients`(list[str]), `user_input`

- [ ] **Step 1: `agent/guardrails/normalizer.md` 생성**

```markdown
# Normalizer 가드레일

정규화 노드 계약. established rule: 성인 19세 이상만, 성별 필수(기본값 금지).

## pre (전제조건)
- `user_input`이 state에 존재.

## post (이탈이면 flag)
- `normalized_data.age`는 int이고 **19 이상**. (미만/누락 → 스코프 이탈)
- `normalized_data.gender` ∈ {male, female}이고 `gender_defaulted`가 False. (성별은 기본값으로 채우면 안 됨)
- `normalized_data.is_pii` 태그 존재. (Compliance 마스킹이 참조)
- `target_nutrients`는 비어있지 않은 list[str].
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`의 `main()` 위에 함수 추가하고 `main()`에서 호출**

```python
from guardrails.checks import pre_normalizer, post_normalizer


def _norm_state(**over):
    nd = {"age": 30, "gender": "female", "gender_defaulted": False,
          "is_pii": {"name": True}, "name": "홍길동"}
    nd.update(over.get("nd", {}))
    s = {"user_input": {"x": 1}, "normalized_data": nd,
         "target_nutrients": ["vitamin_d"]}
    s.update(over.get("top", {}))
    return s


async def test_normalizer():
    assert pre_normalizer({"user_input": {}}) == []
    assert pre_normalizer({}) == ["user_input 없음"]
    assert post_normalizer(_norm_state()) == []
    assert post_normalizer(_norm_state(nd={"age": 17})), "age<19 flag"
    assert post_normalizer(_norm_state(nd={"gender": "x"})), "gender flag"
    assert post_normalizer(_norm_state(nd={"gender_defaulted": True})), "defaulted flag"
    assert post_normalizer(_norm_state(top={"target_nutrients": []})), "targets flag"
    print("  normalizer OK")
```

`main()`에 `await test_normalizer()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_normalizer'`

- [ ] **Step 4: `agent/guardrails/checks.py` 생성 (Normalizer 부분)**

```python
"""노드별 pre/post 체크. 각 함수는 이탈 문자열 list를 반환(빈 list = 통과)."""


def pre_normalizer(state) -> list[str]:
    return [] if state.get("user_input") else ["user_input 없음"]


def post_normalizer(state) -> list[str]:
    nd = state.get("normalized_data") or {}
    p = []
    age = nd.get("age")
    if not isinstance(age, int) or age < 19:
        p.append(f"age 부적합(≥19 필요): {age}")
    if nd.get("gender") not in ("male", "female"):
        p.append(f"gender 부적합: {nd.get('gender')}")
    if nd.get("gender_defaulted"):
        p.append("sex 기본값 사용됨(성별 필수)")
    if "is_pii" not in nd:
        p.append("is_pii 태그 없음")
    tn = state.get("target_nutrients")
    if not (isinstance(tn, list) and tn and all(isinstance(x, str) for x in tn)):
        p.append("target_nutrients 부적합")
    return p
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `normalizer OK`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/normalizer.md agent/guardrails/checks.py agent/test_guardrails.py
git commit -m "feat(guardrails): Normalizer 스코프/PII 태그 체크"
```

---

### Task 3: Planner 가드레일 (+ 프롬프트 주입)

**Files:**
- Create: `agent/guardrails/planner.md`
- Modify: `agent/guardrails/checks.py`
- Modify: `agent/nodes/planner.py` (spec 프롬프트 주입 1줄)
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_planner(state) -> list[str]`, `post_planner(state) -> list[str]`
- Consumes: `execution_plan`(list[dict]: step,tool_name,args), `load_spec` from Task 1

- [ ] **Step 1: `agent/guardrails/planner.md` 생성**

```markdown
# Planner 가드레일

계획 노드 계약. 존재하는 툴만, 의존 순서 준수.

가용 tool_name: calculate_dynamic_ri, validate_ul_guardrail, check_nutrient_interactions, search_products.

## pre
- `normalized_data`와 `target_nutrients`가 state에 존재.

## post
- `execution_plan`은 비어있지 않은 list.
- 모든 step.tool_name ∈ 위 4개.
- 툴별 필수 args 존재:
  - calculate_dynamic_ri: age, gender, weight_kg, target_nutrients
  - validate_ul_guardrail: current_supps_intake, diet_estimated_intake, proposed_supps_intake, age, gender, weight_kg
  - check_nutrient_interactions: nutrient_list
  - search_products: target_nutrients
- **validate_ul_guardrail의 step번호 > search_products의 step번호** (UL 검증은 제품 검색 결과에 의존).
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
from guardrails.checks import pre_planner, post_planner


def _plan_ok():
    return [
        {"step": 1, "tool_name": "calculate_dynamic_ri",
         "args": {"age": 30, "gender": "female", "weight_kg": 60, "target_nutrients": ["vitamin_d"]}},
        {"step": 2, "tool_name": "search_products", "args": {"target_nutrients": ["vitamin_d"]}},
        {"step": 3, "tool_name": "check_nutrient_interactions", "args": {"nutrient_list": ["vitamin_d"]}},
        {"step": 4, "tool_name": "validate_ul_guardrail",
         "args": {"current_supps_intake": {}, "diet_estimated_intake": {}, "proposed_supps_intake": {},
                  "age": 30, "gender": "female", "weight_kg": 60}},
    ]


async def test_planner():
    assert pre_planner({"normalized_data": {}, "target_nutrients": []}) == []
    assert pre_planner({}), "missing precondition"
    assert post_planner({"execution_plan": _plan_ok()}) == []
    bad_tool = _plan_ok(); bad_tool[0]["tool_name"] = "nope"
    assert post_planner({"execution_plan": bad_tool}), "unknown tool flag"
    bad_arg = _plan_ok(); bad_arg[0]["args"].pop("gender")
    assert post_planner({"execution_plan": bad_arg}), "missing arg flag"
    bad_order = _plan_ok()
    bad_order[1]["step"], bad_order[3]["step"] = 4, 2  # search after ul
    assert post_planner({"execution_plan": bad_order}), "order flag"
    print("  planner OK")
```

`main()`에 `await test_planner()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_planner'`

- [ ] **Step 4: `agent/guardrails/checks.py`에 Planner 체크 추가**

```python
_TOOLS = {
    "calculate_dynamic_ri", "validate_ul_guardrail",
    "check_nutrient_interactions", "search_products",
}
_REQ_ARGS = {
    "calculate_dynamic_ri": {"age", "gender", "weight_kg", "target_nutrients"},
    "validate_ul_guardrail": {"current_supps_intake", "diet_estimated_intake",
                              "proposed_supps_intake", "age", "gender", "weight_kg"},
    "check_nutrient_interactions": {"nutrient_list"},
    "search_products": {"target_nutrients"},
}


def pre_planner(state) -> list[str]:
    p = []
    if "normalized_data" not in state:
        p.append("normalized_data 없음")
    if "target_nutrients" not in state:
        p.append("target_nutrients 없음")
    return p


def post_planner(state) -> list[str]:
    plan = state.get("execution_plan")
    if not isinstance(plan, list) or not plan:
        return ["execution_plan 없음/빈값"]
    p = []
    ul_step = sp_step = None
    for s in plan:
        tn = s.get("tool_name")
        if tn not in _TOOLS:
            p.append(f"미지 tool_name: {tn}")
            continue
        missing = _REQ_ARGS[tn] - set((s.get("args") or {}).keys())
        if missing:
            p.append(f"{tn} 필수 args 누락: {sorted(missing)}")
        if tn == "validate_ul_guardrail":
            ul_step = s.get("step")
        if tn == "search_products":
            sp_step = s.get("step")
    if ul_step is not None and sp_step is not None and not (ul_step > sp_step):
        p.append("validate_ul_guardrail가 search_products 뒤가 아님")
    return p
```

- [ ] **Step 5: `agent/nodes/planner.py` — spec 프롬프트 주입**

`_llm_plan` 내부의 `sys = (...)` 정의 **직후**에 다음 2줄을 추가:

```python
        from guardrails.harness import load_spec
        sys = load_spec("planner") + "\n\n" + sys
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `planner OK`

- [ ] **Step 7: 커밋**

```bash
git add agent/guardrails/planner.md agent/guardrails/checks.py agent/nodes/planner.py agent/test_guardrails.py
git commit -m "feat(guardrails): Planner 계약/의존순서 체크 + spec 프롬프트 주입"
```

---

### Task 4: Executor 가드레일

**Files:**
- Create: `agent/guardrails/executor.md`
- Modify: `agent/guardrails/checks.py`
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_executor(state) -> list[str]`, `post_executor(state) -> list[str]`
- Consumes: `execution_results`(list[dict]: status, task_name, result)

- [ ] **Step 1: `agent/guardrails/executor.md` 생성**

```markdown
# Executor 가드레일

실행 노드 계약. LLM이 숫자를 만들지 않는다는 규칙의 출력 경계 강제.

## pre
- `execution_plan`이 state에 존재.

## post
- `execution_results`는 비어있지 않은 list.
- 각 항목 status ∈ {success, error}.
- calculate_dynamic_ri 성공 결과의 custom_ri 값에 null/0 누출 없음 (매칭 없는 코드는 생략돼야 하며 0으로 처방하지 않음).
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
from guardrails.checks import pre_executor, post_executor


def _exec_ok():
    return [
        {"task_name": "calculate_dynamic_ri", "status": "success",
         "result": {"custom_ri": {"vitamin_d": {"value": 10}}}},
        {"task_name": "search_products", "status": "success", "result": {"products": []}},
    ]


async def test_executor():
    assert pre_executor({"execution_plan": []}) == []
    assert pre_executor({}), "missing plan"
    assert post_executor({"execution_results": _exec_ok()}) == []
    assert post_executor({"execution_results": []}), "empty results"
    bad_status = _exec_ok(); bad_status[0]["status"] = "weird"
    assert post_executor({"execution_results": bad_status}), "status flag"
    leak = _exec_ok(); leak[0]["result"]["custom_ri"]["vitamin_d"]["value"] = 0
    assert post_executor({"execution_results": leak}), "0 leak flag"
    print("  executor OK")
```

`main()`에 `await test_executor()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_executor'`

- [ ] **Step 4: `agent/guardrails/checks.py`에 Executor 체크 추가**

```python
def pre_executor(state) -> list[str]:
    return [] if "execution_plan" in state else ["execution_plan 없음"]


def post_executor(state) -> list[str]:
    res = state.get("execution_results")
    if not isinstance(res, list) or not res:
        return ["execution_results 없음/빈값"]
    p = []
    for r in res:
        if r.get("status") not in ("success", "error"):
            p.append(f"status 부적합: {r.get('status')}")
    for r in res:
        if r.get("task_name") == "calculate_dynamic_ri" and r.get("status") == "success":
            cri = (r.get("result") or {}).get("custom_ri", {})
            for code, info in cri.items():
                v = (info or {}).get("value")
                if v is None or v == 0:
                    p.append(f"custom_ri 누출(0/None): {code}")
    return p
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `executor OK`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/executor.md agent/guardrails/checks.py agent/test_guardrails.py
git commit -m "feat(guardrails): Executor 결과 형태/숫자 누출 체크"
```

---

### Task 5: Reviewer 가드레일 (+ md 이동)

**Files:**
- Create: `agent/guardrails/reviewer.md` (기존 `agent/REVIEWER_GUARDRAILS.md` 내용 이동)
- Delete: `agent/REVIEWER_GUARDRAILS.md`
- Modify: `agent/guardrails/checks.py`
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_reviewer(state) -> list[str]`, `post_reviewer(state) -> list[str]`
- Consumes: `review_status`, `retry_count`, `failed_items`; `MAX_RETRIES` from `nodes.reviewer`

- [ ] **Step 1: md 이동**

```bash
git mv agent/REVIEWER_GUARDRAILS.md agent/guardrails/reviewer.md
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
from guardrails.checks import pre_reviewer, post_reviewer


async def test_reviewer_guard():
    assert pre_reviewer({"execution_results": []}) == []
    assert pre_reviewer({}), "missing results"
    assert post_reviewer({"review_status": "pass", "retry_count": 1}) == []
    assert post_reviewer({"review_status": "nonsense"}), "status flag"
    assert post_reviewer({"review_status": "pass", "retry_count": 99}), "retry flag"
    assert post_reviewer({"review_status": "pass",
                          "failed_items": [{"tool_name": "x"}]}), "failed_item shape flag"
    print("  reviewer_guard OK")
```

`main()`에 `await test_reviewer_guard()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_reviewer'`

- [ ] **Step 4: `agent/guardrails/checks.py`에 Reviewer 체크 추가**

파일 상단 import에 추가:

```python
from nodes.reviewer import MAX_RETRIES
```

함수 추가:

```python
def pre_reviewer(state) -> list[str]:
    return [] if "execution_results" in state else ["execution_results 없음"]


def post_reviewer(state) -> list[str]:
    p = []
    if state.get("review_status") not in ("pass", "reject_to_executor", "reject_to_planner"):
        p.append(f"review_status 부적합: {state.get('review_status')}")
    if state.get("retry_count", 0) > MAX_RETRIES:
        p.append(f"retry_count 초과: {state.get('retry_count')}")
    for f in state.get("failed_items", []) or []:
        if f.get("status") != "failed" or "reason" not in f:
            p.append(f"failed_item 형식 오류: {f}")
    return p
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `reviewer_guard OK`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/reviewer.md agent/guardrails/checks.py agent/test_guardrails.py
git commit -m "feat(guardrails): Reviewer 상태/재시도 체크 + reviewer.md 이동"
```

---

### Task 6: Aggregator 가드레일

**Files:**
- Create: `agent/guardrails/aggregator.md`
- Modify: `agent/guardrails/checks.py`
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_aggregator(state) -> list[str]`, `post_aggregator(state) -> list[str]`
- Consumes: `aggregated_report`(dict), `execution_results`

- [ ] **Step 1: `agent/guardrails/aggregator.md` 생성**

```markdown
# Aggregator 가드레일

취합 노드 계약. 숫자를 새로 만들거나 바꾸지 않는다(pass-through).

## pre
- `execution_results`가 state에 존재.

## post
- `aggregated_report`에 필수키: title, user_profile, calculated_target, ul_check, guidelines.
- **숫자 pass-through 동일**: calculated_target == executor의 calculate_dynamic_ri 결과, ul_check == executor의 validate_ul_guardrail 결과. (불일치 = 조작/환각 유입)
- guidelines는 list[str].
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
from guardrails.checks import pre_aggregator, post_aggregator


def _agg_state():
    results = [
        {"task_name": "calculate_dynamic_ri", "status": "success", "result": {"custom_ri": {"vitamin_d": {"value": 10}}}},
        {"task_name": "validate_ul_guardrail", "status": "success", "result": {"is_safe": True}},
    ]
    rep = {
        "title": "t", "user_profile": {}, "guidelines": ["a"],
        "calculated_target": {"custom_ri": {"vitamin_d": {"value": 10}}},
        "ul_check": {"is_safe": True},
    }
    return {"execution_results": results, "aggregated_report": rep}


async def test_aggregator():
    assert pre_aggregator({"execution_results": []}) == []
    assert pre_aggregator({}), "missing results"
    assert post_aggregator(_agg_state()) == []
    s = _agg_state(); del s["aggregated_report"]["title"]
    assert post_aggregator(s), "missing key flag"
    s = _agg_state(); s["aggregated_report"]["calculated_target"] = {"custom_ri": {"vitamin_d": {"value": 999}}}
    assert post_aggregator(s), "pass-through mismatch flag"
    s = _agg_state(); s["aggregated_report"]["guidelines"] = [None]
    assert post_aggregator(s), "guidelines flag"
    print("  aggregator OK")
```

`main()`에 `await test_aggregator()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_aggregator'`

- [ ] **Step 4: `agent/guardrails/checks.py`에 Aggregator 체크 추가**

```python
def pre_aggregator(state) -> list[str]:
    return [] if "execution_results" in state else ["execution_results 없음"]


def post_aggregator(state) -> list[str]:
    rep = state.get("aggregated_report")
    if not isinstance(rep, dict):
        return ["aggregated_report 없음"]
    p = []
    for k in ("title", "user_profile", "calculated_target", "ul_check", "guidelines"):
        if k not in rep:
            p.append(f"필수키 없음: {k}")
    by_task = {
        r["task_name"]: r.get("result")
        for r in state.get("execution_results", [])
        if r.get("status") == "success"
    }
    if "calculated_target" in rep and rep["calculated_target"] != by_task.get("calculate_dynamic_ri", {}):
        p.append("calculated_target가 executor 결과와 불일치")
    if "ul_check" in rep and rep["ul_check"] != by_task.get("validate_ul_guardrail", {}):
        p.append("ul_check가 executor 결과와 불일치")
    g = rep.get("guidelines")
    if not isinstance(g, list) or not all(isinstance(x, str) for x in g):
        p.append("guidelines 형식 오류")
    return p
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `aggregator OK`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/aggregator.md agent/guardrails/checks.py agent/test_guardrails.py
git commit -m "feat(guardrails): Aggregator 필수키/숫자 pass-through 체크"
```

---

### Task 7: Compliance 가드레일 (포맷 + PII)

**Files:**
- Create: `agent/guardrails/compliance.md`
- Modify: `agent/guardrails/checks.py`
- Modify: `agent/test_guardrails.py`

**Interfaces:**
- Produces: `pre_compliance(state) -> list[str]`, `post_compliance(state) -> list[str]`
- Consumes: `final_report`(dict: html, disclaimer, user_profile), `normalized_data`(원본 name/birth_date)

- [ ] **Step 1: `agent/guardrails/compliance.md` 생성**

```markdown
# Compliance 가드레일 (최종 = 포맷 + PII)

## pre
- `aggregated_report`가 state에 존재.

## post — 포맷
- `final_report.html`는 비어있지 않은 str.
- `final_report.disclaimer`에 "의료법상" 정문구 포함.

## post — PII (항상 차단)
- 원본 name/birth_date(normalized_data)가 html에 평문으로 나타나지 않음.
- `final_report.user_profile.name`이 원본과 다름(마스킹됨).
- 주민등록번호(예: 000000-0000000)·전화번호(01x-xxxx-xxxx) 정규식 패턴 미노출.

PII 범위: 이름·생년월일·주민등록번호·전화번호. 입력 필드가 늘면 여기에 추가.
```

- [ ] **Step 2: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
from guardrails.checks import pre_compliance, post_compliance


def _comp_state(html="<p>홍*동 리포트</p>", disc="…의료법상…"):
    return {
        "normalized_data": {"name": "홍길동", "birth_date": "1990-01-01"},
        "final_report": {"html": html, "disclaimer": disc,
                         "user_profile": {"name": "홍*동"}},
    }


async def test_compliance():
    assert pre_compliance({"aggregated_report": {}}) == []
    assert pre_compliance({}), "missing report"
    assert post_compliance(_comp_state()) == []
    assert post_compliance(_comp_state(html="")), "empty html flag"
    assert post_compliance(_comp_state(disc="없음")), "disclaimer flag"
    assert post_compliance(_comp_state(html="<p>홍길동 노출</p>")), "name leak flag"
    assert post_compliance(_comp_state(html="<p>주민 900101-1234567</p>")), "rrn flag"
    print("  compliance OK")
```

`main()`에 `await test_compliance()` 추가.

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: FAIL — `ImportError: cannot import name 'pre_compliance'`

- [ ] **Step 4: `agent/guardrails/checks.py`에 Compliance 체크 추가**

파일 상단 import에 추가:

```python
import re
```

함수 추가:

```python
def pre_compliance(state) -> list[str]:
    return [] if "aggregated_report" in state else ["aggregated_report 없음"]


def post_compliance(state) -> list[str]:
    fr = state.get("final_report")
    if not isinstance(fr, dict):
        return ["final_report 없음"]
    p = []
    html = fr.get("html")
    if not isinstance(html, str) or not html.strip():
        p.append("html 비어있음")
        html = ""
    if "의료법상" not in (fr.get("disclaimer") or ""):
        p.append("disclaimer 정문구 없음")

    nd = state.get("normalized_data", {})
    raw_name = nd.get("name")
    raw_birth = nd.get("birth_date")
    if raw_name and raw_name != "익명" and raw_name in html:
        p.append("이름 평문 노출")
    if raw_name and raw_name != "익명" and fr.get("user_profile", {}).get("name") == raw_name:
        p.append("user_profile 이름 미마스킹")
    if raw_birth and raw_birth in html:
        p.append("생년월일 평문 노출")
    if re.search(r"\d{6}-\d{7}", html):
        p.append("주민등록번호 패턴 노출")
    if re.search(r"01\d-?\d{3,4}-?\d{4}", html):
        p.append("전화번호 패턴 노출")
    return p
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `compliance OK`

- [ ] **Step 6: 커밋**

```bash
git add agent/guardrails/compliance.md agent/guardrails/checks.py agent/test_guardrails.py
git commit -m "feat(guardrails): Compliance 포맷/PII 마스킹 체크"
```

---

### Task 8: 파이프라인 배선 + 차단 응답

**Files:**
- Modify: `agent/graph/workflow.py` (6노드 guard 래핑)
- Modify: `agent/server.py` (GuardViolation → 안전 거부)
- Modify: `agent/test_guardrails.py` (end-to-end 통합)

**Interfaces:**
- Consumes: `guard` (Task 1), `checks.*` (Task 2–7), `graph` from `graph.workflow`, `GuardViolation`

- [ ] **Step 1: 실패 테스트 추가 — `agent/test_guardrails.py`**

```python
async def test_wired_graph():
    # 래핑된 그래프가 정상 입력에 대해 GuardViolation 없이 완주.
    from graph.workflow import graph
    st = await graph.ainvoke({
        "user_input": {"name": "홍길동", "age": 30, "gender": "female", "weight_kg": 60},
        "retry_count": 0,
    })
    assert "final_report" in st
    print("  wired_graph OK")
```

`main()`에 `await test_wired_graph()` 추가.

- [ ] **Step 2: 테스트 실패/에러 확인 (아직 미배선이면 통과할 수도 있으므로, 배선 후 검증이 핵심)**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: 이 시점엔 PASS 가능(가드 미적용 그래프). Step 3–4 후에도 PASS여야 함 = 가드가 정상 흐름을 막지 않음.

- [ ] **Step 3: `agent/graph/workflow.py` — 노드를 guard로 래핑**

import 블록에 추가:

```python
from guardrails.harness import guard
from guardrails import checks as C
```

`build_workflow()`의 6개 `add_node` 호출을 아래로 교체:

```python
    workflow.add_node("normalizer_node", guard(
        input_normalization_node, "normalizer", "guardrails/normalizer.md",
        pre=C.pre_normalizer, post=C.post_normalizer))
    workflow.add_node("planner_agent", guard(
        planner_agent_node, "planner", "guardrails/planner.md",
        pre=C.pre_planner, post=C.post_planner))
    workflow.add_node("executor_agent", guard(
        executor_node, "executor", "guardrails/executor.md",
        pre=C.pre_executor, post=C.post_executor))
    workflow.add_node("reviewer_agent", guard(
        specialized_review_node, "reviewer", "guardrails/reviewer.md",
        pre=C.pre_reviewer, post=C.post_reviewer))
    workflow.add_node("aggregator_agent", guard(
        aggregator_node, "aggregator", "guardrails/aggregator.md",
        pre=C.pre_aggregator, post=C.post_aggregator))
    workflow.add_node("compliance_agent", guard(
        legal_compliance_node, "compliance", "guardrails/compliance.md",
        pre=C.pre_compliance, post=C.post_compliance, on_violation="block"))
```

- [ ] **Step 4: `agent/server.py` — GuardViolation 처리**

import 블록에 추가:

```python
from guardrails.harness import GuardViolation
from nodes.compliance import DISCLAIMER
```

`final_state = await graph.ainvoke(initial_state)` 호출을 감싸는 try에 except 절 추가 (기존 `except Exception` **위에**):

```python
        try:
            final_state = await graph.ainvoke(initial_state)
        except GuardViolation as gv:
            print(f"[BLOCKED] {gv.node}: {gv.problems}")
            return {
                "status": "blocked",
                "message": "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다. "
                           "전문가와 상담하시기를 권장드립니다.",
                "disclaimer": DISCLAIMER,
            }
```

- [ ] **Step 5: 통합 테스트 통과 확인 (가드가 정상 흐름 막지 않음)**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_guardrails.py`
Expected: PASS — `wired_graph OK` / `ALL PASS`

- [ ] **Step 6: 기존 파이프라인 회귀 확인**

Run: `cd agent && PYTHONIOENCODING=utf-8 uv run python test_pipeline.py`
Expected: PASS — `ALL PASS`

- [ ] **Step 7: 커밋**

```bash
git add agent/graph/workflow.py agent/server.py agent/test_guardrails.py
git commit -m "feat(guardrails): 6노드 하네스 배선 + 차단 시 안전 거부 응답"
```

---

## Self-Review 결과

- **Spec coverage:** 목적1(spec .md 참조 + 프롬프트 주입)=Task 3 Step 5 + 각 .md. 목적2(이탈 flag)=Task 1 `flag`/`guard` + Task 2–7 post. 6노드 전부 Task 2–7. 최종 포맷+PII=Task 7. 배선/차단=Task 8. Non-goals(재산출/복구루프/LLM심판)=계획에 없음(준수).
- **Placeholder scan:** 없음. 모든 스텝에 실제 코드/명령.
- **Type consistency:** `pre_*`/`post_*` 모두 `state -> list[str]`. `guard(fn,name,spec_md,pre,post,on_violation)` 시그니처 Task 1 정의와 Task 8 호출 일치. `GuardViolation.node/.problems` 일관. `load_spec` 이름 일관. `MAX_RETRIES`는 `nodes.reviewer`에서 import.
