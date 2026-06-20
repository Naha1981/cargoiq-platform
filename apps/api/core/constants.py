"""
CargoIQ — Verified South African Logistics Constants
======================================================
All figures below are sourced from:
  - Maersk revised import demurrage tariffs effective 15 April 2026
  - Transnet National Ports Authority published tariffs 2026
  - Global freight audit industry reports (multiple sources)
  - SARS Customs & Excise Act enforcement data 2023/24

Update this file — not individual service files — whenever tariffs change.
"""
from typing import Optional

# ── Durban port storage (Pier 1, Pier 2, Point) ─────────────
# Free time: 3 days from container discharge
DURBAN_FREE_DAYS = 3

# Standard dry container (per day, ZAR)
DURBAN_20FT_DAY4      = 2_698.0
DURBAN_20FT_DAY5_PLUS = 4_391.0
DURBAN_40FT_DAY4      = 5_396.0
DURBAN_40FT_DAY5_PLUS = 8_773.0

# Convenience: 2-day penalty (Day 4 + Day 5) for a 40ft — the
# "R14,169 Durban bleed" figure used in sales material
DURBAN_40FT_TWO_DAY_PENALTY = DURBAN_40FT_DAY4 + DURBAN_40FT_DAY5_PLUS  # = 14_169

# Reefer container (per day, ZAR)
DURBAN_20FT_REEFER_DAY4_5  = 4_184.0
DURBAN_20FT_REEFER_DAY6_PLUS = 8_378.0
DURBAN_40FT_REEFER_DAY4_5  = 6_278.0
DURBAN_40FT_REEFER_DAY6_PLUS = 12_567.0

# Reefer peak season (1 May – 31 Oct Durban): free time reduced to 2 days
DURBAN_REEFER_PEAK_FREE_DAYS = 2

# Hazardous / IMO cargo: 0 free days, charges from discharge
DURBAN_40FT_IMO_DAY1_PLUS = 8_773.0
DURBAN_20FT_IMO_DAY1_PLUS = 4_391.0


# ── Cape Town port storage (CTCT and MPT) ───────────────────
# Free time: 4 days from container discharge
CAPE_TOWN_FREE_DAYS = 4

# Standard dry container (per day, ZAR)
CAPE_TOWN_20FT_DAY5_6        = 272.0
CAPE_TOWN_40FT_DAY5_6        = 541.0
CAPE_TOWN_20FT_DAY7_STANDARD  = 272.0
CAPE_TOWN_40FT_DAY7_STANDARD  = 541.0
CAPE_TOWN_20FT_DAY7_MPT      = 1_771.0   # Multipurpose Terminal — 550% jump
CAPE_TOWN_40FT_DAY7_MPT      = 3_533.0

# Reefer peak season (15 Nov – 31 Mar Cape Town)
CAPE_TOWN_REEFER_PEAK_FREE_DAYS = 2


# ── Carrier invoice billing errors ──────────────────────────
# Source: multiple global freight audit industry reports
FREIGHT_INVOICE_ERROR_RATE        = 0.25   # 25% of all invoices contain an error
FREIGHT_AUDIT_RECOVERY_RATE_LOW   = 0.06   # 6% of freight spend recovered by auditors
FREIGHT_AUDIT_RECOVERY_RATE_HIGH  = 0.08   # 8% of freight spend recovered
FREIGHT_INVOICE_MANUAL_COST_ZAR   = 200.0  # ~$11 per invoice to process manually

# Conservative rate used in Shadow Audit and Sales Calculator
FREIGHT_AUDIT_CONSERVATIVE_RATE   = 0.04   # 4% (below industry 6-8% mean)


# ── Truck detention (waiting time) ──────────────────────────
# Source: US industry standard converted to ZAR; SA practitioners
# report similar rates (R350–R1,800/hr depending on fleet size)
DETENTION_FREE_HOURS              = 2.0    # Standard 2-hour free window
DETENTION_RATE_PER_HOUR_ZAR_LOW   = 450.0  # R450/hr (~$25)
DETENTION_RATE_PER_HOUR_ZAR_MID   = 1_100.0  # R1,100/hr — mid-range default
DETENTION_RATE_PER_HOUR_ZAR_HIGH  = 1_800.0  # R1,800/hr (~$100) for large trucks

# Only 3% of drivers receive 90%+ of their detention claims (lack of GPS proof)
DETENTION_BILLING_RATE            = 0.10   # Conservative: 10% actually billed
DETENTION_UNBILLED_RATE           = 0.90   # 90% goes unbilled

# Average wait time at SA retail DCs / warehouses (industry estimate)
DETENTION_AVG_WAIT_HOURS          = 4.0


