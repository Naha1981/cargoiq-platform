"use client";
import { useState } from "react";
import Link from "next/link";

// ── Verified April 2026 constants (mirrors apps/api/core/constants.py) ──
const C = {
  DURBAN_40FT_DAY4:           5_396,
  DURBAN_40FT_DAY5_PLUS:      8_773,
  get DURBAN_TWO_DAY()        { return this.DURBAN_40FT_DAY4 + this.DURBAN_40FT_DAY5_PLUS; }, // 14169
  DURBAN_40FT_REEFER_PEAK:    12_567,  // /day from Day 3 in peak season
  CAPE_TOWN_40FT_MPT_DAY7:     3_533,
  INVOICE_ERROR_RATE:          0.04,   // conservative 4% (industry is 6-8%)
  DETENTION_RATE_PER_HOUR:     1_100,
  DETENTION_UNBILLED_RATE:     0.90,
  DETENTION_AVG_WAIT_HOURS:    4.0,
  DETENTION_FREE_HOURS:        2.0,
  EMPTY_MILE_RATE:             0.20,
  ROAD_LEG_COST:              25_000,
  FREIGHT_COST_PER_CONTAINER: 100_000,
};

function zar(n: number) {
  return `R${Math.round(n).toLocaleString("en-ZA")}`;
}

interface LeakageResult {
  containers:         number;
  freightSpend:       number;
  detention:          number;
  carrierErrors:      number;
  sarsStorage:        number;
  emptyBackhaul:      number;
  total:              number;
  roi:                number;
  annualSaving:       number;
  cargoiqCost:        number;
}

function calculate(containers: number, hasTrucks: boolean, crossBorder: boolean): LeakageResult {
  const freightSpend     = containers * C.FREIGHT_COST_PER_CONTAINER;

  // 1. Unbilled detention: only relevant if they have trucks
  const billableWaitHours = Math.max(0, C.DETENTION_AVG_WAIT_HOURS - C.DETENTION_FREE_HOURS);
  const detention = hasTrucks
    ? containers * billableWaitHours * C.DETENTION_RATE_PER_HOUR * C.DETENTION_UNBILLED_RATE
    : 0;

  // 2. Carrier invoice overcharges: 4% of freight spend
  const carrierErrors = freightSpend * C.INVOICE_ERROR_RATE;

  // 3. SARS storage: assume 1 hold per month, 2 days past free time in Durban
  const sarsStorage = C.DURBAN_TWO_DAY;

  // 4. Empty backhaul: only relevant if cross-border routes
  const emptyBackhaul = crossBorder
    ? containers * C.ROAD_LEG_COST * C.EMPTY_MILE_RATE
    : 0;

  const total       = detention + carrierErrors + sarsStorage + emptyBackhaul;
  const cargoiqCost = 8_000;
  const roi         = Math.round(total / cargoiqCost);
  const annualSaving = total * 12;

  return { containers, freightSpend, detention, carrierErrors, sarsStorage, emptyBackhaul, total, roi, annualSaving, cargoiqCost };
}

