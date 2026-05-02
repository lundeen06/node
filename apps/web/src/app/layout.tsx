import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "@/styles/globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-geist-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export const metadata: Metadata = {
  title: "node · constellation ops",
  description: "Cursor for satellite operators — situational awareness and maneuver planning (demo shell).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${sans.variable} ${mono.variable} min-h-screen bg-background font-sans`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
