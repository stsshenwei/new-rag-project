import "./globals.css";
import type { Metadata } from "next";
import { AppFrame } from "./components/AppFrame";

export const metadata: Metadata = {
  title: "Bee",
  description: "私有知识库问答助手",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <AppFrame>{children}</AppFrame>
      </body>
    </html>
  );
}
