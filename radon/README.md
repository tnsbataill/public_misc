# Radon Mitigation: Research Pack (WS1–WS6)

**Summary**
1. **Licensing (WS1): clear and cheap.** No TN radon license was found (EPA's credentialing list omits TN; TDEC only recommends certification). NRPP Radon Mitigation Specialist costs about $800–975. Base-case compliance is about $3.5K and 6–8 weeks. **Open items:** a written TDEC confirmation, and who may wire fans in Knox.
2. **Market (WS2): about 2,000 jobs/yr in the base case** across five counties (range 760–4,500). 8 jobs/month is about 5% share, and the 2026 sales-growth forecast alone adds about 140 jobs/yr.
3. **Competition (WS3): about 10 active firms,** mostly without published prices. Rn86 already claims PFE-driven, standards-based design, so the edge has to be *speed plus visible documentation plus published pricing*.
4. **Economics (WS4): $700 contribution margin needs about $1,600 (slab/basement) or about $2,150 (crawl or combination).** At $1,200, no system type passes. Blended CM is about $800. Breakeven is about 1.2 jobs/month.
5. **Verdict: conditional GO on paper,** pending (a) TDEC and Knox electrical confirmation, (b) inspector-reported radon attach rates, (c) employer policy, and (d) whether evenings and weekends can deliver the 2-hour-quote / 5-day-install promise.

| File | Workstream |
|---|---|
| [ws1-regulatory.md](ws1-regulatory.md) | Regulatory and licensing |
| [ws2-market-sizing.md](ws2-market-sizing.md) | Market sizing |
| [ws3-competitors.md](ws3-competitors.md) | Competitive teardown |
| [ws4-unit-economics.md](ws4-unit-economics.md) · [ws4-unit-economics.csv](ws4-unit-economics.csv) · [ws4_model.py](ws4_model.py) | Unit economics |
| [ws5-go-to-market.md](ws5-go-to-market.md) | Go-to-market |
| [ws6-ai-ops-stack.md](ws6-ai-ops-stack.md) | AI operations stack |

## Decision gate scorecard (brief §5)

| Gate | Result | Evidence |
|---|---|---|
| Licensing path ≤ ~3 months and ≤ $5K | **Pass (base case)** | About 6–8 weeks and about $3.5K (range $1.6–5.9K). WS1 §5 |
| Base case supports ≥8 jobs/mo within 12 months without displacing incumbents | **Pass, thin** | 96/yr is 4.7% of the base market, roughly equal to 2026 market growth. The low case fails (12.6% share). WS2 §3 |
| CM ≥ $700/job at a competitive price | **Conditional** | Slab/basement passes at about $1,600 (inside the local $800–2,000 band). Crawl and combination need about $2,100–2,200 (inside Radon 1's published $2,000–4,000). Fails at $1,200. WS4 §4 |
| Employer policy allows it | **Owner to confirm** | Not researched, per the brief |

## Risks the brief didn't list
1. **Capacity versus the speed promise.** 8 jobs/month is about 80 labor hours plus quoting. With a full-time job, installs land on weekends, which can break "install within 5 business days." Consider a part-time helper, or cap volume at the rate that can actually be delivered.
2. **Electrical in Knox.** If hardwired fans need a licensed electrician (WS1 §3), expect about $150–300 per job and a scheduling dependency.
3. **Crawlspace-heavy mix.** East TN crawlspaces cost more in materials and time. Underpricing them is the fastest way to miss the CM gate.
4. **Referral economics.** Inspectors can't be paid, and paying agents is legally unclear. The referral channel has to be won on service, not fees.

## Method and limits
- **Direct page loads were blocked** by this environment's network policy (tn.gov, epa.gov, nrpp.info, retailers, and others). Every fact was taken from **web-search result excerpts** of the cited URL. The citations point at primary sources wherever one exists, but the key rows (WS1 table, WS4 prices) should be spot-checked in a browser before any money is spent. To let a future agent open pages directly, widen the environment's network access.
- Everything is labeled **sourced (S)** or **estimated (E)**. Conflicts are marked ⚠ and left unresolved.
- No businesses or people were contacted, nothing was bought, and no accounts were created.

*Research date: 2026-09-29.*
