"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

// If already authenticated, go to dashboard
export default function LandingPage() {
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("cargoiq_token")) {
      window.location.href = "/dashboard";
    }
  }, []);

  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Leakage counter: R217,340/month = R7,245/day = R301.9/hr = R5.03/min
  const perSecond = 217_340 / 30 / 24 / 3600;
  const leakage   = Math.round(tick * perSecond);

  function zar(n: number) {
    return `R${n.toLocaleString("en-ZA")}`;
  }

  const PAIN = [
    {
      icon: "🩸",
      stat: "R14,169",
      label: "Durban storage penalty",
      desc: "One 40ft container held two days past the 3-day free window. Day 4 = R5,396. Day 5 = R8,773. Verified Maersk tariff, April 2026.",
    },
    {
      icon: "🛡️",
      stat: "25%",
      label: "of carrier invoices contain billing errors",
      desc: "Global freight audit data. Third-party auditors recover 6–8% of total freight spend. At R1.5M/month that is R60,000–R90,000 leaking silently.",
    },
    {
      icon: "⏰",
      stat: "R59,400",
      label: "unbilled detention per month",
      desc: "15 trucks × 4hrs avg wait at retail DCs × R1,100/hr. Only 3% of drivers receive full detention claims without GPS-verified proof.",
    },
    {
      icon: "⚠️",
      stat: "Section 99(2)",
      label: "personal liability for clearing agents",
      desc: "If the importer provides incorrect data and disappears before an audit, the clearing agent pays the understated duties, VAT, and excise — personally.",
    },
  ];

  const WHAT_CARGOIQ_DOES = [
    { label: "Runs the Compliance Shield on every shipment before SARS submission — catches HS code errors, VAT mismatches, SAD500 field 46 discrepancies" },
    { label: "Checks SARS eFiling RLA status daily at 06:00 — alerts you at 06:01 if an importer's registration is suspended" },
    { label: "Audits every carrier invoice against your negotiated rate cards — flags overcharges and generates a printable dispute notice" },
    { label: "Captures driver WhatsApp check-ins (ARRIVED / DEPARTED) and converts them into billable waiting-time charge notices — no GPS hardware needed" },
    { label: "Monitors Transnet and shipping-line portals every 30 minutes — tells you the moment a container is released" },
    { label: "Generates a monthly Savings Certificate: CargoWise fees reduced, fines prevented, overcharges recovered, ROI multiple. One document for the CFO meeting." },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white">

      {/* ── Nav ──────────────────────────────────────────────── */}
      <nav className="border-b border-slate-800/60 px-6 py-4 flex items-center justify-between sticky top-0 bg-slate-950/90 backdrop-blur z-50">
        <div className="font-mono text-xl font-bold">
          Cargo<span className="text-amber-500">IQ</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/calculator" className="text-sm text-slate-400 hover:text-white transition">
            Calculate Leakage
          </Link>
          <Link href="/auth/login" className="text-sm bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold px-4 py-2 rounded transition">
            Client Login
          </Link>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <p className="text-xs font-mono tracking-widest text-amber-500 uppercase mb-6">
          South Africa's only AI compliance and cost layer for CargoWise
        </p>
        <h1 className="text-5xl md:text-6xl font-bold leading-tight mb-6">
          Your freight operation is
          <span className="text-red-400"> bleeding</span>.
          <br />
          You just can't see where.
        </h1>
        <p className="text-slate-400 text-lg leading-relaxed mb-10 max-w-2xl mx-auto">
          Carrier invoice overcharges. SARS storage penalties. Unbilled waiting time.
          RLA suspensions discovered on Monday morning. For a mid-size operation
          running 15 containers a month, the total is <strong className="text-white">R217,340 every month</strong> —
          leaving through gaps no one is watching.
        </p>

        {/* Live counter */}
        <div className="inline-block bg-red-950 border border-red-800 rounded-2xl px-8 py-6 mb-10">
          <p className="text-xs font-mono text-red-400 uppercase tracking-wider mb-1">
            Since you opened this page, the average SA forwarder has leaked
          </p>
          <div className="text-5xl font-mono font-bold text-red-400">
            {zar(leakage)}
          </div>
          <p className="text-xs text-slate-600 mt-1">
            Based on R217,340/month ÷ 30 days ÷ 86,400 seconds
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/calculator"
            className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-8 py-4 rounded-lg text-base transition">
            Calculate My Leakage →
          </Link>
          <a href="mailto:thabiso@nahalabs.co.za?subject=CargoIQ Shadow Audit"
            className="border border-slate-700 hover:border-slate-500 text-slate-300 hover:text-white px-8 py-4 rounded-lg text-base transition">
            Request Free Shadow Audit
          </a>
        </div>
      </section>

      {/* ── Pain ─────────────────────────────────────────────── */}
      <section className="border-t border-slate-800 py-20">
        <div className="max-w-5xl mx-auto px-6">
          <p className="text-xs font-mono tracking-widest text-amber-500 uppercase text-center mb-3">
            The Numbers
          </p>
          <h2 className="text-3xl font-bold text-center mb-12">
            Four verified figures that stop freight owners cold
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            {PAIN.map((p) => (
              <div key={p.stat} className="bg-slate-900 border border-slate-800 hover:border-red-800 rounded-xl p-6 transition">
                <div className="text-3xl mb-3">{p.icon}</div>
                <div className="text-3xl font-mono font-bold text-red-400 mb-1">{p.stat}</div>
                <div className="text-sm font-semibold text-white mb-2">{p.label}</div>
                <div className="text-sm text-slate-500 leading-relaxed">{p.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── What CargoIQ does ─────────────────────────────────── */}
      <section className="border-t border-slate-800 py-20 bg-slate-900/40">
        <div className="max-w-4xl mx-auto px-6">
          <p className="text-xs font-mono tracking-widest text-amber-500 uppercase text-center mb-3">
            The Product
          </p>
          <h2 className="text-3xl font-bold text-center mb-4">
            CargoIQ sits on top of CargoWise.
            <span className="text-slate-400"> It does not replace it.</span>
          </h2>
          <p className="text-slate-400 text-center text-sm mb-10 max-w-xl mx-auto">
            Every alternative on the market — GoFreight, Magaya, Descartes — wants you
            to migrate. A 12-month project, R200,000 in consulting, and no guarantee.
            CargoIQ plugs in alongside what you already use and starts finding money on day one.
          </p>
          <div className="space-y-3">
            {WHAT_CARGOIQ_DOES.map((item, i) => (
              <div key={i} className="flex items-start gap-3 bg-slate-900 border border-slate-800 rounded-lg px-5 py-4">
                <span className="text-emerald-400 font-bold mt-0.5">✓</span>
                <p className="text-sm text-slate-300 leading-relaxed">{item.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── WiseTech pricing context ──────────────────────────── */}
      <section className="border-t border-slate-800 py-20">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <p className="text-xs font-mono tracking-widest text-amber-500 uppercase mb-3">
            The December 2025 Shift
          </p>
          <h2 className="text-3xl font-bold mb-6">
            CargoWise switched to <span className="text-red-400">$19.95 per transaction event</span>
            <br className="hidden md:block" /> on December 1, 2025.
          </h2>
          <p className="text-slate-400 leading-relaxed max-w-2xl mx-auto mb-8">
            A mid-size operation where clerks hit Save five to seven times per shipment
            now pays <strong className="text-white">$30,000–$42,000 per month</strong> in CargoWise transaction fees.
            WiseTech reported 20–50% cost increases across their customer base.
            CargoIQ's WiseLayer compacts those five to seven events into one XML transmission —
            a 60–70% reduction in billable events with zero change to your workflow.
          </p>
          <div className="inline-block bg-emerald-950 border border-emerald-800 rounded-xl px-8 py-6">
            <p className="text-emerald-400 text-sm mb-1">300 shipments/month at 6 events each</p>
            <p className="text-white text-2xl font-mono font-bold">$35,910 → $10,773</p>
            <p className="text-slate-500 text-xs mt-1">CargoWise fees, before and after WiseLayer compaction</p>
          </div>
        </div>
      </section>

      {/* ── Proof ─────────────────────────────────────────────── */}
      <section className="border-t border-slate-800 py-20 bg-slate-900/40">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <p className="text-xs font-mono tracking-widest text-amber-500 uppercase mb-3">
            The Proof
          </p>
          <h2 className="text-3xl font-bold mb-6">
            We run the Shadow Audit before you sign anything.
          </h2>
          <p className="text-slate-400 leading-relaxed max-w-2xl mx-auto mb-8">
            Send us 20 of your most recent shipment documents. CargoIQ runs the Compliance Shield
            on all of them and shows you exactly what your team missed — HS code errors,
            invoice/SAD500 mismatches, RLA status issues — in a signed findings report.
            No software installed. No workflow changed. No commitment.
            If we find nothing, you owe us nothing.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/calculator"
              className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-8 py-4 rounded-lg text-base transition">
              Calculate My Leakage →
            </Link>
            <a href="mailto:thabiso@nahalabs.co.za?subject=Shadow Audit Request&body=Please contact me about a free shadow audit."
              className="border border-amber-500/40 hover:border-amber-500 text-amber-400 hover:text-amber-300 px-8 py-4 rounded-lg text-base transition">
              Request Shadow Audit
            </a>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────── */}
      <footer className="border-t border-slate-800 py-8 px-6">
        <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="font-mono font-bold text-slate-400">
            Cargo<span className="text-amber-500">IQ</span>
            <span className="text-slate-600 font-normal ml-2">· NahaLabs (Pty) Ltd · Johannesburg</span>
          </div>
          <div className="flex gap-6 text-xs text-slate-600">
            <span>POPIA Compliant</span>
            <span>Data hosted in South Africa</span>
            <Link href="/auth/login" className="hover:text-slate-400 transition">Client Login</Link>
          </div>
        </div>
      </footer>

    </div>
  );
}
