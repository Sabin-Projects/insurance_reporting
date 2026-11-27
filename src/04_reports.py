"""
Step 7 - Monthly product-level financial reports.

Run from the project folder:
    python src/04_reports.py

Builds three reports and proves each one ties back to its source:
    1. Monthly product report   (freMTPL)    month x region x policy type
    2. Line of business report  (Schedule P) line x accident year
    3. State report             (Iowa)       line of insurance, plus spotlight

Outputs (in outputs/):
    report_monthly_product.csv
    report_line_of_business.csv
    report_iowa_lines.csv
    report_spotlight.csv
"""
import numpy as np
import pandas as pd

import config
import load


def ratio(numerator, denominator):
    """Divide, but return blank (NaN) instead of an error or infinity when the
    denominator is zero. Metric standard: a ratio with no premium is blank."""
    return numerator / denominator.replace(0, np.nan)


def control_check(label, report_total, source_total, tolerance=1):
    """Print PASS/FAIL: does the report total tie back to the source total?"""
    ok = abs(report_total - source_total) <= tolerance
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: report {report_total:,.2f} vs source {source_total:,.2f}")
    return ok


# ===========================================================================
# REPORT 1: MONTHLY PRODUCT REPORT
# Reporting basis: claims-complete policies only (data quality decision PC-05),
# so premium and losses come from the same set of policies.
# ===========================================================================
print("Building monthly product report ...")
policies = pd.read_csv(config.PROCESSED_DIR / "policies_enriched.csv")
claims = pd.read_csv(config.PROCESSED_DIR / "claims_enriched.csv")
earned = pd.read_csv(config.PROCESSED_DIR / "earned_premium_monthly.csv")

policies = policies[policies["claims_complete"]]
claims = claims[claims["claims_complete"] == True]
earned = earned[earned["claims_complete"]]

keys = ["month", "region", "fuel_type"]

# Written side: grouped by the month each policy was written
written = (
    policies.rename(columns={"written_month": "month"})
    .groupby(keys)
    .agg(policies_written=("policy_id", "count"),
         written_premium=("written_premium", "sum"),
         commission=("commission", "sum"),
         admin_expense=("admin_expense", "sum"))
    .reset_index()
)

# Earned side: already monthly from Step 6
earned_side = earned.groupby(keys)[["earned_premium", "exposure_days"]].sum().reset_index()

# Loss side: grouped by the month the accident happened
losses = (
    claims.rename(columns={"accident_month": "month"})
    .groupby(keys)
    .agg(claim_count=("claim_id", "count"), incurred_loss=("claim_amount", "sum"))
    .reset_index()
)

# Combine the three sides. "outer" keeps a row if ANY side has data for it.
monthly = (
    written.merge(earned_side, on=keys, how="outer")
           .merge(losses, on=keys, how="outer")
           .fillna(0)
)

# Keep the 24-month reporting window (earned premium runs into 2026)
window = pd.period_range(config.REPORT_START, periods=config.REPORT_MONTHS, freq="M").astype(str)
monthly = monthly[monthly["month"].isin(window)]

# KPIs, following docs/metric_standards.md
monthly["total_expense"] = monthly["commission"] + monthly["admin_expense"]
monthly["loss_ratio"] = ratio(monthly["incurred_loss"], monthly["earned_premium"])
monthly["expense_ratio"] = ratio(monthly["total_expense"], monthly["written_premium"])
monthly["combined_ratio"] = monthly["loss_ratio"] + monthly["expense_ratio"]
monthly["avg_written_premium"] = ratio(monthly["written_premium"], monthly["policies_written"])
monthly["claim_frequency"] = ratio(monthly["claim_count"], monthly["exposure_days"] / 365)
monthly["claim_severity"] = ratio(monthly["incurred_loss"], monthly["claim_count"])

monthly = monthly.sort_values(keys).reset_index(drop=True)
monthly.to_csv(config.OUTPUTS_DIR / "report_monthly_product.csv", index=False)

print(" Control totals:")
control_check("Written premium", monthly["written_premium"].sum(), policies["written_premium"].sum())
control_check("Policies written", monthly["policies_written"].sum(), len(policies), tolerance=0)
# Losses: report + accidents after the window must equal all claims
in_window = claims["accident_month"].isin(window)
after_window = claims.loc[~in_window, "claim_amount"].sum()
control_check("Incurred loss (report + after window)",
              monthly["incurred_loss"].sum() + after_window, claims["claim_amount"].sum())
print(f"  Losses with accidents after {window[-1]} (not in report): €{after_window:,.2f}")
control_check("Earned premium (window)", monthly["earned_premium"].sum(),
              earned.loc[earned["month"].isin(window), "earned_premium"].sum())

# Year view of the same report, for a quick read
monthly["year"] = monthly["month"].str[:4]
by_year = monthly.groupby("year")[["written_premium", "earned_premium", "incurred_loss", "total_expense"]].sum()
by_year["loss_ratio"] = by_year["incurred_loss"] / by_year["earned_premium"]
by_year["expense_ratio"] = by_year["total_expense"] / by_year["written_premium"]
by_year["combined_ratio"] = by_year["loss_ratio"] + by_year["expense_ratio"]
print("\n Summary by year:")
with pd.option_context("display.float_format", "{:,.3f}".format):
    print(by_year.to_string())

unearned = (policies["written_premium"].sum()
            - earned.loc[earned["month"].isin(window), "earned_premium"].sum())
print(f"\n Unearned premium at {window[-1]} month-end: €{unearned:,.0f}")


