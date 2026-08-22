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
