import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Enigma SAC",
  description: "Semantic discovery for NASA PSI combustion science datasets"
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
