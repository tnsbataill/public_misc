"""WS4 unit-economics model. Every input is labeled S (sourced) or E (estimated)
in ws4-unit-economics.md. Run: python3 ws4_model.py  -> prints tables, writes CSV."""
import csv, os

# Bill of materials per system type (USD). Retail prices; contractor/distributor pricing is usually lower.
BOM = {
    "SSD (basement/slab)": {
        "fan": 152.95,            # S: RadonAway RP145c, Walmart
        "pvc_pipe": 4 * 18.24,    # S price (Charlotte 3in x 10ft Sch40 DWV, Home Depot); E qty 4 sticks
        "fittings_hangers_cap": 60.0,   # E
        "manometer_labels": 36.14,      # S: Fantech FRIKSL, SupplyHouse
        "sealant": 3 * 8.47,            # S price (Sikaflex-1a, Home Depot); E qty 3
        "electrical_materials": 40.0,   # E
        "misc_consumables": 25.0,       # E
        "post_test_kit": 17.99,         # S: AirChek short-term kit, Walmart
    },
    "Crawlspace sub-membrane (~1,500 sf liner)": {
        "fan": 222.00,                  # S: Festa AMG Eagle
        "membrane_12mil": 307.99 * 1500 / 1200,  # S price (Crawlspace Depot 12mil 12x100); E area
        "seam_tape_fasteners": 80.0,    # E
        "perforated_pipe": 30.0,        # E
        "pvc_pipe": 4 * 18.24,
        "fittings_hangers_cap": 60.0,
        "manometer_labels": 36.14,
        "electrical_materials": 40.0,
        "misc_consumables": 25.0,
        "post_test_kit": 17.99,
    },
    "Combination (slab + ~600 sf crawl)": {
        "fan": 267.00,                  # S: Festa AMG Eagle Extreme
        "membrane_12mil": 307.99 * 600 / 1200,
        "seam_tape_fasteners": 80.0,
        "perforated_pipe": 30.0,
        "pvc_pipe": 6 * 18.24,
        "fittings_hangers_cap": 80.0,
        "manometer_labels": 36.14,
        "sealant": 3 * 8.47,
        "electrical_materials": 40.0,
        "misc_consumables": 35.0,
        "post_test_kit": 17.99,
    },
    "Passive-stack activation (fan only)": {
        "fan": 152.95,
        "fittings_hangers_cap": 30.0,
        "manometer_labels": 36.14,
        "electrical_materials": 40.0,
        "misc_consumables": 15.0,
        "post_test_kit": 17.99,
    },
}

# On-site labor hours incl. PFE diagnostics, excl. travel (E, informed by published 3-12 h ranges)
HOURS = {
    "SSD (basement/slab)": 6.0,
    "Crawlspace sub-membrane (~1,500 sf liner)": 9.0,
    "Combination (slab + ~600 sf crawl)": 12.0,
    "Passive-stack activation (fan only)": 2.5,
}
TRAVEL_ADMIN_HOURS = 1.5          # E

# Variable non-material costs per job
PROCESSING_RATE = 0.029           # E: typical card processing
VEHICLE = 30.0                    # E: fuel + wear per job
ELECTRICAL_PERMIT = 60.0          # E: no fee schedule seen
ELECTRICIAN_BLENDED = 150.0       # E: ~50% of jobs subbed at ~$300
WARRANTY_RESERVE = 40.0           # E
CAC = 150.0                       # E: blended acquisition cost per job

PRICES = [1200, 1800, 2500]
GATE = 700

def materials(t):
    return sum(BOM[t].values())

def cm(t, price):
    return (price - materials(t) - price * PROCESSING_RATE - VEHICLE - ELECTRICAL_PERMIT
            - ELECTRICIAN_BLENDED - WARRANTY_RESERVE - CAC)

def price_for_cm(t, target):
    fixed = materials(t) + VEHICLE + ELECTRICAL_PERMIT + ELECTRICIAN_BLENDED + WARRANTY_RESERVE + CAC
    return (target + fixed) / (1 - PROCESSING_RATE)

rows = []
for t in BOM:
    for p in PRICES + [round(price_for_cm(t, GATE))]:
        c = cm(t, p)
        hrs = HOURS[t] + TRAVEL_ADMIN_HOURS
        rows.append({
            "system_type": t, "price": p, "materials": round(materials(t)),
            "other_variable": round(p - materials(t) - c), "contribution_margin": round(c),
            "total_hours": hrs, "cm_per_hour": round(c / hrs), "meets_700_gate": c >= GATE - 0.5,
        })

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ws4-unit-economics.csv")
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows)

for t in BOM:
    print(f"{t}: materials ${materials(t):.0f}; price for $700 CM ${price_for_cm(t, GATE):.0f}")
for r in rows:
    print(r)

# Fixed monthly costs (E unless noted)
FIXED = {
    "general_liability_insurance": 2000 / 12,   # S range $500-2,500/yr; E point
    "pollution_or_E&O_insurance": 1000 / 12,    # E
    "software_stack": 170,                      # from WS6 recommended stack
    "llc_annual_report": 300 / 12,              # S
    "nrpp_renewal_and_CE": (300 + 200) / 24,    # S fee; E CE cost
    "marketing_fixed": 300,                     # E
    "tool_depreciation_36mo": 4000 / 36,        # E
    "vehicle_insurance_increment": 50,          # E
}
fixed = sum(FIXED.values())
print(f"\nFixed monthly: ${fixed:.0f}")
mix = {"SSD (basement/slab)": (0.40, 1600), "Crawlspace sub-membrane (~1,500 sf liner)": (0.40, 2200),
       "Combination (slab + ~600 sf crawl)": (0.20, 2500)}
blended_cm = sum(w * cm(t, p) for t, (w, p) in mix.items())
blended_price = sum(w * p for t, (w, p) in mix.items())
blended_hours = sum(w * (HOURS[t] + TRAVEL_ADMIN_HOURS) for t, (w, p) in mix.items())
print(f"Blended price ${blended_price:.0f}, blended CM ${blended_cm:.0f}, hours {blended_hours:.1f}")
print(f"Breakeven jobs/month (fixed only): {fixed / blended_cm:.2f}")
for income in (2000, 4000, 6000):
    print(f"Jobs/month for ${income}/mo owner profit: {(fixed + income) / blended_cm:.1f}")
