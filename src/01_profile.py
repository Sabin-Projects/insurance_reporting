"""
For every column in every source it records nulls, distinct values,
min/max, negatives and zeros. Results are saved to outputs/.
"""
import pandas as pd

import config
import load

# Make sure the output folders exist (does nothing if they already do)
config.OUTPUTS_DIR.mkdir(exist_ok=True)
config.PROCESSED_DIR.mkdir(exist_ok=True)


def profile_table(df):
    """Return one row per column describing what's in that column."""
    rows = []

    for col in df.columns:
        values = df[col]
        is_number = pd.api.types.is_numeric_dtype(values)

        rows.append({
            "column": col,
            "data_type": str(values.dtype),
            "non_null": values.notna().sum(),
            "nulls": values.isna().sum(),
            "pct_null": round(values.isna().mean() * 100, 2),
            "distinct": values.nunique(),
            # min/max/negatives/zeros only make sense for numbers
            "min": values.min() if is_number else None,
            "max": values.max() if is_number else None,
            "negatives": (values < 0).sum() if is_number else None,
            "zeros": (values == 0).sum() if is_number else None,
            "examples": ", ".join(str(v) for v in values.dropna().unique()[:5]),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Profile each source and save the results
# ---------------------------------------------------------------------------
summary = []

for name, loader in load.LOADERS.items():
    print(f"Profiling {name} ...")
    df = loader()

    # Column-by-column profile -> outputs/profile_<name>.csv
    profile = profile_table(df)
    profile.to_csv(config.OUTPUTS_DIR / f"profile_{name}.csv", index=False)

    # Save the standardized table so later steps can start from it
    df.to_csv(config.PROCESSED_DIR / f"{name}.csv", index=False)

    # One summary line per source
    summary.append({
        "source": name,
        "rows": len(df),
        "columns": df.shape[1],
        "total_nulls": df.isna().sum().sum(),
        "duplicate_rows": df.duplicated().sum(),
    })

summary = pd.DataFrame(summary)
summary.to_csv(config.OUTPUTS_DIR / "profile_summary.csv", index=False)

print("\n=== SUMMARY ===")
print(summary.to_string(index=False))

# ---------------------------------------------------------------------------
# A few business questions worth answering up front
# ---------------------------------------------------------------------------
sp = load.load_schedule_p()
print("\n=== SCHEDULE P: coverage by line of business ===")
coverage = sp.groupby("lob_name").agg(
    companies=("group_code", "nunique"),
    first_year=("accident_year", "min"),
    last_year=("accident_year", "max"),
    rows=("group_code", "size"),
)
print(coverage.to_string())

iowa = load.load_iowa()
print(f"\n=== IOWA: years in file: {sorted(iowa['data_year'].unique().tolist())} ===")

spotlight = iowa[
    iowa["company_name"].str.contains(config.SPOTLIGHT_COMPANY, case=False)
    & (iowa["premiums_written"] != 0)
]
print(f"\n=== {config.SPOTLIGHT_COMPANY.upper()} in Iowa (lines with premium) ===")
print(spotlight[["line_of_insurance", "premiums_written", "losses_paid"]].to_string(index=False))

print(f"\nDone. Profiles saved to {config.OUTPUTS_DIR}")