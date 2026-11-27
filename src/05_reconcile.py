"""
Step 8 - Reconciliation: underwriting vs claims vs general ledger.

Run from the project folder:
    python src/05_reconcile.py

Three systems should tell the same financial story:
    Underwriting system  -> policies and premium   (policies_enriched.csv)
    Claims system        -> claims and losses      (claims_enriched.csv)
    General ledger (GL)  -> the accounting books   (built in Part 1 below)

The GL is simulated from the two systems, the way accounting would book it,
with a few errors planted on purpose (settings in config.py). The
reconciliations must find every difference and explain it.

Outputs (in outputs/):
    general_ledger.csv            the simulated GL journal
    recon_premium_monthly.csv     R1: underwriting vs GL premium by month
    recon_claims_detail.csv       R2: every claim that did not match the GL
    recon_losses_monthly.csv      R2: claims system vs GL losses by month
    recon_summary.csv             all reconciling items in one table
"""
import numpy as np
import pandas as pd

import config

rng = np.random.default_rng(config.RANDOM_SEED)

policies = pd.read_csv(config.PROCESSED_DIR / "policies_enriched.csv",
                       parse_dates=["effective_date"])
claims = pd.read_csv(config.PROCESSED_DIR / "claims_enriched.csv")

# Orphan claims have no policy, so no dates; they are covered in R3 instead
dated_claims = claims[~claims["is_orphan"]].copy()

# ===========================================================================
# PART 1: BUILD THE GENERAL LEDGER
# Accounting books premium in the month a policy is WRITTEN, and a claim in
# the month it is REPORTED (accounting can't book what it doesn't know about).
# ===========================================================================
print("Building the general ledger ...")

# --- Premium entries: one per policy ---------------------------------------
gl_premium = pd.DataFrame({
    "gl_month": policies["written_month"],
    "account": "Written Premium",
    "source_ref": policies["policy_id"],
    "amount": policies["written_premium"],
})

# Planted error 1: CUTOFF. A few policies written on the last day of a month
# are booked in the next month instead.
last_day = policies["effective_date"].dt.is_month_end & (policies["written_month"] < "2025-12")
cutoff_ids = rng.choice(policies.loc[last_day, "policy_id"], config.GL_PREMIUM_CUTOFF_ERRORS, replace=False)
is_cutoff = gl_premium["source_ref"].isin(cutoff_ids)
next_month = pd.PeriodIndex(gl_premium.loc[is_cutoff, "gl_month"], freq="M") + 1
gl_premium.loc[is_cutoff, "gl_month"] = next_month.astype(str)

# --- Claim entries: one per claim, in the month it was reported ------------
gl_claims = pd.DataFrame({
    "gl_month": dated_claims["report_month"],
    "account": "Claims Incurred",
    "source_ref": dated_claims["claim_id"],
    "amount": dated_claims["claim_amount"],
})

# Planted errors 2-4 each use different claims
picked = rng.choice(gl_claims["source_ref"],
                    config.GL_DUPLICATE_CLAIMS + config.GL_MISSING_CLAIMS + config.GL_DECIMAL_ERRORS,
                    replace=False)
dup_ids = picked[:config.GL_DUPLICATE_CLAIMS]
missing_ids = picked[config.GL_DUPLICATE_CLAIMS:config.GL_DUPLICATE_CLAIMS + config.GL_MISSING_CLAIMS]
decimal_ids = picked[config.GL_DUPLICATE_CLAIMS + config.GL_MISSING_CLAIMS:]

# Error 2: DUPLICATE - the same claim posted twice
gl_claims = pd.concat([gl_claims, gl_claims[gl_claims["source_ref"].isin(dup_ids)]], ignore_index=True)
# Error 3: MISSING - claims never posted
gl_claims = gl_claims[~gl_claims["source_ref"].isin(missing_ids)]
# Error 4: DECIMAL - amount keyed at 10 times the real value
gl_claims.loc[gl_claims["source_ref"].isin(decimal_ids), "amount"] *= 10

