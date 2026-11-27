"""Investigation of PC-05: policies with claim_count > 0 but no claim records."""
import pandas as pd

import config
import load

policies = load.load_policies()
claims = load.load_claims()
missing = pd.read_csv(config.OUTPUTS_DIR / "dq_failures" / "PC-05.csv")

# All policies that SAY they had a claim - the group we compare against
with_claims = policies[policies["claim_count"] > 0]

# --- Q1: How big? ---------------------------------------------------------
print("=== Q1: SIZE ===")
print("Policies reporting claims:", len(with_claims))
print("Of those, missing claim records:", len(missing))
print("Percent affected:", round(len(missing) / len(with_claims) * 100, 1), "%")
print("Total claims missing:", missing["claim_count"].sum())

# --- Q2: What does it look like? ------------------------------------------
print("\n=== Q2: CLAIMS PER POLICY ===")
print(missing["claim_count"].value_counts().sort_index())

# --- Q3: Where is it? -----------------------------------------------------
# Put policy IDs into buckets of 1 million and count each group
buckets = [0, 1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000, 7_000_000]
comparison = pd.DataFrame({
    "all_policies_with_claims": pd.cut(with_claims["policy_id"], buckets).value_counts(),
    "missing_claim_records": pd.cut(missing["policy_id"], buckets).value_counts(),
}).sort_index()
print("\n=== Q3: BY POLICY ID RANGE ===")
print(comparison)

print("\n=== Q3: TOP REGIONS (share) ===")
print("Missing:     ", missing["region"].value_counts(normalize=True).head(3).round(3).to_dict())
print("All w/claims:", with_claims["region"].value_counts(normalize=True).head(3).round(3).to_dict())

# --- Q4: What does it affect? ---------------------------------------------
avg_claim = claims["claim_amount"].mean()
est_missing = missing["claim_count"].sum() * avg_claim
print("\n=== Q4: ESTIMATED IMPACT ===")
print(f"Average claim amount:          €{avg_claim:,.0f}")
print(f"Total claims in claims file:   €{claims['claim_amount'].sum():,.0f}")
print(f"Estimated missing claim value: €{est_missing:,.0f}")