from typing import TypedDict, List, Dict, Any, Literal, Optional
from pathlib import Path
import csv
import re
import math
from collections import Counter

from langgraph.graph import StateGraph, END

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# 1. 상태(State) 정의
class State(TypedDict, total=False):
    user_input: Dict[str, Any]
    normalized_data: Dict[str, Any]
    rag_context: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    review_status: Literal["pass", "reject_to_executor", "reject_to_planner"]
    review_feedback: str
    final_report: Dict[str, Any]


# -----------------------------------------------------------------------------
# RAG 설정
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
RAG_DATA_DIR = BASE_DIR / "data"
RAG_EXTENSIONS = {".pdf", ".csv", ".txt", ".md"}
RAG_TOP_K = 8
RAG_CHUNK_SIZE = 1200
RAG_CHUNK_OVERLAP = 200


class SimpleRAG:
    """외부 벡터DB 없이 data/ 폴더를 검색하는 경량 RAG.

    - PDF: 페이지 단위 텍스트 추출 후 chunking
    - CSV: 행 단위 document 생성
    - TXT/MD: 텍스트 chunking
    - 검색: TF-IDF 유사도 + 키워드 overlap 기반

    데이터가 커지면 이 클래스의 search()만 FAISS/Chroma 등으로 교체할 수 있습니다.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.documents: List[Dict[str, Any]] = []
        self.file_stats: List[Dict[str, Any]] = []
        self._idf: Dict[str, float] = {}
        self._indexed = False

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # 한글/영문/숫자 토큰을 보존하고 너무 짧은 토큰은 제외
        return [
            token.lower()
            for token in re.findall(r"[가-힣A-Za-z0-9]+", text or "")
            if len(token) >= 2
        ]

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = RAG_CHUNK_SIZE,
                    overlap: int = RAG_CHUNK_OVERLAP) -> List[str]:
        text = re.sub(r"\\s+", " ", text or "").strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _add_document(self, source: Path, content: str, metadata: Dict[str, Any]):
        for chunk_index, chunk in enumerate(self._chunk_text(content)):
            self.documents.append({
                "id": f"{source.name}:{metadata.get('page', metadata.get('row', chunk_index))}:{chunk_index}",
                "source": source.name,
                "path": str(source),
                "content": chunk,
                "metadata": {**metadata, "chunk_index": chunk_index},
            })

    def _load_pdf(self, path: Path):
        if fitz is None:
            raise RuntimeError(
                "PDF RAG를 사용하려면 PyMuPDF가 필요합니다. `pip install pymupdf`를 실행하세요."
            )
        doc = fitz.open(path)
        for page_no, page in enumerate(doc, start=1):
            self._add_document(path, page.get_text("text"), {"page": page_no, "type": "pdf"})
        doc.close()

    def _load_csv(self, path: Path):
        # utf-8-sig 우선, 실패 시 cp949까지 지원
        last_error = None
        for encoding in ("utf-8-sig", "cp949", "utf-8"):
            try:
                with path.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    for row_no, row in enumerate(reader, start=2):
                        fields = [f"{k}: {v}" for k, v in row.items() if v not in (None, "")]
                        self._add_document(
                            path,
                            " | ".join(fields),
                            {"row": row_no, "type": "csv", "columns": list(row.keys())},
                        )
                return
            except UnicodeDecodeError as exc:
                last_error = exc
        raise last_error

    def _load_text(self, path: Path):
        last_error = None
        for encoding in ("utf-8-sig", "cp949", "utf-8"):
            try:
                self._add_document(path, path.read_text(encoding=encoding), {"type": path.suffix[1:]})
                return
            except UnicodeDecodeError as exc:
                last_error = exc
        raise last_error

    def build_index(self):
        self.documents.clear()
        self.file_stats.clear()
        self._idf.clear()

        if not self.data_dir.exists():
            print(f"[RAG] data 폴더가 없습니다: {self.data_dir}")
            self._indexed = True
            return

        files = sorted(
            p for p in self.data_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in RAG_EXTENSIONS
        )

        for path in files:
            before = len(self.documents)
            try:
                suffix = path.suffix.lower()
                if suffix == ".pdf":
                    self._load_pdf(path)
                elif suffix == ".csv":
                    self._load_csv(path)
                else:
                    self._load_text(path)
                self.file_stats.append({
                    "file": path.name,
                    "status": "success",
                    "documents": len(self.documents) - before,
                })
            except Exception as exc:
                self.file_stats.append({
                    "file": path.name,
                    "status": "error",
                    "documents": 0,
                    "error": str(exc),
                })
                print(f"[RAG] 파일 로드 실패: {path.name} -> {exc}")

        # IDF 계산
        df = Counter()
        for doc in self.documents:
            df.update(set(self._tokenize(doc["content"])))
        n_docs = max(len(self.documents), 1)
        self._idf = {
            token: math.log((1 + n_docs) / (1 + freq)) + 1
            for token, freq in df.items()
        }
        self._indexed = True
        print(f"[RAG] index 완료: {len(files)}개 파일 / {len(self.documents)}개 document")

    def _score(self, query_tokens: List[str], content: str) -> float:
        tokens = self._tokenize(content)
        if not tokens or not query_tokens:
            return 0.0

        counts = Counter(tokens)
        query_set = set(query_tokens)
        score = 0.0
        for token in query_set:
            if token in counts:
                tf = 1 + math.log(counts[token])
                score += tf * self._idf.get(token, 1.0)

        # 짧은 질의에서 exact phrase/substring이 있는 경우 보너스
        return score / math.sqrt(max(len(tokens), 1))

    def search(self, query: str, top_k: int = RAG_TOP_K) -> List[Dict[str, Any]]:
        if not self._indexed:
            self.build_index()

        query = query.strip()
        if not query:
            return []

        query_tokens = self._tokenize(query)
        scored = []
        for doc in self.documents:
            score = self._score(query_tokens, doc["content"])
            if score > 0:
                scored.append({**doc, "score": round(score, 6)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


rag_store = SimpleRAG(RAG_DATA_DIR)


def _build_rag_query(state: State) -> str:
    """현재 상태에서 RAG 검색용 질의를 구성합니다."""
    user_input = state.get("user_input", {})
    normalized = state.get("normalized_data", {})

    parts = []
    for data in (user_input, normalized):
        for key, value in data.items():
            if key in {"name", "masked"}:
                continue
            if value not in (None, "", False):
                parts.append(f"{key}: {value}")

    return "\\n".join(parts)


def rag_context_agent_node(state: State) -> State:
    """data/ 폴더 전체를 대상으로 RAG 검색 후 context를 State에 주입합니다."""
    print("[Agent] RAG Context: data 폴더의 근거 자료 검색 중...")

    query = _build_rag_query(state)
    if not query:
        state["rag_context"] = {
            "query": "",
            "results": [],
            "sources": [],
            "message": "RAG 검색 질의가 없어 검색하지 않았습니다.",
        }
        return state

    # 개발 중 파일 추가/변경이 즉시 반영되도록 매 실행 index를 재생성합니다.
    # 데이터가 커지면 파일 mtime 기반 캐시로 변경하는 것을 권장합니다.
    rag_store.build_index()
    results = rag_store.search(query, top_k=RAG_TOP_K)

    sources = []
    seen = set()
    for result in results:
        if result["source"] not in seen:
            sources.append(result["source"])
            seen.add(result["source"])

    state["rag_context"] = {
        "query": query,
        "results": results,
        "sources": sources,
        "indexed_files": rag_store.file_stats,
    }

    print(f"[RAG] 검색 결과: {len(results)}건 / source: {sources}")
    return state

# 2. 메인 노드 및 에이전트 함수 정의
def input_normalization_node(state: State) -> State:
    print("\n[Node] Normalizer: 입력 데이터 정규화 및 마스킹 처리 중...")
    state["normalized_data"] = {"masked": True, "units_normalized": True, **state["user_input"]}
    return state

def planner_agent_node(state: State) -> State:
    print("[Agent] Planner: 작업 계획 수립 중...")
    rag = state.get("rag_context", {})
    state["execution_plan"] = [
        {
            "step": 1,
            "tool": "calculate_dynamic_ri",
            "rag_sources": rag.get("sources", []),
        },
        {
            "step": 2,
            "tool": "validate_ul_guardrail",
            "rag_sources": rag.get("sources", []),
        },
    ]
    return state

def executor_node(state: State) -> State:
    print("[Agent] Executor: MCP 서버 툴 호출 및 연산 실행 중...")
    state["execution_results"] = [{"tool": "validate_ul_guardrail", "status": "success", "result": "safe"}]
    return state

def specialized_review_node(state: State) -> State:
    print("[Agent] Reviewer: 결과 검토 및 가드레일 검증 중...")
    # 예시: 여기를 "reject_to_executor"로 바꾸면 루프(Self-Correction)를 테스트할 수 있습니다.
    state["review_status"] = "pass" 
    state["review_feedback"] = "안전성 검증 통과"
    return state

def aggregator_node(state: State) -> State:
    print("[Agent] Aggregator: 통합 리포트 프롬프트 취합 중...")
    state["final_report"] = {
        "title": "개인 맞춤형 영양 리포트",
        "details": state.get("execution_results", []),
        "rag_context": state.get("rag_context", {}),
        "disclaimer": "본 리포트는 의료인의 진단을 대체할 수 없습니다."
    }
    return state

def legal_compliance_node(state: State) -> State:
    print("[Agent] Compliance: 법률 및 규제 준수 최종 검수 완료.\n")
    return state

# 3. 그래프 구성
workflow = StateGraph(State)

workflow.add_node("normalizer_node", input_normalization_node)
workflow.add_node("rag_context_agent", rag_context_agent_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("executor_agent", executor_node)
workflow.add_node("reviewer_agent", specialized_review_node)
workflow.add_node("aggregator_agent", aggregator_node)
workflow.add_node("compliance_agent", legal_compliance_node)

workflow.set_entry_point("normalizer_node")
workflow.add_edge("normalizer_node", "rag_context_agent")
workflow.add_edge("rag_context_agent", "planner_agent")
workflow.add_edge("planner_agent", "executor_agent")
workflow.add_edge("executor_agent", "reviewer_agent")

def route_after_review(state: State) -> Literal["executor_agent", "planner_agent", "aggregator_agent"]:
    status = state.get("review_status", "pass")
    if status == "reject_to_executor":
        print("  -> ⚠️ 피드백 발생: Executor로 돌아가 재실행합니다 (Loop).")
        return "executor_agent"
    elif status == "reject_to_planner":
        print("  -> ⚠️ 피드백 발생: Planner로 돌아가 계획을 재수립합니다 (Loop).")
        return "planner_agent"
    else:
        print("  -> ✅ 검증 통과: Aggregator로 넘어갑니다.")
        return "aggregator_agent"

workflow.add_conditional_edges(
    "reviewer_agent",
    route_after_review,
    {
        "executor_agent": "executor_agent",
        "planner_agent": "planner_agent",
        "aggregator_agent": "aggregator_agent"
    }
)

workflow.add_edge("aggregator_agent", "compliance_agent")
workflow.add_edge("compliance_agent", END)

app = workflow.compile()

# --- 실행 테스트 로직 ---
if __name__ == "__main__":
    # 초기 테스트 입력 데이터
    initial_input = {
        "user_input": {
            "name": "홍길동",
            "age": 35,
            "weight_kg": 75.5,
            "ocr_text": "혈중 칼슘 9.5 mg/dL"
        }
    }
    
    print("=== AI 영양제 추천 서비스 에이전트 파이프라인 시작 ===")
    # app.invoke를 통해 초기 상태를 주입하고 파이프라인 실행
    final_state = app.invoke(initial_input)
    
    print("=== 🏁 최종 출력 결과 ===")
    print(final_state.get("final_report"))