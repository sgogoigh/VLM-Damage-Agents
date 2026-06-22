import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orchestrate Claims Desk",
  description:
    "Multi-modal damage-claim evidence review — a support chat that adjudicates photos against the claim.",
};

export const viewport: Viewport = {
  themeColor: "#0e1525",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