gl = pd.concat([gl_premium, gl_claims], ignore_index=True)
gl.insert(0, "gl_entry_id", range(1, len(gl) + 1))
gl.to_csv(config.OUTPUTS_DIR / "general_ledger.csv", index=False)
print(f"  {len(gl):,} GL entries ({len(gl_premium):,} premium, {len(gl_claims):,} claims)")

# ===========================================================================
# R1: PREMIUM - underwriting system vs GL, by month
# ===========================================================================
print("\nR1: Premium (underwriting system vs general ledger)")

uw_monthly = policies.groupby("written_month")["written_premium"].sum().rename("uw_premium")
gl_monthly = gl_premium.groupby("gl_month")["amount"].sum().rename("gl_premium")

r1 = pd.concat([uw_monthly, gl_monthly], axis=1).fillna(0)
r1.index.name = "month"
r1["difference"] = (r1["gl_premium"] - r1["uw_premium"]).round(2)

# Explain each month's difference using the policy-level detail:
# a cutoff policy is missing from its written month (-) and extra in the next month (+)
cutoff = policies[policies["policy_id"].isin(cutoff_ids)][["policy_id", "written_month", "written_premium"]]
out_of_month = cutoff.groupby("written_month")["written_premium"].sum()
cutoff["booked_month"] = (pd.PeriodIndex(cutoff["written_month"], freq="M") + 1).astype(str)
into_month = cutoff.groupby("booked_month")["written_premium"].sum()

r1["explained_cutoff"] = into_month.reindex(r1.index, fill_value=0) - out_of_month.reindex(r1.index, fill_value=0)
r1["unexplained"] = (r1["difference"] - r1["explained_cutoff"]).round(2)
r1 = r1.reset_index()
r1.to_csv(config.OUTPUTS_DIR / "recon_premium_monthly.csv", index=False)

months_with_diff = (r1["difference"].abs() > 0.005).sum()
print(f"  Months with a difference: {months_with_diff} of {len(r1)}")
print(f"  Total difference over all months: €{r1['difference'].sum():,.2f}  (cutoff errors net to zero over time)")
print(f"  Unexplained: €{r1['unexplained'].abs().sum():,.2f}")

# ===========================================================================
# R2: LOSSES - claims system vs GL, claim by claim
# ===========================================================================
print("\nR2: Losses (claims system vs general ledger)")

# How many times, and at what amount, did each claim reach the GL?
gl_by_claim = gl_claims.groupby("source_ref").agg(
    gl_postings=("amount", "size"),
    gl_amount=("amount", "sum"),
    gl_month=("gl_month", "first"),
).reset_index().rename(columns={"source_ref": "claim_id"})

detail = dated_claims[["claim_id", "policy_id", "claim_amount", "accident_month", "report_month"]].merge(
    gl_by_claim, on="claim_id", how="left"
)
detail["gl_postings"] = detail["gl_postings"].fillna(0).astype(int)
detail["gl_amount"] = detail["gl_amount"].fillna(0)


def classify(row):
    """Put each claim into one reconciliation category."""
    if row["gl_postings"] == 0:
        return "Missing from GL"
    if row["gl_postings"] > 1:
        return "Duplicate in GL"
    if abs(row["gl_amount"] - row["claim_amount"]) > 0.01:
        return "Amount difference"
    if row["gl_month"] != row["accident_month"]:
        return "Timing: reported in a later month"
    return "Matched"


detail["status"] = detail.apply(classify, axis=1)
detail["difference"] = (detail["gl_amount"] - detail["claim_amount"]).round(2)

breaks = detail[detail["status"] != "Matched"]
breaks.to_csv(config.OUTPUTS_DIR / "recon_claims_detail.csv", index=False)

status_summary = detail.groupby("status").agg(
    claims=("claim_id", "count"),
    claims_system=("claim_amount", "sum"),
    general_ledger=("gl_amount", "sum"),
    difference=("difference", "sum"),
)
with pd.option_context("display.float_format", "{:,.2f}".format):
    print(status_summary.to_string())

