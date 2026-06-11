import type { Metadata } from "next";
export const metadata: Metadata = { title: "CargoIQ Sentinel — Live Intelligence" };
export default function SentinelLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
