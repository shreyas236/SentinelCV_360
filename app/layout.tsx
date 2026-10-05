import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SentinelCV 360 | CV Assurance Workspace",
  description: "Evidence-driven dataset, model and inference integrity assurance, trust lineage and forensic investigation.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
