"""
Step 6 - Build the underwriting and claims systems.

Run from the project folder:
    python src/03_enrich.py

The freMTPL data has no premiums and no dates, so this script adds them,
using the assumptions in config.py. It also applies two data quality
decisions: the exposure cap (PC-02) and the claims-complete flag (PC-05).

Outputs (in processed/):
    policies_enriched.csv          the UNDERWRITING system: one row per policy
    claims_enriched.csv            the CLAIMS system: one row per claim
    earned_premium_monthly.csv     earned premium by month x region x fuel type
"""
import numpy as np
import pandas as pd

import config
import load

# One random number generator with a fixed seed: same "random" numbers every run
rng = np.random.default_rng(config.RANDOM_SEED)

policies = load.load_policies()
claims = load.load_claims()
print(f"Loaded {len(policies):,} policies and {len(claims):,} claims")

# ===========================================================================
# PART 1: POLICIES (underwriting system)
# ===========================================================================

# --- 1a. Data quality decisions ---------------------------------------------
# PC-02: cap exposure at 1 year
policies["exposure_capped"] = policies["exposure_years"].clip(upper=config.EXPOSURE_CAP)

# PC-05: only policies above the ID cutoff have complete claim records
policies["claims_complete"] = policies["policy_id"] > config.CLAIMS_COMPLETE_MIN_ID

# --- 1b. Dates --------------------------------------------------------------
# Each policy starts on a random day in the 24-month reporting window
start = pd.Timestamp(config.REPORT_START)
window_end = start + pd.DateOffset(months=config.REPORT_MONTHS)
window_days = (window_end - start).days

policies["effective_date"] = start + pd.to_timedelta(
    rng.integers(0, window_days, size=len(policies)), unit="D"
)

# How long the policy is in force: exposure x 365 days (at least 1 day)
policies["term_days"] = (policies["exposure_capped"] * 365).round().clip(lower=1).astype(int)

# Coverage ends the day before expiry_date (expiry_date is the first day NOT covered)
policies["expiry_date"] = policies["effective_date"] + pd.to_timedelta(policies["term_days"], unit="D")

# --- 1c. Premium ------------------------------------------------------------
# Each rating factor is a multiplier: 1.0 = average, above 1 = riskier
policies["factor_bonus_malus"] = policies["bonus_malus"] / 100
policies["factor_area"] = policies["area_code"].map(config.AREA_FACTORS)
policies["factor_fuel"] = policies["fuel_type"].map(config.FUEL_FACTORS)
policies["factor_power"] = 1 + config.POWER_STEP * (policies["vehicle_power"] - 6)

policies["annual_premium"] = (
    config.BASE_RATE
    * policies["factor_bonus_malus"]
    * policies["factor_area"]
    * policies["factor_fuel"]
    * policies["factor_power"]
).round(2)

# Written premium covers only the period the policy is in force
policies["written_premium"] = (policies["annual_premium"] * policies["exposure_capped"]).round(2)

# --- 1d. Expenses -----------------------------------------------------------
policies["commission"] = (policies["written_premium"] * config.COMMISSION_RATE).round(2)
policies["admin_expense"] = config.ADMIN_COST_PER_POLICY

# Month the policy is booked in (used for written premium and expense reports)
policies["written_month"] = policies["effective_date"].dt.to_period("M").astype(str)

# ===========================================================================
# PART 2: CLAIMS (claims system)
# ===========================================================================
# Bring each claim's policy dates and segments onto the claim (like a VLOOKUP).
# how="left" keeps every claim, even the orphan claims with no policy (PC-04).
policy_cols = ["policy_id", "effective_date", "term_days", "region", "fuel_type", "claims_complete"]
claims = claims.merge(policies[policy_cols], on="policy_id", how="left")
claims["is_orphan"] = claims["effective_date"].isna()

# Accident happens on a random day while the policy is in force
days_into_policy = np.floor(rng.random(len(claims)) * claims["term_days"].fillna(0))
claims["accident_date"] = claims["effective_date"] + pd.to_timedelta(days_into_policy, unit="D")