# ── Empty backhaul ───────────────────────────────────────────
# Source: SA regional trucking industry data
EMPTY_MILE_RATE_LOW   = 0.15   # 15% of total trucking mileage is empty
EMPTY_MILE_RATE_HIGH  = 0.20   # 20% upper estimate
ROAD_LEG_COST_ZAR     = 25_000.0  # Durban–JHB road leg cost estimate


# ── Beitbridge border delay ─────────────────────────────────
# Source: North-South Corridor efficiency studies
BEITBRIDGE_STATUS_QUO_DELAY_HOURS = 18.0
BEITBRIDGE_DIESEL_THEFT_LITRES    = 600.0  # Per incident (organised syndicates)
DIESEL_PRICE_GAUTENG_APR2026      = 26.11  # R/litre, April 2026 Gauteng price
BEITBRIDGE_DIESEL_LOSS_ZAR        = BEITBRIDGE_DIESEL_THEFT_LITRES * DIESEL_PRICE_GAUTENG_APR2026
# = R15,666 per truck per incident


# ── SARS enforcement context ─────────────────────────────────
# Source: SARS Annual Report 2023/24
SARS_ADMIN_PENALTY_DEBT_TOTAL_ZAR = 22_600_000_000.0  # R22.6B outstanding
SARS_SEIZURES_2324_COUNT          = 6_980
SARS_SEIZURES_2324_VALUE_ZAR      = 6_700_000_000.0   # R6.7B seized
SARS_CRIMINAL_PROSECUTION_SUCCESS = 0.9529             # 95.29% success rate


# ── Composite: R217,340 monthly leakage profile ─────────────
# Basis: mid-size Johannesburg importer, 15 × 40ft containers/month
# Used in the Shadow Audit Calculator and sales collateral
LEAKAGE_PROFILE_CONTAINERS        = 15
LEAKAGE_PROFILE_FREIGHT_SPEND     = 1_500_000.0  # ~R100k per container/month

LEAKAGE_UNBILLED_DETENTION        = 59_400.0   # 15 × 4hrs × R1,100 × 90% unbilled
LEAKAGE_CARRIER_OVERCHARGES       = 60_000.0   # R1.5M × 4% conservative error rate
LEAKAGE_SARS_STORAGE_ONE_HOLD     = 22_940.0   # 1 container, 3 days past free time
LEAKAGE_EMPTY_BACKHAULS           = 75_000.0   # 15 × R25k × 20%
LEAKAGE_TOTAL_MONTHLY             = 217_340.0  # = sum of above


# ── Known SARS tariff amendments ─────────────────────────────
# A running log of confirmed SARS tariff schedule changes. The
# HS Classifier checks cargo descriptions against this list and
# flags a warning if the commodity falls into a recently-amended
# category — these are exactly the classifications where an
# importer's old HS code mapping is now wrong and risks a
# retroactive penalty when SARS catches the mismatch.
#
# Update this list whenever SARS publishes a tariff amendment
# (sars.gov.za/legal-counsel/preparation-of-legislation/tariff-amendments).
# This is a manually-curated log, not a live feed — reliability
# over fragile automation for a solo founder.

KNOWN_TARIFF_AMENDMENTS = [
    {
        "effective_date": "2026-06-12",
        "category":       "steel",
        "keywords":       ["steel", "flat-rolled", "hot-rolled", "cold-rolled", "steel coil", "steel sheet"],
        "change":         "Safeguard duty introduced — 15%+ depending on product, 3-year protection period",
        "hs_chapters":     ["72", "73"],
        "source":         "SARS.gov.za tariff amendment, 12 June 2026",
    },
    {
        "effective_date": "2026-06-12",
        "category":       "polyethylene",
        "keywords":       ["polyethylene", "PE film", "PE bags", "PE containers", "plastic film", "plastic packaging"],
        "change":         "Anti-dumping duty structure changed on polyethylene products",
        "hs_chapters":     ["39"],
        "source":         "SARS.gov.za tariff amendment, 12 June 2026",
    },
    {
        "effective_date": "2026-06-12",
        "category":       "machinery",
        "keywords":       ["industrial machinery", "industrial equipment", "machinery parts"],
        "change":         "Tariff relief — select industrial machinery reduced from 20% to 15%",
        "hs_chapters":     ["84", "85"],
        "source":         "SARS.gov.za tariff amendment, 12 June 2026",
    },
]


def check_tariff_amendment_match(cargo_description: str, hs_chapter: str = "") -> Optional[dict]:
    """
    Check whether a cargo description or HS chapter matches a
    recently-amended SARS tariff category. Used by the HS
    Classifier to add a time-sensitive warning when relevant.
    """
    desc_lower = (cargo_description or "").lower()
    for amendment in KNOWN_TARIFF_AMENDMENTS:
        keyword_match = any(kw in desc_lower for kw in amendment["keywords"])
        chapter_match = hs_chapter and hs_chapter[:2] in amendment["hs_chapters"]
        if keyword_match or chapter_match:
            return amendment
    return None
