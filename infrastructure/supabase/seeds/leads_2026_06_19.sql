-- ============================================================
-- CargoIQ Leads Seed — Deal Hunter Batch, 19 June 2026
-- ============================================================
-- Paste into Supabase SQL Editor and run once. Costs nothing —
-- this is plain data entry, no API calls involved.
--
-- CORRECTIONS MADE to the raw Base44 output before inserting:
--   1. "GPS" / "GPS geofencing" → "WhatsApp-verified timestamps"
--      (driver_checkin_service.py uses WhatsApp ARRIVED/DEPARTED
--      texts, not GPS hardware — this is accurate either way,
--      since the location field works for a DC or a border post)
--   2. "Beitbridge Fuel Theft Detector" claims REMOVED. CargoIQ
--      has no fuel-consumption or telematics integration — there
--      is nothing that can prove diesel theft from timestamps
--      alone. Replaced with the TMS Pre-Declaration Checker,
--      which is real, built, and addresses a confirmed SARS
--      regulation (mandatory from 1 June 2026).
--   3. Pharma-specific regulatory claims (Impilo) kept general —
--      CargoIQ has not verified SAHPRA/MCC-specific requirements,
--      so the DM doesn't claim expertise it doesn't have.

INSERT INTO leads (
  company_name, company_website, company_type, location,
  contact_name, contact_title, linkedin_url,
  primary_pain, pain_estimate_zar_low, pain_estimate_zar_high,
  cargoiq_modules, hook, dm_draft, status, source, notes
) VALUES

