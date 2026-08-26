import type { Metadata } from "next";
import { Inter, Spectral, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// The story editor face. Spectral is a screen-first serif with a large
// x-height - it holds up at 17px over long drafting sessions.
const spectral = Spectral({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-spectral",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-jb",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Story Studio — Human–AI Co-Creative Storytelling",
  description:
    "An educational writing environment where the AI asks instead of answers. ET617 Group 15.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${spectral.variable} ${mono.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
