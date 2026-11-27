"""
Step 5 - Data validation.

Runs a list of data quality rules against every source. For each rule it
counts the failing rows and saves them, so every issue can be investigated.

Outputs:
    outputs/dq_results.csv            one row per rule: pass/fail and count
    outputs/dq_failures/<rule>.csv    the failing rows for each failed rule
"""
import pandas as pd

import config
import load

FAIL_DIR = config.OUTPUTS_DIR / "dq_failures"
FAIL_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load every source once
# ---------------------------------------------------------------------------
print("Loading data ...")
sp = load.load_schedule_p()
iowa = load.load_iowa()
policies = load.load_policies()
claims = load.load_claims()


# ---------------------------------------------------------------------------
# RULES
# Each rule is a function that returns the rows that FAIL it.
# An empty result means the rule passed.
# ---------------------------------------------------------------------------

# ----- Schedule P ----------------------------------------------------------
def sp_net_premium_exact():
    """Net earned premium should equal direct minus ceded, exactly."""
    diff = sp["earned_prem_direct"] - sp["earned_prem_ceded"] - sp["earned_prem_net"]
    return sp[diff != 0]


def sp_net_premium_tolerance():
    """Net premium = direct - ceded, allowing 1 for rounding ($ thousands)."""
    diff = sp["earned_prem_direct"] - sp["earned_prem_ceded"] - sp["earned_prem_net"]
    return sp[diff.abs() > 1]


def sp_negative_paid():
    """Cumulative paid losses should never be negative."""
    return sp[sp["cum_paid_loss"] < 0]


def sp_paid_decreases():
    """Cumulative paid should not go down from one development year to the next."""
    ordered = sp.sort_values(["lob_code", "group_code", "accident_year", "development_lag"])
    change = ordered.groupby(["lob_code", "group_code", "accident_year"])["cum_paid_loss"].diff()
    return ordered[change < 0]


def sp_paid_exceeds_incurred():
    """Paid losses should not be larger than incurred losses."""
    return sp[sp["cum_paid_loss"] > sp["incurred_loss"]]


def sp_incomplete_triangle():
    """Each company and line should have 10 accident years x 10 lags = 100 rows."""
    counts = sp.groupby(["lob_code", "lob_name", "group_code", "group_name"]).size()
    counts = counts.reset_index(name="rows")
    return counts[counts["rows"] != 100]


# ----- Iowa ----------------------------------------------------------------
def ia_negative_premium():
    """Premiums written should not be negative."""
    return iowa[iowa["premiums_written"] < 0]


def ia_losses_without_premium():
    """Losses paid on a line with zero premium written should be reviewed."""
    return iowa[(iowa["losses_paid"] > 0) & (iowa["premiums_written"] == 0)]


def ia_misspelled_lines():
    """Line names should be spelled consistently (known typos in the source)."""
    typos = ["Commerical", "Occcurence"]
    pattern = "|".join(typos)            # "Commerical|Occcurence" means either one
    return iowa[iowa["line_of_insurance"].str.contains(pattern)]


def ia_missing_chapter():
    """Every company should have the Iowa Code chapter it is licensed under."""
    return iowa[iowa["chapter"].isna()]


# ----- Policies and claims (freMTPL) ---------------------------------------
def pc_duplicate_policy():
    """Each policy ID should appear only once."""
    return policies[policies["policy_id"].duplicated(keep=False)]


def pc_exposure_out_of_range():
    """Exposure must be above 0 and at most 1 year."""
    e = policies["exposure_years"]
    return policies[(e <= 0) | (e > 1)]


def pc_driver_age_out_of_range():
    """Drivers must be 18 to 100 years old."""
    a = policies["driver_age"]
    return policies[(a < 18) | (a > 100)]


def pc_orphan_claims():
    """Every claim should belong to a policy in the underwriting system."""
    return claims[~claims["policy_id"].isin(policies["policy_id"])]


def pc_claims_missing():
    """Policies with claim_count > 0 should have claim records."""
    has_claims = policies[policies["claim_count"] > 0]
    return has_claims[~has_claims["policy_id"].isin(claims["policy_id"])]


def pc_claim_count_mismatch():
    """Where both exist, claim_count should equal the number of claim records."""
    records = claims.groupby("policy_id").size().rename("claim_records")
    joined = policies.merge(records, on="policy_id", how="inner")
    return joined[joined["claim_count"] != joined["claim_records"]]


def pc_nonpositive_claim():
    """Claim amounts should be greater than zero."""
    return claims[claims["claim_amount"] <= 0]


# ---------------------------------------------------------------------------
# RULE REGISTER: id, source, severity, function
# Severity: High   = would misstate a reported number
#           Medium = needs a documented treatment
#           Low    = cosmetic or explained
# ---------------------------------------------------------------------------
RULES = [
    ("SP-01", "Schedule P", "Low",    sp_net_premium_exact),
    ("SP-02", "Schedule P", "High",   sp_net_premium_tolerance),
    ("SP-03", "Schedule P", "High",   sp_negative_paid),
    ("SP-04", "Schedule P", "Medium", sp_paid_decreases),
    ("SP-05", "Schedule P", "High",   sp_paid_exceeds_incurred),
    ("SP-06", "Schedule P", "Medium", sp_incomplete_triangle),
    ("IA-01", "Iowa",       "Medium", ia_negative_premium),
    ("IA-02", "Iowa",       "Medium", ia_losses_without_premium),
    ("IA-03", "Iowa",       "Low",    ia_misspelled_lines),
    ("IA-04", "Iowa",       "Low",    ia_missing_chapter),
    ("PC-01", "Policies",   "High",   pc_duplicate_policy),
    ("PC-02", "Policies",   "Medium", pc_exposure_out_of_range),
    ("PC-03", "Policies",   "Medium", pc_driver_age_out_of_range),
    ("PC-04", "Claims",     "High",   pc_orphan_claims),
    ("PC-05", "Policies",   "High",   pc_claims_missing),
    ("PC-06", "Policies",   "Medium", pc_claim_count_mismatch),
    ("PC-07", "Claims",     "Medium", pc_nonpositive_claim),
]

SOURCE_ROWS = {
    "Schedule P": len(sp),
    "Iowa": len(iowa),
    "Policies": len(policies),
    "Claims": len(claims),
}

# ---------------------------------------------------------------------------
# RUN EVERY RULE
# ---------------------------------------------------------------------------
results = []
for rule_id, source, severity, check in RULES:
    failures = check()
    n_fail = len(failures)

    if n_fail > 0:
        failures.to_csv(FAIL_DIR / f"{rule_id}.csv", index=False)

    results.append({
        "rule_id": rule_id,
        "source": source,
        "severity": severity,
        "description": check.__doc__,
        "rows_checked": SOURCE_ROWS[source],
        "rows_failed": n_fail,
        "status": "PASS" if n_fail == 0 else "FAIL",
    })

results = pd.DataFrame(results)
results.to_csv(config.OUTPUTS_DIR / "dq_results.csv", index=False)

print("\n=== DATA QUALITY RESULTS ===")
print(results[["rule_id", "severity", "status", "rows_failed", "description"]].to_string(index=False))

failed = results[results["status"] == "FAIL"]
print(f"\n{len(results)} rules run: {len(results) - len(failed)} passed, {len(failed)} failed.")
print(f"Failing rows saved to {FAIL_DIR}")