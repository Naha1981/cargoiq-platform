import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "CargoIQ — Logistics Intelligence",
  description: "South Africa's AI compliance and cost containment layer for freight forwarders.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body className="bg-canvas text-text-primary antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
