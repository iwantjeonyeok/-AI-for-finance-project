import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "리서치 기반 개인화 포트폴리오",
  description:
    "리서치 보고서 기반 개인화 Black–Litterman 포트폴리오 데모",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
