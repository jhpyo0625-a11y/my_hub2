import Link from "next/link";

export default function Home() {
  return (
    <main className="wrap">
      <div className="hero">
        <span className="screen-tag">영양제 추천 엔진 · KDRI 2025</span>
        <h1>모든 숫자가 국가 기준에 근거하고, 추적 가능합니다</h1>
        <p className="lede">
          2025 한국인 영양소 섭취기준(KDRI 2025)에 근거해 복용 중인 영양제를
          30개 영양소로 분석합니다. 표시된 모든 수치는 계산 근거를 펼쳐 확인할 수
          있습니다.
        </p>

        <div className="actions" style={{ justifyContent: "center" }}>
          <Link className="btn btn-primary" href="/intake">
            시작하기
          </Link>
        </div>

        <div className="value">
          <strong>왜 이 서비스인가요?</strong>
          <br />
          추천량은 추정하지 않습니다. 목표 섭취량은 KDRI 2025, 식이 기여는
          국민 평균, 상한 여유는 상한섭취량에서 나옵니다. 근거가 없는 항목은
          &ldquo;판단 보류&rdquo;로 남겨 과대 추천을 막습니다.
        </div>
      </div>

      <p className="disclaimer">
        본 서비스는 진단·치료를 목적으로 하지 않으며, 2025 한국인 영양소
        섭취기준에 근거한 참고 정보를 제공합니다. 질환이 있거나 약을 복용
        중이신 경우 의사·약사와 상담하세요.
      </p>
    </main>
  );
}
