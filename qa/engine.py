# -*- coding: utf-8 -*-
"""frontend2 판정 엔진을 qa 폴더에서 불러 쓰기 위한 어댑터.

sys.path 를 만지는 곳은 이 파일 하나뿐입니다. 다른 스크립트는 여기서
import 만 하면 되므로, frontend2 위치가 바뀌어도 이 파일만 고치면 됩니다.

frontend2 의 analyze/exam/standards 는 표준 라이브러리에만 의존하므로
(fastapi·psycopg 없음) 별도 venv 없이 그냥 python 으로 돌아갑니다.
"""
import json
import sys
from pathlib import Path

QA_DIR = Path(__file__).resolve().parent
FRONTEND2 = QA_DIR.parent / "frontend2"

if not (FRONTEND2 / "analyze.py").exists():
    raise SystemExit(
        "frontend2/analyze.py 를 찾지 못했습니다.\n"
        f"  찾아본 곳: {FRONTEND2}\n"
        "  qa 폴더가 my_hub2 바로 아래에 있어야 합니다."
    )

sys.path.insert(0, str(FRONTEND2))

from analyze import to_report            # noqa: E402
from standards import STD_LIST, MED_RULES, find_std, level_of, NEAR_RATIO  # noqa: E402


def read_json(path):
    """읽기는 항상 UTF-8. 이 환경의 기본 인코딩(CP949)에 맡기면 한글이 깨집니다."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_text(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def load_cases():
    """cases/case*.json 을 번호 순으로."""
    files = sorted((QA_DIR / "cases").glob("case*.json"))
    return [read_json(f) for f in files]


def load_expected():
    return read_json(QA_DIR / "cases" / "expected.json")


def standards_fingerprint():
    """지금 기준값의 지문.

    기대값(expected.json)은 '오늘의 standards.py' 를 보고 손으로 계산한 것이라,
    기준값이 바뀌면 기대값도 다시 봐야 합니다. 그때 테스트가 그냥 '실패'로
    보이면 원인을 매번 손으로 추적하게 되므로, 기준값 변경은 별도로 감지해
    '실패'가 아니라 '기준이 움직였다'로 알려 줍니다.
    """
    return {
        s["name"]: {"unit": s["unit"], "rda": s.get("rda"), "ul": s.get("ul"),
                    "meal": s.get("meal"), "iu": s.get("iu"),
                    "ul_basis": s.get("ul_basis")}
        for s in STD_LIST
    }
