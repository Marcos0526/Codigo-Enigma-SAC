import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Enigma SAC | Physical Sciences Discovery",
  description:
    "Connect your research interests with NASA Physical Sciences Informatics datasets through semantic discovery and interactive exploration.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark">
      <body>{children}</body>
    </html>
  );
}
