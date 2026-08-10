import type { Metadata } from "next";
import "./globals.css";
import Topbar from "./Topbar";

export const metadata: Metadata = {
  title: "영양제 추천 엔진 — KDRI 2025",
  description:
    "2025 한국인 영양소 섭취기준에 근거한 참고용 영양제 분석. 모든 숫자는 추적 가능합니다.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <Topbar />
        {children}
      </body>
    </html>
  );
}