export default function CalculatorPage() {
  const [containers, setContainers] = useState(15);
  const [hasTrucks,  setHasTrucks]  = useState(true);
  const [crossBorder, setCrossBorder] = useState(false);
  const [result,     setResult]     = useState<LeakageResult | null>(null);
  const [done,       setDone]       = useState(false);

  const run = () => {
    setResult(calculate(containers, hasTrucks, crossBorder));
    setDone(true);
  };

  const LineItem = ({ icon, label, sub, amount, show = true }: any) => {
    if (!show) return null;
    return (
      <div className="flex items-start justify-between py-4 border-b border-slate-800 last:border-0">
        <div className="flex items-start gap-3">
          <span className="text-2xl mt-0.5">{icon}</span>
          <div>
            <p className="text-sm font-medium text-white">{label}</p>
            <p className="text-xs text-slate-500 mt-0.5 max-w-xs">{sub}</p>
          </div>
        </div>
        <span className="font-mono text-base font-semibold text-red-400 flex-shrink-0 ml-4">
          {zar(amount)}
        </span>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* Nav */}
      <nav className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="font-mono text-lg font-bold">
          Cargo<span className="text-amber-500">IQ</span>
        </div>
        <Link href="/auth/login" className="text-xs text-slate-400 hover:text-white transition">
          Client Login →
        </Link>
      </nav>

      <div className="max-w-2xl mx-auto px-6 py-12">

        {/* Heading */}
        <div className="text-center mb-10">
          <p className="text-xs font-mono tracking-widest text-amber-500 uppercase mb-3">
            Free Shadow Audit Calculator
          </p>
          <h1 className="text-3xl font-bold text-white mb-3">
            How much is your freight operation leaking?
          </h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            Based on verified April 2026 Durban port tariffs and global freight audit data.
            Takes 30 seconds.
          </p>
        </div>

        {/* Input card */}
        {!done && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Containers per month (40ft equivalent)
              </label>
              <input
                type="range"
                min={5} max={100} step={5}
                value={containers}
                onChange={e => setContainers(Number(e.target.value))}
                className="w-full accent-amber-500"
              />
              <div className="flex justify-between mt-1">
                <span className="text-xs text-slate-600">5</span>
                <span className="text-2xl font-mono font-bold text-white">{containers}</span>
                <span className="text-xs text-slate-600">100</span>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Your operation includes:
              </p>
              <label className="flex items-center gap-3 cursor-pointer group">
                <input type="checkbox" checked={hasTrucks} onChange={e => setHasTrucks(e.target.checked)}
                  className="w-4 h-4 rounded accent-amber-500" />
                <span className="text-sm text-slate-300 group-hover:text-white transition">
                  Own or contracted truck fleet (drivers waiting at DCs/warehouses)
                </span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer group">
                <input type="checkbox" checked={crossBorder} onChange={e => setCrossBorder(e.target.checked)}
                  className="w-4 h-4 rounded accent-amber-500" />
                <span className="text-sm text-slate-300 group-hover:text-white transition">
                  Cross-border routes (Beitbridge, Lebombo, Nakop, Vioolsdrift)
                </span>
              </label>
            </div>

            <button
              onClick={run}
              className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold py-4 rounded-lg text-base transition"
            >
              Calculate My Leakage
            </button>
          </div>
        )}

        {/* Result card */}
        {done && result && (
          <div className="space-y-4">

            {/* Hero total */}
            <div className="bg-gradient-to-br from-red-950 to-slate-900 border border-red-800 rounded-xl p-8 text-center">
              <p className="text-xs font-mono tracking-widest text-red-400 uppercase mb-2">
                Estimated Monthly Revenue Leakage
              </p>
              <div className="text-6xl font-mono font-bold text-red-400 mb-2">
                {zar(result.total)}
              </div>
              <p className="text-slate-500 text-sm">
                {zar(result.annualSaving)} per year ·{" "}
                {result.containers} containers/month
              </p>
            </div>

            {/* Breakdown */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Where it's leaking
              </p>
              <LineItem
                icon="🩸"
                label="SARS Storage Penalty — Durban"
                sub={`1 container held 2 days past free time: Day 4 = R${C.DURBAN_40FT_DAY4.toLocaleString()} + Day 5 = R${C.DURBAN_40FT_DAY5_PLUS.toLocaleString()} (verified April 2026 tariff)`}
                amount={result.sarsStorage}
              />
              <LineItem
                icon="🛡️"
                label="Carrier Invoice Overcharges"
                sub={`25% of freight invoices contain billing errors. At 4% conservative recovery rate on R${(result.freightSpend).toLocaleString("en-ZA")} monthly freight spend`}
                amount={result.carrierErrors}
              />
              <LineItem
                icon="⏰"
                label="Unbilled Truck Detention"
                sub={`${result.containers} trucks × 2hrs billable wait × R${C.DETENTION_RATE_PER_HOUR.toLocaleString("en-ZA")}/hr. Only 3% of drivers get full claim paid without GPS proof.`}
                amount={result.detention}
                show={hasTrucks}
              />
              <LineItem
                icon="🚛"
                label="Empty Backhaul Inefficiency"
                sub={`15–20% of cross-border mileage is empty running. ${result.containers} trucks × R${C.ROAD_LEG_COST.toLocaleString("en-ZA")} road leg × 20%`}
                amount={result.emptyBackhaul}
                show={crossBorder}
              />
            </div>

            {/* ROI */}
            <div className="bg-emerald-950 border border-emerald-800 rounded-xl p-6 text-center">
              <p className="text-xs font-mono tracking-widest text-emerald-400 uppercase mb-1">
                CargoIQ ROI at R8,000/month
              </p>
              <div className="text-5xl font-mono font-bold text-emerald-400 mb-1">
                {result.roi}×
              </div>
              <p className="text-slate-400 text-sm">
                You pay R8,000. CargoIQ finds {zar(result.total)}.
                Pays for itself in the first week.
              </p>
            </div>

            {/* Data caveat */}
            <p className="text-xs text-slate-600 text-center leading-relaxed px-4">
              Storage figures: Maersk revised tariffs, Durban, effective 15 April 2026.
              Invoice error rate: global freight audit industry average (multiple sources).
              Detention and empty-mile figures: SA logistics industry estimates.
              This is an indicative estimate — actual figures depend on your specific operation.
            </p>

            {/* CTAs */}
            <div className="space-y-3 pt-2">
              <a
                href="mailto:thabiso@nahalabs.co.za?subject=Shadow Audit Request&body=I used the calculator and want a real audit on my shipments."
                className="block w-full text-center bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold py-4 rounded-lg text-base transition"
              >
                Start My Free Shadow Audit
              </a>
              <button
                onClick={() => { setDone(false); setResult(null); }}
                className="block w-full text-center text-slate-500 hover:text-slate-300 text-sm py-2 transition"
              >
                Recalculate
              </button>
            </div>
          </div>
        )}

        {/* Footer note */}
        <p className="text-center text-slate-700 text-xs mt-10">
          CargoIQ (Pty) Ltd · Johannesburg · POPIA Compliant
        </p>
      </div>
    </div>
  );
}
