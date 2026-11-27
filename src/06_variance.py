"""
Step 9 - Variance analysis on premium, loss and expense.

Run from the project folder:
    python src/06_variance.py

Explains WHY the numbers moved, in four analyses:
    A. Premium: 2025 actual vs budget by region, split into volume and rate
    B. Loss ratio: 2025 vs 2024, split into attritional and large losses
    C. Expense ratio: 2025 actual vs budget
    D. Reserve development: Schedule P incurred losses at year 1 vs year 10
Then drafts written commentary for the largest variances.

Outputs (in outputs/):
    variance_premium_by_region.csv
    variance_loss_ratio.csv
    variance_reserve_development.csv
    variance_commentary.md
"""
import pandas as pd

import config
import load

report = pd.read_csv(config.OUTPUTS_DIR / "report_monthly_product.csv")
report["year"] = report["month"].str[:4]

claims = pd.read_csv(config.PROCESSED_DIR / "claims_enriched.csv")
claims = claims[(claims["claims_complete"] == True)]
claims["year"] = claims["accident_month"].str[:4]
claims = claims[claims["year"].isin(["2024", "2025"])]
claims["is_large"] = claims["claim_amount"] >= config.LARGE_LOSS_THRESHOLD

commentary = []   # bullet points collected as we go


def pct(x):
    return f"{x:.1%}"


def eur(x):
    sign = "-" if x < 0 else ""
    return f"{sign}€{abs(x):,.0f}"


# ===========================================================================
# A. PREMIUM: 2025 ACTUAL vs BUDGET, VOLUME AND RATE
#    Premium = number of policies x average premium per policy.
#    Volume effect = change in policy count, priced at budget average premium
#    Rate effect   = change in average premium, on the actual policy count
#    Volume + rate = total variance, exactly.
# ===========================================================================
print("A. Written premium: 2025 actual vs budget, by region")

by_region = report.groupby(["region", "year"])[["policies_written", "written_premium"]].sum().unstack("year")
a = pd.DataFrame({
    "actual_policies": by_region[("policies_written", "2025")],
    "actual_premium": by_region[("written_premium", "2025")],
    "base_policies": by_region[("policies_written", "2024")],
    "base_premium": by_region[("written_premium", "2024")],
})
a["actual_avg"] = a["actual_premium"] / a["actual_policies"]
a["budget_policies"] = a["base_policies"] * (1 + config.BUDGET_POLICY_GROWTH)
a["budget_avg"] = (a["base_premium"] / a["base_policies"]) * (1 + config.BUDGET_AVG_PREMIUM_CHANGE)
a["budget_premium"] = a["budget_policies"] * a["budget_avg"]

a["variance"] = a["actual_premium"] - a["budget_premium"]
a["volume_effect"] = (a["actual_policies"] - a["budget_policies"]) * a["budget_avg"]
a["rate_effect"] = (a["actual_avg"] - a["budget_avg"]) * a["actual_policies"]
a["variance_pct"] = a["variance"] / a["budget_premium"]

# Check: the two effects must add up to the total variance
assert (a["volume_effect"] + a["rate_effect"] - a["variance"]).abs().max() < 0.01

a = a.sort_values("variance")
a.round(2).to_csv(config.OUTPUTS_DIR / "variance_premium_by_region.csv")

total = a[["budget_premium", "actual_premium", "variance", "volume_effect", "rate_effect"]].sum()
print(f"  Budget {eur(total['budget_premium'])} | Actual {eur(total['actual_premium'])}"
      f" | Variance {eur(total['variance'])} ({pct(total['variance'] / total['budget_premium'])})")
print(f"  Volume effect {eur(total['volume_effect'])} | Rate effect {eur(total['rate_effect'])}")
print("\n  Five largest regional shortfalls:")
show = a[["budget_premium", "actual_premium", "variance", "volume_effect", "rate_effect"]]
with pd.option_context("display.float_format", "{:,.0f}".format):
    print(show.head(5).to_string())

