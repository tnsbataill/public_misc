# WS4: Unit Economics

**Summary**
1. Materials cost at retail: **about $430** for a slab or basement sub-slab system, **about $970** for a crawlspace sub-membrane system (~1,500 sf liner), and **about $875** for a combination system. Distributor pricing would lower these.
2. To reach the **$700 contribution-margin gate**, the minimum prices are about **$1,610 (slab/basement), $2,160 (crawl), and $2,070 (combination)**. At **$1,200, no system type passes.**
3. That puts the owner in the **upper-middle of the local range**. It is viable only if the speed and documentation edge supports it. Otherwise the plan has to cut electrician cost or acquisition cost (the two biggest non-material lines).
4. A blended mix (40% slab/basement at $1,600, 40% crawl at $2,200, 20% combination at $2,500) gives an average ticket of **$2,020 and $797 contribution margin**, with about 10 hours of labor per job.
5. Fixed costs are about **$930/month**, so breakeven is about **1.2 jobs/month**. About **8.7 jobs/month** yields about $6,000/month owner profit. **Startup capital is about $9K in the base case** (range $6–13K, estimated).

> The model lives in [`ws4_model.py`](ws4_model.py) and writes [`ws4-unit-economics.csv`](ws4-unit-economics.csv). Change an input there and re-run it. Prices come from **web-search excerpts** of the linked retailer listings (direct loads were blocked). Listings change, so re-check them before buying.

---

## 1. Bill of materials (per system type)

