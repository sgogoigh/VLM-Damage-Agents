import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orchestrate Claim Verifier",
  description: "Chat interface for claim evidence verification",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
