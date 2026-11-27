# Data Quality Log

Results of `src/02_validate.py`: what each rule found, what was investigated,
and what was decided. Severity: High = would misstate a reported number;
Medium = needs a documented treatment; Low = cosmetic or explained.

## Summary

17 rules run: 4 passed, 13 failed.

| Rule | Source | Severity | Failed | Status |
|---|---|---|---|---|
| SP-01 | Schedule P | Low | 3,510 | Explained: rounding |
| SP-02 | Schedule P | High | 0 | Pass |
| SP-03 | Schedule P | High | 724 | Investigated |
| SP-04 | Schedule P | Medium | 2,127 | Open |
| SP-05 | Schedule P | High | 840 | Open |
| SP-06 | Schedule P | Medium | 107 | Open |
| IA-01 | Iowa | Medium | 124 | Open |
| IA-02 | Iowa | Medium | 104 | Open |
| IA-03 | Iowa | Low | 3,708 | Fix: standardize names |
| IA-04 | Iowa | Low | 86 | Accepted |
| PC-01 | Policies | High | 0 | Pass |
| PC-02 | Policies | Medium | 1,224 | Investigated |
| PC-03 | Policies | Medium | 0 | Pass |
| PC-04 | Claims | High | 195 | Investigated |
| PC-05 | Policies | High | 9,116 | Open |
| PC-06 | Policies | Medium | 1 | Open |
| PC-07 | Claims | Medium | 0 | Pass |

## Findings

### SP-01: Net premium ≠ direct − ceded (3,510 rows)
- **Finding:** Every difference is exactly ±1.
- **Cause:** Schedule P is reported in $ thousands; each figure is rounded separately.
- **Decision:** Not an error. Validate with a ±1 tolerance (SP-02, which passes).

### SP-03: Negative cumulative paid losses (724 rows)
- **Finding:** 724 rows (1.0% of Schedule P) across 66 companies.
  Concentrated: Contractors Bonding & Ins (14%), Atlantic Cas Ins Co (10%),
  Nova Cas Co (9%) = 33% of the negative amount. 49 of 66 are single
  companies rather than groups. 523 of the 724 rows also have negative
  incurred losses.
- **Likely cause:** Schedule P is net of reinsurance. Net recoveries
  (reinsurance, salvage, subrogation) exceeding payments for an accident
  year would produce negative net paid and incurred together.
  Not confirmed: the data does not include the reason.
- **Decision:** Keep the rows (likely valid accounting). Flag them, and
  exclude affected companies from industry loss ratio benchmarks.

### PC-02: Exposure above 1 year (1,224 policies, 0.2%)
- **Finding:** Max 2.01. 653 are between 1.01 and 1.05; only 42 are above 1.5.
- **Likely cause:** Small excesses from day-count conventions or short
  extensions; values above 1.5 may be two terms merged into one record.
- **Decision:** Cap exposure at 1.0 when calculating earned premium.

### PC-04: Claims with no matching policy (195 claims, €788,714)
- **Finding:** All 195 claims belong to just 6 policy IDs, all between
  2,220,367 and 2,286,775. One policy has 66 claims.
- **Impact:** 1.3% of total claim dollars (€60.7M).
- **Likely cause:** The clustered IDs suggest a batch of policies (possibly
  fleet or commercial) missing from the policy extract, not random errors.
- **Decision:** Exclude from policy-level reports; carry as a reconciling
  item between the claims and underwriting systems (Step 8).

### IA-03: Misspelled line names (3,708 rows)
- **Finding:** Source spells "Commerical" and "Occcurence".
- **Decision:** Map to correct spellings when loading.

### IA-04: Missing Iowa Code chapter (86 rows)
- **Decision:** Accepted. The field isn't used in any report.

### PC-05: Policies reporting claims with no claim records (9,116 policies)
- **Finding:** 26.8% of the 34,060 policies with claim_count > 0 have no
  records in the claims file: 9,657 claims in total. Most have 1 claim;
  one policy has 11.
- **Pattern:** 99.8% (9,099) have a policy ID of 1,000,000 or below. In that
  range 67% of claim-reporting policies are missing claim records; above it,
  almost none are (17 of 20,572). Region shares are similar to the full
  population, so region is not the driver.
- **Impact:** At the average claim of €2,279, about €22.0M of losses are
  missing, roughly 27% of what total losses would be (€60.7M on file).
  Loss ratios built from the claims file would be materially understated.
- **Likely cause:** Claims for the oldest block of policies (IDs ≤ 1M) were
  not included when the claims file was built: a batch extract issue,
  not individual errors. Consistent with PC-04, where orphan claims
  also cluster in one ID range. Not confirmed from the data alone.
- **Decision:** Loss reporting (loss ratio, severity) uses only policies with
  ID above 1,000,000, where policy and claims systems agree. Flagged in
  Step 6; carried as a reconciling item in Step 8.

### Open items
SP-04, SP-05, SP-06, IA-01, IA-02, PC-06: to be investigated.