worst = a.iloc[0]
commentary.append(
    f"**Written premium** was {eur(total['actual_premium'])} against a budget of "
    f"{eur(total['budget_premium'])}, a variance of {eur(total['variance'])} "
    f"({pct(total['variance'] / total['budget_premium'])}). Volume contributed "
    f"{eur(total['volume_effect'])} and rate {eur(total['rate_effect'])}. "
    f"The largest shortfall was {a.index[0]} ({eur(worst['variance'])}), "
    f"mostly from {'volume' if abs(worst['volume_effect']) > abs(worst['rate_effect']) else 'rate'}."
)

# ===========================================================================
# B. LOSS RATIO: 2025 vs 2024, ATTRITIONAL vs LARGE LOSSES
#    Loss ratio = attritional loss ratio + large loss ratio
#    "Attritional" = the everyday, smaller claims
# ===========================================================================
print("\nB. Loss ratio: 2025 vs 2024")

earned = report.groupby("year")["earned_premium"].sum()
exposure_years = report.groupby("year")["exposure_days"].sum() / 365

b = claims.groupby(["year", "is_large"])["claim_amount"].agg(["sum", "count"]).unstack("is_large", fill_value=0)
lr = pd.DataFrame({
    "earned_premium": earned,
    "attritional_loss": b[("sum", False)],
    "large_loss": b[("sum", True)],
    "attritional_claims": b[("count", False)],
    "large_claims": b[("count", True)],
})
lr["attritional_lr"] = lr["attritional_loss"] / lr["earned_premium"]
lr["large_lr"] = lr["large_loss"] / lr["earned_premium"]
lr["total_lr"] = lr["attritional_lr"] + lr["large_lr"]
# Frequency and severity explain the attritional part
lr["attritional_frequency"] = lr["attritional_claims"] / exposure_years
lr["attritional_severity"] = lr["attritional_loss"] / lr["attritional_claims"]
lr.to_csv(config.OUTPUTS_DIR / "variance_loss_ratio.csv")

with pd.option_context("display.float_format", "{:,.3f}".format):
    print(lr[["attritional_lr", "large_lr", "total_lr", "large_claims",
              "attritional_frequency", "attritional_severity"]].to_string())

change = lr.loc["2025"] - lr.loc["2024"]
print(f"\n  Total loss ratio change: {change['total_lr']:+.1%} points")
print(f"    from attritional losses: {change['attritional_lr']:+.1%} points")
print(f"    from large losses:       {change['large_lr']:+.1%} points")

top = claims[claims["year"] == "2024"].nlargest(2, "claim_amount")
commentary.append(
    f"**Loss ratio** improved from {pct(lr.loc['2024', 'total_lr'])} in 2024 to "
    f"{pct(lr.loc['2025', 'total_lr'])} in 2025 ({change['total_lr']:+.1%} points). "
    f"Large losses (≥ {eur(config.LARGE_LOSS_THRESHOLD)}) explain {change['large_lr']:+.1%} points: "
    f"2024 had {int(lr.loc['2024', 'large_claims'])} large claims totalling "
    f"{eur(lr.loc['2024', 'large_loss'])}, including single claims of "
    f"{eur(top['claim_amount'].iloc[0])} ({top['region'].iloc[0]}, {top['accident_month'].iloc[0]}) and "
    f"{eur(top['claim_amount'].iloc[1])}. The attritional loss ratio moved "
    f"only {change['attritional_lr']:+.1%} points, so the underlying book is stable; "
    f"the year-on-year swing is large-loss volatility, not a trend."
)

