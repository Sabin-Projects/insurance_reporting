# Assumptions Log

The freMTPL data has no premiums, dates or expenses. These were simulated
with the rules below. All values are set in `src/config.py`, and the random
seed (42) makes every run produce identical results.

| # | Area | Assumption | Reason |
|---|---|---|---|
| 1 | Systems | freMTPL2freq = underwriting system; freMTPL2sev = claims system | Public data has no real multi-system extract |
| 2 | Policy type | fuel_type (Diesel / Regular) used as policy type | Clean two-way product split |
| 3 | Geography | region used as geographic segment | Closest equivalent to a state split |
| 4 | Effective dates | Random day from Jan 1, 2024 to Dec 31, 2025 | Creates 24 months of written business |
| 5 | Policy term | exposure (capped at 1.0) × 365 days | Exposure is the fraction of a year in force |
| 6 | Annual premium | €375 × bonus-malus/100 × area factor × fuel factor × power factor | Base rate set for a ~70% expected loss ratio |
| 7 | Area factors | A 0.85, B 0.95, C 1.00, D 1.10, E 1.20, F 1.30 | Urban areas have more accidents |
| 8 | Fuel factors | Regular 1.00, Diesel 1.05 | Diesel cars are typically driven more |
| 9 | Power factor | +3% per power level above 6 | More powerful cars cost more to insure |
| 10 | Written premium | annual premium × capped exposure | Premium covers only the period in force |
| 11 | Earned premium | Written premium earned evenly per day in force | Standard pro rata premium recognition |
| 12 | Commission | 15% of written premium | Typical agent commission |
| 13 | Admin expense | €20 per policy | Cost to issue and service a policy |
| 14 | Accident date | Random day within the policy period | No dates in source |
| 15 | Report date | Accident date + 0 to 45 days | Creates realistic reporting lag |
| 16 | Exposure cap | Exposure > 1 capped at 1.0 | Data quality decision PC-02 |
| 17 | Claims-complete | Policy ID > 1,000,000 | Data quality decision PC-05 |
| 18 | GL premium | Booked in the month the policy is written | Standard written premium accounting |
| 19 | GL claims | Booked in the month the claim is reported | Accounting can only book known claims |
| 20 | GL errors | Planted: 20 cutoff, 2 duplicate, 3 missing, 2 decimal (×10) | Tests that the reconciliation finds known errors |
| 21 | Orphan claims | Excluded from claims vs GL matching (no dates); reported in R3 | No policy means no simulated dates |
| 22 | Large loss | Claim ≥ €100,000 | Separates volatile large claims from everyday claims |
| 23 | 2025 budget | 2024 actual × (1 + 2% policies) × (1 + 3% average premium); loss ratio 65%; expense ratio 30% | Simple plan to measure variance against |