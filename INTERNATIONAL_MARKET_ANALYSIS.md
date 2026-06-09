# CargoIQ — International Market Analysis
## China-to-SEA Freight Forwarding Opportunity
### Research Validated: June 2026

---

## Executive Summary

The research across six documents covering China, Philippines, Indonesia, Vietnam,
and Singapore reveals one critical finding:

**The exact same pain points driving CargoIQ's SA market exist identically
in the China-to-SEA freight corridor — and the market is 40x larger.**

| Metric | SA Market | China-SEA Market |
|---|---|---|
| Market size | ~1,200 forwarders | ASEAN freight: $33.13B (2026) |
| Manual operations | High | 70% still manual |
| WhatsApp dependency | High | Universal across SMEs |
| Customs doc errors | SARS compliance | HS code errors, duty disputes |
| Willingness to pay | R5k-R25k/month | $5k-$15k/month |
| Core pain | CargoWise + SARS | No TMS, WhatsApp chaos |

---

## Pain Point Mapping — Direct Relevance to CargoIQ Tech

### Pain 1: Manual Data Entry (42 min/shipment) ← WE SOLVE THIS
**SA version:** Re-keying emails + PDFs into CargoWise manually.
**SEA version:** Identical. 70% of forwarders use Excel + WhatsApp + email.
Multiple suppliers in Yiwu, Shenzhen, Guangzhou → manual consolidation → errors.
**Our tech that solves it:** Document extraction pipeline + AI extraction service.
No changes needed — works on any freight document.

### Pain 2: Customs Documentation Errors ← WE SOLVE THIS
**SA version:** SARS requires 8-digit HS codes, Invoice/PL cross-reference,
SACU VAT formula, personal liability under S99(2).
**SEA version:** Philippines customs = 8-9 day average clearance.
Cause: HS code misclassification, under-declared values, multilingual docs.
1-digit HS error = 10-20% duty rate change.
**Our tech that solves it:** Compliance Shield modules 1+2+3 are universal.
Different regulatory rules, same technical architecture.

### Pain 3: WhatsApp-Based Operations ← WE SOLVE THIS
**SA version:** Freight instructions arrive on WhatsApp.
**SEA version:** WhatsApp + WeChat are the PRIMARY ops tools for China-to-SEA.
Drivers send slip photos via WhatsApp. Managers coordinate via groups.
**Our tech that solves it:** Evolution API integration already built.
WhatsApp webhook → document extraction → structured data. Zero changes needed.

### Pain 4: No Real-Time Shipment Visibility ← WE SOLVE THIS
**SA version:** Operators check CargoWise manually for status.
**SEA version:** Operations teams "fly blind" once cargo handed to ocean carriers.
35% of e-commerce buyers in Asia cite poor service due to tracking anxiety.
**Our tech that solves it:** Dashboard + status notifications already built.

### Pain 5: Customer Support Overload ← WE SOLVE THIS
**SA version:** "Where is my shipment" queries handled manually.
**SEA version:** Identical. "Where is my cargo?" consumes most support time.
Ninja Van reduced support overhead 40% with conversational AI.
**Our tech that solves it:** WhatsApp bot + automated status updates.

---

## What Is NOT Relevant to CargoIQ

The following items in the research describe DIFFERENT products:

| Item | Why it's irrelevant |
|---|---|
| Backhaul/empty trip optimizer | Fleet management product, different buyer |
| OR-Tools vehicle routing | Transport company product, not freight forwarding |
| TimescaleDB GPS telemetry | Fleet monitoring, not CargoIQ |
| PostGIS theft heatmaps | Mining intelligence product |
| FAISS load matching | Marketplace product, not document intelligence |
| Kafka streaming | Premature for current scale |
| Traccar GPS tracking | Different product entirely |

---

## The Technology Gap