| Item | Unit price | Label | Source | SSD | Crawl | Combo |
|---|---|---|---|---|---|---|
| Fan: RadonAway RP145c | $152.95 | S | [Walmart](https://www.walmart.com/ip/RadonAway-RP145c-Radon-Mitigation-Fan-Pump/285067290) (Lowe's $198.19: [link](https://www.lowes.com/pd/RadonAway-C-Series-Rp145c-Radon-Fan/1001429744)) | 1 | | |
| Fan: Festa AMG Eagle | $222.00 | S | [Walmart / Lowe's listings](https://www.walmart.com/ip/Festa-Radon-AMG-Eagle-Radon-Fan-Quiet-and-Energy-Efficient-241-CFM-Radon-Mitigation-System-Inline-Fan-3/1505759532) | | 1 | |
| Fan: Festa AMG Eagle Extreme | $267.00 | S | [Lowe's](https://www.lowes.com/pd/Festa-AMG-Radon-Fans-AMG-Eagle-Extreme-Centrifugal-Radon-Fan/5014713977) | | | 1 |
| *(Alt.)* RadonAway GP501 high-suction fan for tight soils | ~$305–319 | S | [Walmart kit](https://www.walmart.com/ip/RadonAway-GP501-Radon-Mitigation-Fan-3x3-Install-Kit/179140245) | swap-in | | |
| PVC 3″×10′ Sch 40 DWV | $18.24 | S | [Home Depot (Charlotte Pipe)](https://www.homedepot.com/b/Plumbing-Pipe-Fittings-Pipe-PVC-Pipe-PVC-Schedule-40-Pipe/N-5yc1vZbueo) | 4 (E) | 4 (E) | 6 (E) |
| Fittings, rubber couplers, hangers, rain cap | $60–80 | E | | 1 | 1 | 1 |
| U-tube manometer + system labels (Fantech FRIKSL) | $36.14 | S | [SupplyHouse](https://www.supplyhouse.com/Fantech-FRIKSL-Radon-Mitigation-U-Tube-Manometer-System-Labels) (manometer alone $8.50–14.56: [RadonSupplies](https://radonsupplies.com/collections/ma)) | 1 | 1 | 1 |
| Sikaflex-1a polyurethane sealant, 10.1 oz | $8.47 | S | [Home Depot listing via search](https://www.homedepot.com/p/Sika-10-1-fl-oz-Sikaflex-All-Purpose-Non-Sag-Construction-Sealant-Polyurethane-in-White-7116045/300934496); 24-case $152.99 ([Best Materials](https://www.bestmaterials.com/detail.aspx?ID=27129)) | 3 (E) | | 3 (E) |
| 12-mil crawlspace liner, 12′×100′ (1,200 sf) | $307.99 | S | [Crawlspace Depot](https://crawlspacedepot.com/12-mil-economy-crawl-space-liner-wb-12-x-100-roll/) (20-mil: $559.99, [link](https://crawlspacedepot.com/20-mil-reinforced-crawl-space-liner-12-x-100-roll/)) | | 1,500 sf | 600 sf |
| Seam tape, mechanical fasteners, termination bar | $80 | E | | | 1 | 1 |
| Perforated collection pipe under the liner | $30 | E | | | 1 | 1 |
| Electrical materials (weatherproof disconnect, whip) | $40 | E | | 1 | 1 | 1 |
| Misc. consumables (primer, cement, fasteners, backer rod) | $25–35 | E | | 1 | 1 | 1 |
| Post-mitigation test (AirChek short-term, lab included) | $17.99 | S | [Walmart](https://www.walmart.com/ip/AirChek-Short-Term-Charcoal-Radon-Test-Kit/843078229) (bulk $14.69) | 1 | 1 | 1 |
| **Materials total** | | | | **$430** | **$969** | **$875** |

## 2. Labor hours

| System | On-site hours (incl. PFE diagnostic) | + travel and admin | Total | Label | Basis |
|---|---|---|---|---|---|
| SSD (slab/basement) | 6.0 | 1.5 | 7.5 | E | Published ranges: 3–6 h and 4–8 h for a typical install ([Radon 1 timeline](https://radon1.com/how-long-radon-mitigation-takes/); [Michigan Radon Control](https://michiganradoncontrol.com/how-long-does-a-radon-mitigation-system-installation-take/)) |
| Crawlspace sub-membrane | 9.0 | 1.5 | 10.5 | E | Crawlspace jobs 6–12 h because of the liner work ([RadonBase guide](https://www.radonbase.com/blog/diy-radon-mitigation-installation-guide)) |
| Combination | 12.0 | 1.5 | 13.5 | E | Crawlspaces, split-levels, and second suction points "can stretch to two days" (same sources) |
| Passive-stack activation | 2.5 | 1.5 | 4.0 | E | Fan and electrical only |

Hours assume a **solo installer**. Crawlspace liner work goes much faster with a helper. A $25/h helper for 5 hours costs $125 and isn't modeled.

## 3. Per-job variable costs other than materials (all E)

| Line | Value | Why |
|---|---|---|
| Card processing | 2.9% of price | Typical processor rate |
| Vehicle (fuel and wear) | $30 | 30–60 mi round trip |
| Electrical permit | $60 | No fee schedule found (WS1 §3) |
| Electrician subcontract, blended | $150 | About 50% of jobs need hardwiring at about $300. **This is the largest controllable line** |
| Warranty reserve | $40 | Fan failures inside the workmanship warranty |
| Customer acquisition cost | $150 | Mix of referral (low) and paid search (high) |

## 4. Contribution margin by price point (before the owner's labor)

| System | $1,200 | $1,800 | $2,500 | Price needed for $700 CM |
|---|---|---|---|---|
| SSD (slab/basement) | **$305** ✗ | $887 ✓ | $1,567 ✓ | **$1,607** |
| Crawlspace sub-membrane | **−$234** ✗ | $349 ✗ | $1,028 ✓ | **$2,162** |
| Combination | **−$140** ✗ | $443 ✗ | $1,123 ✓ | **$2,065** |
| Passive-stack activation | $443 ✗ | $1,026 ✓ | $1,705 ✓ | $1,465 |

CM per labor hour at $1,800 is $118/h for SSD and $33/h for crawl. At $2,500 it is $209/h for SSD and $98/h for crawl. Full rows are in the CSV.

**Sensitivities (from the model):**
- If the owner handles electrical in-house where it's legal (Blount with an LLE, or plug-in fans), CM rises **$150/job**, and the SSD gate price falls to about $1,450.
- Referral-only acquisition (CAC $50 instead of $150) adds **$100/job**.
- Contractor pricing on fans is typically below retail. That's unverified, since distributor price lists are behind accounts.
- A realistic activation price of about $900 yields only about **$150 CM** under base assumptions, because permits, electrician, and CAC swamp the low materials cost. Activation only works if the electrical is done in-house.

**Implication for the gate:** "≥$700 CM at a competitive price" holds for SSD at about $1,600, which is inside the local $1,000–2,000 band but above its $1,000–1,500 center. It holds for crawl and combination only at $2,100–2,200, which is within Radon 1's published $2,000–4,000 and the third-party $1,500–3,000 crawl range. **The gate passes conditionally.** It depends on pricing crawlspace work at about $2,200 and on keeping electrician and acquisition costs down.

## 5. Fixed monthly costs (E unless noted)

| Line | $/mo |
|---|---|
| General liability ($2,000/yr; sourced range $500–2,500) | 167 |
| Pollution / E&O ($1,000/yr) | 83 |
| Software stack (WS6 recommendation) | 170 |
| LLC annual report ($300/yr, S) | 25 |
| NRPP renewal + CE (($300 + $200) / 24 mo) | 21 |
| Fixed marketing (GBP photos, print, sponsorships) | 300 |
| Tool depreciation ($4,000 / 36 mo) | 111 |
| Vehicle insurance increment (business use) | 50 |
| **Total** | **≈ $927** |

## 6. Breakeven

| Target | Jobs / month (blended $797 CM) |
|---|---|
| Cover fixed costs | **1.2** |
| + $2,000/mo owner profit | 3.7 |
| + $4,000/mo | 6.2 |
| + $6,000/mo | 8.7 |

At 8 jobs a month and about 10 hours each, the owner works about **80 hours a month**. With a full-time day job, that means evenings and weekends, which conflicts with the "speed inside the contingency window" promise. See the risk note in the [README](README.md).

## 7. Startup capital

| Item | Cost | Label | Source |
|---|---|---|---|
| Certification, LLC, licenses, first-year insurance | $1,600–5,900 (base ≈ $3,500) | S/E | WS1 §5 |
| 5″ SDS-max core bit | $232–374 | S | [Bosch via Home Depot](https://www.homedepot.com/b/Tools-Power-Tool-Accessories-Drill-Bits-Coring-Drill-Bits/SDS-Max/N-5yc1vZc7mqZ1z18032); [Drill Bit Warehouse radon bit](https://www.drillbitwarehouse.com/product/5-dry-diamond-carbide-core-bit/) |
| SDS-max rotary hammer | $600–900 | E | not searched |
| Digital micromanometer (PFE) | $445 (Infiltec DM1) – $635 (Dwyer kit incl. smoke pen) | S | [Infiltec](https://www.infiltec.com/inf-dm1s.htm); [Radon PDS Dwyer kit](https://radonpds.com/shop/radon-tools-and-training/tools-tools-and-training/dwyer-diagnostic-kit/) |
| Continuous radon monitor (optional; for own post-tests and diagnostics) | $895–995 (SunRadon 1028-XP) | S | [Tool Experts](https://www.toolexperts.com/sunradon-continuous-radon-monitor-1028-xp) |
| HEPA shop vac, ladders, hand and power tools, silica PPE | $1,000–1,500 | E | |
| Starter inventory (3 fans + pipe) | $600 | E (from §1 prices) | |
| Website, logo, vehicle decal | $300–1,500 | E | |
| Launch marketing | $1,000 | E | |
| Vehicle | $0 (assumes the owner's truck) + ladder rack $300 | E | |
| **Total** | **≈ $6,100–12,700 (base ≈ $9,100)** excluding the CRM; **+$900** with it | | |