-- #1 — Cargo Partners International
('Cargo Partners International', NULL, '3pl_fleet', 'Johannesburg, Gauteng',
 'Thabo Mthembu', 'Managing Director', NULL,
 'Multi-client DC consolidation — unbilled DC detention time untracked across fleet',
 70000, 180000,
 ARRAY['driver_checkin','invoice_generator'],
 '15 years in JHB DC and consolidation work',
 'Hi Thabo,

You''ve built Cargo Partners into a solid mid-tier 3PL — 15 years in Johannesburg DC and consolidation work is no joke.

Here''s the one most 3PLs still miss: every truck sitting 4+ hours at a client DC waiting to offload gets written off as part of the service. For a multi-client operation like yours, that''s R70k-R180k/month in legitimate waiting time you''re eating instead of invoicing.

CargoIQ captures this via WhatsApp — your driver texts ARRIVED and DEPARTED, we calculate the billable hours and generate a numbered tax invoice automatically. No disputes, no manual logs, just cash back.

Free 7-day Shadow Audit on your last 10 DC trips. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a quick 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #2 — Trans Continental Logistics
('Trans Continental Logistics', NULL, '3pl_fleet', 'Durban, KwaZulu-Natal',
 'Coen Du Plessis', 'Director and Founder', NULL,
 'Durban port consolidation — Transnet storage penalties + untracked container dwell time',
 50000, 150000,
 ARRAY['compliance_shield','shadow_audit'],
 '20 years running consolidation out of Durban',
 'Hi Coen,

20 years running consolidation out of Durban means you''ve seen every iteration of the Transnet penalty game.

Here''s what I find with Durban consolidators: the free container storage window closes faster than anyone expects. That''s R14,169 per container in avoidable Transnet fees once you''re 2 days past free time — and on a busy consolidation operation, R50k-R150k/month walking out the door.

CargoIQ''s portal watcher checks container status every 30 minutes and flags containers trending toward the penalty deadline — so you move the container, not pay the fine.

Free 7-day Shadow Audit on your last 10 containers. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #3 — SafeFreight Solutions
('SafeFreight Solutions', NULL, '3pl_fleet', 'Kempton Park, Gauteng',
 'Derek Van Der Merwe', 'Owner and Operations Director', NULL,
 '20-truck DC fleet — unbilled detention + carrier invoice errors',
 40000, 120000,
 ARRAY['driver_checkin','carrier_invoice_auditor'],
 'Owner-operator who still drives some routes personally',
 'Hi Derek,

Owner-operators who still drive some of the routes have an advantage: you feel every hour of DC waiting time personally.

A single truck sitting 4+ hours at a DC waiting to offload costs you R1,200-R1,500 in idle time and fuel. On a 20-truck operation running regular DC runs, that adds up to R40k-R120k/month unaccounted for.

CargoIQ captures wait time via a simple WhatsApp text from the driver — ARRIVED, DEPARTED — and auto-generates the detention invoice with timestamps the client can''t dispute.

Free 7-day Shadow Audit on your last 10 DC trips. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a 15-minute call to set this up?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #4 — Beitbridge Customs Brokers (reseller / viral candidate)
('Beitbridge Customs Brokers', NULL, 'clearing_agent', 'Musina/Beitbridge',
 'Joseph Mbedu', 'Founder/Border Ops Manager', NULL,
 '100+ daily crossings — clients exposed to TMS non-compliance detention + undetected carrier overcharges',
 150000, 400000,
 ARRAY['tms_checker','compliance_shield','driver_checkin'],
 'Stationed at Beitbridge — sees border pain across entire client book daily. POTENTIAL RESELLER: could offer CargoIQ to every importer/fleet owner they clear for.',
 'Hi Joseph,

Stationed at Beitbridge, you see something most operators only hear about: cross-border compliance risk across 100+ truck crossings every single day.

From 1 June 2026, SARS requires every foreign-registered vehicle to be declared on the TMS system before crossing — no exceptions, including SACU countries. An undeclared truck risks 24-48 hour detention at the border, R15,000-R36,000 per incident.

CargoIQ''s TMS Pre-Declaration Checker flags this before the truck leaves the yard. For a brokerage your size clearing 100+ crossings, that''s real exposure across your entire client book.

Free 7-day Shadow Audit on your last 10 client crossings. If I don''t find R20k in recovered/avoided cost, you don''t pay a cent — and you walk away with a tool you could offer every importer and fleet owner you clear for.

Worth a 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026 — HIGH PRIORITY: reseller/partner angle, not just a client'),

-- #5 — Zambezi Freight Corporation (foreign — Zambia)
('Zambezi Freight Corporation', NULL, 'cross_border_trucker', 'Livingstone, Zambia',
 'Sylvester Kasoza', 'CEO / Founder', NULL,
 '120 trucks across 4 SADC corridors — TMS compliance exposure + untracked border wait time',
 150000, 600000,
 ARRAY['tms_checker','driver_checkin'],
 'Zambia-based, 120 trucks across Beitbridge/Chirundu/Kazungula/Groblersbrug. Foreign-plated fleet = directly subject to SARS TMS.',
 'Hi Sylvester,

Running 120+ trucks across four different border corridors into South Africa means every one of your vehicles is foreign-registered from SARS''s perspective.

From 1 June 2026, SARS requires ALL foreign-registered vehicles to be declared on the TMS system before crossing into or out of South Africa — no exceptions. An undeclared truck risks 24-48 hour detention, R15,000-R36,000 per incident. Across a 120-truck fleet running multiple corridors weekly, that compliance exposure compounds fast.

CargoIQ''s TMS Pre-Declaration Checker flags any shipment missing TMS confirmation before the vehicle leaves the yard. We also capture border wait time via a simple WhatsApp text from your drivers — useful evidence if you''re billing detention back to clients.

Free 7-day Shadow Audit on your last 20 cross-border trips. If I don''t find R50k in recovered/avoided cost, you don''t pay a cent.

Worth a 15-minute call next week to run the numbers on your regional book?',
 'new', 'deal_hunter', 'Batch 19 June 2026 — foreign entity, verify SA tax/banking arrangement before contract'),

-- #6 — Durban Container Depot Ltd
('Durban Container Depot Ltd', NULL, '3pl_fleet', 'Durban, KwaZulu-Natal',
 'Rajesh Patel', 'Director and Operations Lead', NULL,
 '25-year Durban consolidation — Transnet penalties + SARS hold costs + carrier overcharges',
 40000, 120000,
 ARRAY['compliance_shield','carrier_invoice_auditor','shadow_audit'],
 '25 years running a Durban container depot',
 'Hi Rajesh,

25 years running a Durban container depot means you''ve paid the Transnet storage penalty in every way possible.

The free storage window is invisible until it''s gone — R14,169 per container once you''re 2 days past free time. On a busy consolidation operation, that''s R40k-R120k/month in penalties you''re eating because nobody saw them coming.

CargoIQ checks container status every 30 minutes and alerts you before the penalty threshold hits — so you move the container instead of paying the fine. We also audit your carrier invoices against your negotiated rate cards to catch overcharges.

Free 7-day Shadow Audit on your last 10 container invoices. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #7 — JHB Wholesale Supplies (Electronics)
('JHB Wholesale Supplies', NULL, 'importer_wholesaler', 'Johannesburg (City Deep)',
 'Vikram Nair', 'Director — Imports & Logistics', NULL,
 'HS-code mismatches → SARS holds. Carrier surcharges on R2M+ book',
 50000, 120000,
 ARRAY['hs_classifier','compliance_shield','carrier_invoice_auditor'],
 'High-volume electronics importer through City Deep — HS code risk is constant',
 'Hi Vikram,

Running a high-volume electronics import operation through City Deep means you''re managing tariff and SARS risk on every single shipment. One HS-code mismatch = one 72-hour SARS hold = R36k-R72k in demurrage that eats your margin.

CargoIQ''s HS Code Classifier cross-checks your cargo descriptions against the SARS tariff schedule before submission — including a live-updated log of recent tariff amendments, so you''re not caught using an outdated rate. CarrierInvoice Auditor catches surcharge overcharges on your container freight separately.

Free 7-day Shadow Audit on your last 10 invoices. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a 15-minute call to run the numbers on your import book?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #8 — Coastal Freight Express
('Coastal Freight Express', NULL, '3pl_fleet', 'Cape Town, Western Cape',
 'Pierre Groenewald', 'Owner and Fleet Manager', NULL,
 'Cape Town DC + port exposure — unbilled detention + Transnet overstay fees',
 30000, 100000,
 ARRAY['driver_checkin','compliance_shield'],
 '15-truck fleet doing DC deliveries and port work in Cape Town',
 'Hi Pierre,

Running a 15-truck fleet doing DC deliveries and port work in Cape Town means you''re managing two pain points most operators deal with separately: DC waiting time and Transnet storage penalties.

Every truck sitting 4+ hours at a retail DC waiting to offload costs you R1,200-R1,500 in idle time. Separately, Transnet storage on overstayed containers runs R541-R3,533/day at Cape Town depending on terminal, and the free window expires faster than expected.

CargoIQ captures DC wait time via WhatsApp driver check-ins and auto-generates the invoice. Our portal watcher tracks container dwell time and flags penalty risk early. Together they usually recover R30k-R100k/month for Cape Town operations your size.

Free 7-day Shadow Audit on your last 10 DC trips and container records. If I don''t find R20k in recovered cash, you don''t pay a cent.

Worth a 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026'),

-- #9 — Impilo Distribution (Pharma)
('Impilo Distribution', NULL, 'importer_wholesaler', 'Midrand, Gauteng',
 'Dr. Thembi Mkhize', 'Operations Director', NULL,
 'Pharma — frequent SARS holds + HS-code mismatches on regulated goods. Carrier surcharges',
 30000, 80000,
 ARRAY['hs_classifier','compliance_shield'],
 'Pharma/health products importer through Johannesburg — compliance-heavy by nature',
 'Hi Dr. Thembi,

Running pharmaceutical and health product imports through Johannesburg means every shipment carries extra compliance weight.

HS-code mismatches on regulated goods can trigger extended SARS holds that delay your entire stock rotation. One 72-hour hold = R36k-R72k in demurrage, plus the cost of stock unavailability.

CargoIQ''s HS Code Classifier and Compliance Shield run a pre-submission check on every shipment to catch classification risk before SARS does. We don''t replace your regulatory compliance process — we add a second check specifically on the customs side, before declaration.

Free 7-day Shadow Audit on your last 10 shipments. If I don''t find R15k in cost recovery, you don''t pay a cent.

Worth a 15-minute call next week to see if this fits your workflow?',
 'new', 'deal_hunter', 'Batch 19 June 2026 — do not overclaim pharma-specific (SAHPRA/MCC) expertise, not verified'),

-- #10 — Motswana Cross-Border Services (foreign — Botswana)
('Motswana Cross-Border Services', NULL, 'cross_border_trucker', 'Gaborone, Botswana',
 'Keabo Moatshe', 'Managing Director', NULL,
 '30 trucks across 3 corridors — TMS compliance exposure + untracked border wait time',
 80000, 300000,
 ARRAY['tms_checker','driver_checkin'],
 'Botswana-based, SA-Botswana-Zimbabwe corridors. SACU member but TMS has NO exemptions for SACU plates.',
 'Hi Keabo,

Running 30+ trucks across the SA-Botswana-Zimbabwe corridors means every vehicle in your fleet is foreign-registered from a South African customs perspective — and that matters more than most operators realise.

From 1 June 2026, SARS requires ALL foreign-registered vehicles to be declared on the TMS system before crossing — including SACU member countries like Botswana. There is no exemption. An undeclared truck risks 24-48 hour detention, R15,000-R36,000 per incident.

CargoIQ''s TMS Pre-Declaration Checker flags any shipment missing TMS confirmation before the vehicle leaves the yard — so there are no surprises at Groblersbrug.

Free 7-day Shadow Audit on your last 15 cross-border trips. If I don''t find R20k in recovered/avoided cost, you don''t pay a cent.

Worth a 15-minute call next week?',
 'new', 'deal_hunter', 'Batch 19 June 2026 — foreign entity, verify SA tax/banking arrangement before contract');