**What CargoIQ's core pipeline solves universally:**
```
Email/WhatsApp/PDF arrives          ← Universal pain
        ↓
AI extracts structured fields       ← Universal pain
        ↓
Compliance validation               ← Needs localisation per country
        ↓
System integration                  ← CargoWise in SA, other TMS in SEA
```

**What needs localisation for SEA market:**
- Compliance Shield rules (Philippines BOC vs SARS)
- System integration (CargoWise → local TMS/ERP)
- Language support (Tagalog, Vietnamese, Bahasa)
- Pricing in USD/PHP/IDR vs ZAR

**Estimated localisation effort:** 6-8 weeks per country after SA PMF.

---

## Top 10 Tier 1 Leads (International — For Year 2)

Based on the lead scoring research:

1. **Senghor Logistics** (Shenzhen/Philippines) — Score: 100
   WhatsApp primary ops. DDP+CBM model. No TMS. Immediate buy.

2. **Fulfillmen** (China/Philippines) — Score: 92
   D2C DDP model. High volume. Pay-as-you-send structure.

3. **SINO Shipping** (Shenzhen/Shanghai) — Score: 84
   Traditional 3PL. Manual coordination. Consolidation errors.

4. **Vietnamese domestic SMEs** — Score: 82
   Basic digitisation. Excel + WhatsApp. Strong willingness to pay.

5. **Fast Logistics** (Philippines) — Score: 78
   Major regional player. High customs delay pain.

6. **QuadX** (Philippines) — Score: 74
   E-commerce focus. Routing bottleneck. Cost pressure.

7. **GoGo Xpress** (Philippines) — Score: 71
   Visibility gaps. Manual carrier audits.

8. **Indonesian SME forwarders** — Score: 68-75
   Multi-island complexity. WhatsApp operations. Excel primary tool.

9. **Philippine Span Asia Carrier** — Score: 68
   Inter-island maritime. Domestic rates exceed international freight.

10. **Leroy Basson / African maritime agents** — Score: 65
    WhatsApp-first. Maritime docs. Similar profile to SA leads.

---

## Revenue Opportunity

| Market | TAM | Realistic capture (Year 3) | Monthly Revenue |
|---|---|---|---|
| SA (current) | 1,200 forwarders | 50 clients @ R18k | R900k/month |
| Philippines | 3,000+ forwarders | 30 clients @ $8k | $240k/month |
| Indonesia | 5,000+ forwarders | 40 clients @ $6k | $240k/month |
| Vietnam | 3,000+ forwarders | 25 clients @ $5k | $125k/month |
| **Total Year 3** | | | **~$800k/month** |

---

## Decision: When to Expand Internationally

**Expansion trigger (not before this):**
- [ ] 20 paying SA clients
- [ ] R200,000+ MRR in SA
- [ ] Extraction accuracy ≥ 90%
- [ ] CargoWise execution stable (< 5% failure rate)
- [ ] First SA client ROI case study published

**Expansion sequence:**
1. Philippines first (English-speaking, CargoIQ pitch translates directly)
2. Indonesia second (largest market, needs Bahasa localisation)
3. Vietnam third (strong growth, French/US trade lane)
4. Singapore (enterprise sales, longer cycle, higher ACV)

**The product change for Philippines:**
Replace SARS Compliance Shield modules with Philippines BOC rules.
Same architecture, different rules engine. 3-4 weeks of work.

---

## Bottom Line

The international research validates three things:

1. **CargoIQ's core technology is globally applicable.**
   WhatsApp ingestion + AI extraction + compliance shield = universal solution
   to universal problems. The SA market is a proving ground, not a ceiling.

2. **The SEA market is larger and less competitive.**
   No CargoIQ equivalent exists in Philippines, Indonesia, or Vietnam.
   The tools they use are WhatsApp, Excel, and prayer.

3. **Expansion must wait for SA product-market fit.**
   The research identifies the opportunity clearly.
   Chasing it before SA traction guarantees failure in both markets.

Build CargoIQ to R1M MRR in SA. Then use that revenue, that case study,
and that proven product to enter Philippines with a single sales trip.