# ===========================================================================
# REPORT 2: LINE OF BUSINESS (Schedule P)
# As reported in the 2007 annual statement: each accident year at its 2007
# valuation. Companies with negative paid losses in a line are excluded from
# the industry totals (data quality decision SP-03).
# ===========================================================================
print("\nBuilding line of business report ...")
sp = load.load_schedule_p()

# Which company/line combinations had any negative paid loss (SP-03)?
negative = sp.loc[sp["cum_paid_loss"] < 0, ["lob_code", "group_code"]].drop_duplicates()
negative["sp03_flag"] = True
sp = sp.merge(negative, on=["lob_code", "group_code"], how="left")
sp["sp03_flag"] = sp["sp03_flag"].fillna(False).astype(bool)

as_of = sp[sp["development_year"] == config.SCHEDULE_P_AS_OF_YEAR]
included = as_of[~as_of["sp03_flag"]]

lob = (
    included.groupby(["lob_code", "lob_name", "accident_year"])
    .agg(companies=("group_code", "nunique"),
         direct_earned=("earned_prem_direct", "sum"),
         ceded_earned=("earned_prem_ceded", "sum"),
         net_earned=("earned_prem_net", "sum"),
         paid_loss=("cum_paid_loss", "sum"),
         incurred_loss=("incurred_loss", "sum"))
    .reset_index()
)
lob["reserves"] = lob["incurred_loss"] - lob["paid_loss"]
lob["pct_ceded"] = ratio(lob["ceded_earned"], lob["direct_earned"])
lob["net_loss_ratio"] = ratio(lob["incurred_loss"], lob["net_earned"])
lob["paid_to_incurred"] = ratio(lob["paid_loss"], lob["incurred_loss"])
lob.to_csv(config.OUTPUTS_DIR / "report_line_of_business.csv", index=False)

print(" Control totals:")
control_check("Net earned premium", lob["net_earned"].sum(), included["earned_prem_net"].sum())
control_check("Incurred loss", lob["incurred_loss"].sum(), included["incurred_loss"].sum())
print(f"  Company/line combinations excluded for SP-03: {len(negative)}")

lob_total = lob.groupby("lob_name")[["net_earned", "incurred_loss", "reserves"]].sum()
lob_total["net_loss_ratio"] = lob_total["incurred_loss"] / lob_total["net_earned"]
print("\n All accident years 1998-2007, $ thousands:")
with pd.option_context("display.float_format", "{:,.3f}".format):
    print(lob_total.sort_values("net_earned", ascending=False).to_string())


# ===========================================================================
# REPORT 3: IOWA STATE REPORT + SPOTLIGHT
# ===========================================================================
print("\nBuilding Iowa state report ...")
iowa = load.load_iowa()

# IA-03: fix misspelled line names
for wrong, right in config.LINE_NAME_FIXES.items():
    iowa["line_of_insurance"] = iowa["line_of_insurance"].str.replace(wrong, right)

active = iowa[iowa["premiums_written"] != 0]

lines = (
    iowa.groupby("line_of_insurance")
    .agg(premiums_written=("premiums_written", "sum"),
         losses_paid=("losses_paid", "sum"),
         taxes_paid=("taxes_paid", "sum"))
    .reset_index()
)
companies = active.groupby("line_of_insurance")["company_name"].nunique().rename("companies_writing")
lines = lines.merge(companies, on="line_of_insurance", how="left").fillna({"companies_writing": 0})
lines["paid_loss_ratio"] = ratio(lines["losses_paid"], lines["premiums_written"])
lines["implied_tax_rate"] = ratio(lines["taxes_paid"], lines["premiums_written"])
lines = lines.sort_values("premiums_written", ascending=False)
lines.to_csv(config.OUTPUTS_DIR / "report_iowa_lines.csv", index=False)

print(" Control totals:")
control_check("Premiums written", lines["premiums_written"].sum(), iowa["premiums_written"].sum())
control_check("Losses paid", lines["losses_paid"].sum(), iowa["losses_paid"].sum())

# Spotlight: the company's lines compared to the Iowa market
co = iowa[iowa["company_name"].str.contains(config.SPOTLIGHT_COMPANY, case=False)
          & (iowa["premiums_written"] != 0)]
spot = co[["line_of_insurance", "premiums_written", "losses_paid"]].merge(
    lines[["line_of_insurance", "premiums_written", "losses_paid", "companies_writing"]],
    on="line_of_insurance", suffixes=("_company", "_market"),
)
spot["market_share"] = spot["premiums_written_company"] / spot["premiums_written_market"]
spot["company_paid_lr"] = ratio(spot["losses_paid_company"], spot["premiums_written_company"])
spot["market_paid_lr"] = ratio(spot["losses_paid_market"], spot["premiums_written_market"])

# Rank within the spotlight line: where does the company place among all writers?
line_writers = active[active["line_of_insurance"] == config.SPOTLIGHT_LINE].copy()
line_writers["rank"] = line_writers["premiums_written"].rank(ascending=False, method="min")
company_rank = line_writers.loc[
    line_writers["company_name"].str.contains(config.SPOTLIGHT_COMPANY, case=False), "rank"
]
spot.to_csv(config.OUTPUTS_DIR / "report_spotlight.csv", index=False)

print(f"\n {config.SPOTLIGHT_COMPANY} vs Iowa market (2019):")
print(spot[["line_of_insurance", "premiums_written_company", "market_share",
            "company_paid_lr", "market_paid_lr"]].round(4).to_string(index=False))
if not company_rank.empty:
    print(f"\n Rank in Iowa {config.SPOTLIGHT_LINE}: #{int(company_rank.iloc[0])}"
          f" of {len(line_writers)} companies writing the line")

print(f"\nReports saved to {config.OUTPUTS_DIR}")