# Monthly view: claims system (by accident month) vs GL (by report month)
cs_monthly = dated_claims.groupby("accident_month")["claim_amount"].sum().rename("claims_system")
gl_loss_monthly = gl_claims.groupby("gl_month")["amount"].sum().rename("general_ledger")
r2_monthly = pd.concat([cs_monthly, gl_loss_monthly], axis=1).fillna(0)
r2_monthly.index.name = "month"
r2_monthly["difference"] = r2_monthly["general_ledger"] - r2_monthly["claims_system"]
r2_monthly.reset_index().to_csv(config.OUTPUTS_DIR / "recon_losses_monthly.csv", index=False)

# ===========================================================================
# R3: UNDERWRITING vs CLAIMS SYSTEM (known items from data validation)
# ===========================================================================
print("\nR3: Underwriting system vs claims system")
orphans = claims[claims["is_orphan"]]
missing_records = policies[(policies["claim_count"] > 0)
                           & ~policies["policy_id"].isin(claims["policy_id"])]
avg_claim = claims["claim_amount"].mean()
print(f"  Orphan claims (no policy, PC-04):       {len(orphans):,} claims, €{orphans['claim_amount'].sum():,.0f}")
print(f"  Policies with claims but no records (PC-05): {missing_records['claim_count'].sum():,} claims,"
      f" est. €{missing_records['claim_count'].sum() * avg_claim:,.0f}")

# ===========================================================================
# SUMMARY: every reconciling item in one table
# ===========================================================================
items = []
items.append({"recon": "R1 Premium", "item": "Cutoff: booked in following month",
              "count": len(cutoff_ids), "amount": cutoff["written_premium"].sum(),
              "type": "Timing", "action": "Reverses next month; fix posting date"})
for status in ["Timing: reported in a later month", "Duplicate in GL", "Missing from GL", "Amount difference"]:
    rows = detail[detail["status"] == status]
    items.append({
        "recon": "R2 Losses", "item": status, "count": len(rows),
        "amount": rows["difference"].sum() if status != "Timing: reported in a later month" else rows["claim_amount"].sum(),
        "type": "Timing" if status.startswith("Timing") else "Error",
        "action": {"Timing: reported in a later month": "Expected; accrue via IBNR",
                   "Duplicate in GL": "Reverse the duplicate posting",
                   "Missing from GL": "Post the missing claims",
                   "Amount difference": "Correct the keyed amount"}[status],
    })
items.append({"recon": "R3 UW vs Claims", "item": "Orphan claims (PC-04)", "count": len(orphans),
              "amount": orphans["claim_amount"].sum(), "type": "Data", "action": "Locate missing policy records"})
items.append({"recon": "R3 UW vs Claims", "item": "Missing claim records (PC-05, estimated)",
              "count": int(missing_records["claim_count"].sum()),
              "amount": missing_records["claim_count"].sum() * avg_claim,
              "type": "Data", "action": "Request claims extract for policy IDs <= 1,000,000"})
summary = pd.DataFrame(items)
summary["amount"] = summary["amount"].round(2)
summary.to_csv(config.OUTPUTS_DIR / "recon_summary.csv", index=False)

print("\n=== RECONCILING ITEMS ===")
with pd.option_context("display.float_format", "{:,.2f}".format, "display.max_colwidth", 45):
    print(summary.to_string(index=False))

# ===========================================================================
# CONTROL: over the whole period, GL claims = claims system + errors found
# ===========================================================================
errors = detail.loc[detail["status"].isin(["Duplicate in GL", "Missing from GL", "Amount difference"]), "difference"].sum()
ok = abs(gl_claims["amount"].sum() - (dated_claims["claim_amount"].sum() + errors)) < 0.01
print(f"\n[{'PASS' if ok else 'FAIL'}] GL losses = claims system + identified errors"
      f" (€{gl_claims['amount'].sum():,.2f} = €{dated_claims['claim_amount'].sum():,.2f} + €{errors:,.2f})")
print(f"Reports saved to {config.OUTPUTS_DIR}")