# ===========================================================================
# C. EXPENSE RATIO: 2025 ACTUAL vs BUDGET
# ===========================================================================
print("\nC. Expense ratio: 2025 actual vs budget")
r25 = report[report["year"] == "2025"]
commission_ratio = r25["commission"].sum() / r25["written_premium"].sum()
admin_ratio = r25["admin_expense"].sum() / r25["written_premium"].sum()
actual_er = commission_ratio + admin_ratio
print(f"  Actual {pct(actual_er)} vs budget {pct(config.BUDGET_EXPENSE_RATIO)}"
      f" -> {actual_er - config.BUDGET_EXPENSE_RATIO:+.1%} points")
print(f"    commission {pct(commission_ratio)} + admin {pct(admin_ratio)}")
avg_premium = r25["written_premium"].sum() / r25["policies_written"].sum()
print(f"  Average written premium is {eur(avg_premium)}, so the fixed {eur(config.ADMIN_COST_PER_POLICY)}"
      f" admin cost per policy is {pct(config.ADMIN_COST_PER_POLICY / avg_premium)} of a typical premium")

commentary.append(
    f"**Expense ratio** was {pct(actual_er)} against a budget of {pct(config.BUDGET_EXPENSE_RATIO)} "
    f"({actual_er - config.BUDGET_EXPENSE_RATIO:+.1%} points). Commission is a fixed "
    f"{pct(commission_ratio)}; the overrun is the {eur(config.ADMIN_COST_PER_POLICY)} per-policy admin cost, "
    f"which is {pct(admin_ratio)} of premium because the average policy is small "
    f"({eur(avg_premium)}, many written for part of a year). Combined ratio for 2025 is "
    f"{pct(lr.loc['2025', 'total_lr'] + actual_er)}."
)

# ===========================================================================
# D. RESERVE DEVELOPMENT (Schedule P)
#    How much did each line's incurred losses change between the first
#    year-end (lag 1) and ten years later (lag 10)?
#    Positive = ADVERSE (first estimate too low); negative = FAVORABLE.
# ===========================================================================
print("\nD. Reserve development: incurred at lag 1 vs lag 10 (Schedule P)")
sp = load.load_schedule_p()

# Exclude company/lines flagged in SP-03 (negative paid losses)
flagged = sp.loc[sp["cum_paid_loss"] < 0, ["lob_code", "group_code"]].drop_duplicates()
sp = sp.merge(flagged.assign(flag=True), on=["lob_code", "group_code"], how="left")
sp = sp[sp["flag"].isna()]

lags = (sp[sp["development_lag"].isin([1, 10])]
        .groupby(["lob_name", "development_lag"])["incurred_loss"].sum()
        .unstack("development_lag"))
lags.columns = ["incurred_lag1", "incurred_lag10"]
lags["development"] = lags["incurred_lag10"] - lags["incurred_lag1"]
lags["development_pct"] = lags["development"] / lags["incurred_lag1"]
lags = lags.sort_values("development_pct", ascending=False)
lags.to_csv(config.OUTPUTS_DIR / "variance_reserve_development.csv")

with pd.option_context("display.float_format", "{:,.3f}".format):
    print(lags.to_string())

worst_line, best_line = lags.index[0], lags.index[-1]
commentary.append(
    f"**Reserve development (industry, Schedule P, accident years 1998-2007):** "
    f"{worst_line} showed the most adverse development, with incurred losses "
    f"{lags.loc[worst_line, 'development_pct']:+.1%} from the first year-end estimate to ten years later. "
    f"{best_line} was the most favorable at {lags.loc[best_line, 'development_pct']:+.1%}. "
    f"Lines with long-tailed claims need larger, more uncertain reserves."
)

# ===========================================================================
# COMMENTARY
# ===========================================================================
text = "# Variance Commentary: 2025\n\n" \
       "_Draft generated by `src/06_variance.py`. Numbers are calculated; the analyst " \
       "reviews and adds context before sharing._\n\n" \
       + "\n\n".join(f"- {c}" for c in commentary) + "\n"
(config.OUTPUTS_DIR / "variance_commentary.md").write_text(text, encoding="utf-8")

print("\n=== DRAFT COMMENTARY ===\n")
print(text)