# Claim is reported 0 to 45 days after the accident
claims["report_date"] = claims["accident_date"] + pd.to_timedelta(
    rng.integers(0, config.MAX_REPORT_LAG_DAYS + 1, size=len(claims)), unit="D"
)

claims["accident_month"] = claims["accident_date"].dt.to_period("M").astype(str)
claims["report_month"] = claims["report_date"].dt.to_period("M").astype(str)
claims = claims.drop(columns=["effective_date", "term_days"])

# ===========================================================================
# PART 3: EARNED PREMIUM BY MONTH
# ===========================================================================
# Premium is earned evenly, day by day, while the policy is in force.
# For each month: earned = written premium x (days covered in that month / term days)
daily_premium = policies["written_premium"] / policies["term_days"]

first_month = start.to_period("M")
last_month = policies["expiry_date"].max().to_period("M")

monthly = []
for month in pd.period_range(first_month, last_month, freq="M"):
    month_start = month.start_time
    next_month_start = (month + 1).start_time

    # Days of overlap between [effective, expiry) and [month_start, next_month_start)
    overlap_start = policies["effective_date"].clip(lower=month_start)
    overlap_end = policies["expiry_date"].clip(upper=next_month_start)
    days = (overlap_end - overlap_start).dt.days.clip(lower=0)

    earned = daily_premium * days
    summary = (
        policies.assign(earned_premium=earned, exposure_days=days)
        .groupby(["region", "fuel_type", "claims_complete"], as_index=False)
        [["earned_premium", "exposure_days"]].sum()
    )
    summary.insert(0, "month", str(month))
    monthly.append(summary)

earned_monthly = pd.concat(monthly, ignore_index=True)

# ===========================================================================
# PART 4: CONTROL CHECKS - prove the new numbers are right before using them
# ===========================================================================
print("\n=== CONTROL CHECKS ===")

total_written = policies["written_premium"].sum()
total_earned = earned_monthly["earned_premium"].sum()
check1 = abs(total_written - total_earned) < 1
print(f"[{'PASS' if check1 else 'FAIL'}] Total earned = total written:"
      f" written €{total_written:,.2f}, earned €{total_earned:,.2f}")

matched = claims[~claims["is_orphan"]]
check2 = matched["accident_date"].notna().all()
print(f"[{'PASS' if check2 else 'FAIL'}] Every matched claim has an accident date")

in_force = matched.merge(policies[["policy_id", "effective_date", "expiry_date"]], on="policy_id")
check3 = ((in_force["accident_date"] >= in_force["effective_date"])
          & (in_force["accident_date"] < in_force["expiry_date"])).all()
print(f"[{'PASS' if check3 else 'FAIL'}] Every accident falls inside its policy period")

check4 = len(claims) == 26_639 and claims["claim_id"].is_unique
print(f"[{'PASS' if check4 else 'FAIL'}] No claims lost or duplicated in the merge ({len(claims):,})")

print(f"\nOrphan claims kept with no dates (PC-04): {claims['is_orphan'].sum()}")
print(f"Policies with complete claims (PC-05):   {policies['claims_complete'].sum():,}")

# A first look at the economics, on the population where claims are complete
complete = policies[policies["claims_complete"]]
complete_losses = claims.loc[claims["claims_complete"] == True, "claim_amount"].sum()
complete_premium = complete["written_premium"].sum()
expenses = complete["commission"].sum() + complete["admin_expense"].sum()
print("\n=== FIRST LOOK (claims-complete policies) ===")
print(f"Written premium: €{complete_premium:,.0f}")
print(f"Losses:          €{complete_losses:,.0f}")
print(f"Loss ratio:      {complete_losses / complete_premium:.1%}")
print(f"Expense ratio:   {expenses / complete_premium:.1%}")
print(f"Combined ratio:  {(complete_losses + expenses) / complete_premium:.1%}")

# ===========================================================================
# SAVE
# ===========================================================================
policies.to_csv(config.PROCESSED_DIR / "policies_enriched.csv", index=False)
claims.to_csv(config.PROCESSED_DIR / "claims_enriched.csv", index=False)
earned_monthly.to_csv(config.PROCESSED_DIR / "earned_premium_monthly.csv", index=False)
print(f"\nSaved 3 files to {config.PROCESSED_DIR}")