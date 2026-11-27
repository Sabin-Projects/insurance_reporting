"""
Insurance Reporting Dashboard.

Run from the project folder:
    streamlit run app/dashboard.py

The dashboard only DISPLAYS results. All calculations happen in the src/
scripts, which save their results to outputs/ and processed/. Run them
first, in order (01 to 06), whenever the data or assumptions change.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Let the dashboard use config.py from the src/ folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import config  # noqa: E402

st.set_page_config(page_title="P&C Insurance Reporting", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@st.cache_data
def read(name, folder="outputs"):
    """Read a result file once and keep it in memory between clicks."""
    base = config.OUTPUTS_DIR if folder == "outputs" else config.PROCESSED_DIR
    path = base / name
    if not path.exists():
        st.error(f"Missing {folder}/{name}. Run the src/ scripts 01 to 06 first.")
        st.stop()
    return pd.read_csv(path)


def eur(x):
    sign = "-" if x < 0 else ""
    return f"{sign}€{abs(x):,.0f}"


def usd(x):
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def pct(x):
    return f"{x:.1%}"


monthly = read("report_monthly_product.csv")
monthly["year"] = monthly["month"].str[:4]


# ===========================================================================
# PAGE 1: EXECUTIVE SUMMARY
# ===========================================================================
def executive_summary():
    st.title("Executive Summary")
    st.caption("Claims-complete policies (data quality decision PC-05). Calendar years 2024–2025.")

    yearly = monthly.groupby("year")[["written_premium", "earned_premium", "incurred_loss",
                                      "total_expense"]].sum()
    yearly["loss_ratio"] = yearly["incurred_loss"] / yearly["earned_premium"]
    yearly["expense_ratio"] = yearly["total_expense"] / yearly["written_premium"]
    yearly["combined_ratio"] = yearly["loss_ratio"] + yearly["expense_ratio"]
    cur, prev = yearly.loc["2025"], yearly.loc["2024"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Written premium 2025", eur(cur["written_premium"]),
              f"{cur['written_premium'] / prev['written_premium'] - 1:+.1%} vs 2024")
    c2.metric("Earned premium 2025", eur(cur["earned_premium"]),
              f"{cur['earned_premium'] / prev['earned_premium'] - 1:+.1%} vs 2024")
    # For ratios, going DOWN is good, so delta_color="inverse" shows a decrease in green
    c3.metric("Loss ratio", pct(cur["loss_ratio"]),
              f"{(cur['loss_ratio'] - prev['loss_ratio']) * 100:+.1f} pts", delta_color="inverse")
    c4.metric("Expense ratio", pct(cur["expense_ratio"]),
              f"{(cur['expense_ratio'] - prev['expense_ratio']) * 100:+.1f} pts", delta_color="inverse")
    c5.metric("Combined ratio", pct(cur["combined_ratio"]),
              f"{(cur['combined_ratio'] - prev['combined_ratio']) * 100:+.1f} pts", delta_color="inverse")

    by_month = monthly.groupby("month")[["earned_premium", "incurred_loss", "written_premium"]].sum()
    by_month["loss_ratio"] = by_month["incurred_loss"] / by_month["earned_premium"]

    left, right = st.columns(2)
    with left:
        fig = px.bar(by_month.reset_index(), x="month", y=["written_premium", "earned_premium"],
                     barmode="group", title="Written vs earned premium by month",
                     labels={"value": "€", "variable": ""})
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.line(by_month.reset_index(), x="month", y="loss_ratio", markers=True,
                      title="Monthly loss ratio")
        fig.add_hline(y=config.BUDGET_LOSS_RATIO, line_dash="dash",
                      annotation_text=f"Budget {pct(config.BUDGET_LOSS_RATIO)}")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Key messages")
    commentary = (config.OUTPUTS_DIR / "variance_commentary.md")
    if commentary.exists():
        st.markdown(commentary.read_text(encoding="utf-8").split("\n", 2)[2])


# ===========================================================================
# PAGE 2: PRODUCT PERFORMANCE
# ===========================================================================
def product_performance():
    st.title("Product Performance")
    tab_product, tab_lob = st.tabs(["Monthly product report", "Line of business (Schedule P)"])

    with tab_product:
        st.caption("By geographic segment (region) and policy type (fuel type). Claims-complete basis.")
        f1, f2, f3 = st.columns(3)
        years = f1.multiselect("Year", sorted(monthly["year"].unique()), default=["2025"])
        types = f2.multiselect("Policy type", sorted(monthly["fuel_type"].unique()),
                               default=sorted(monthly["fuel_type"].unique()))
        regions = f3.multiselect("Region (blank = all)", sorted(monthly["region"].unique()))

        view = monthly[monthly["year"].isin(years) & monthly["fuel_type"].isin(types)]
        if regions:
            view = view[view["region"].isin(regions)]

        if view.empty:
            st.warning("No data for this selection.")
        else:
            seg = view.groupby(["region", "fuel_type"])[
                ["policies_written", "written_premium", "earned_premium", "claim_count",
                 "incurred_loss", "total_expense"]].sum()
            seg["loss_ratio"] = seg["incurred_loss"] / seg["earned_premium"]
            seg["expense_ratio"] = seg["total_expense"] / seg["written_premium"]
            seg["combined_ratio"] = seg["loss_ratio"] + seg["expense_ratio"]
            seg = seg.sort_values("written_premium", ascending=False)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Policies written", f"{seg['policies_written'].sum():,.0f}")
            k2.metric("Written premium", eur(seg["written_premium"].sum()))
            k3.metric("Loss ratio", pct(seg["incurred_loss"].sum() / seg["earned_premium"].sum()))
            k4.metric("Claims", f"{seg['claim_count'].sum():,.0f}")

            by_region = seg.groupby("region")[["written_premium", "earned_premium", "incurred_loss"]].sum()
            by_region["loss_ratio"] = by_region["incurred_loss"] / by_region["earned_premium"]
            fig = px.bar(by_region.reset_index().sort_values("written_premium"),
                         x="written_premium", y="region", orientation="h", color="loss_ratio",
                         color_continuous_scale="RdYlGn_r", title="Written premium by region (colour = loss ratio)")
            fig.update_layout(height=600)
            st.plotly_chart(fig, width="stretch")

            st.dataframe(
                seg.reset_index(), width="stretch", hide_index=True,
                column_config={
                    "written_premium": st.column_config.NumberColumn(format="euro"),
                    "earned_premium": st.column_config.NumberColumn(format="euro"),
                    "incurred_loss": st.column_config.NumberColumn(format="euro"),
                    "total_expense": st.column_config.NumberColumn(format="euro"),
                    "loss_ratio": st.column_config.NumberColumn(format="percent"),
                    "expense_ratio": st.column_config.NumberColumn(format="percent"),
                    "combined_ratio": st.column_config.NumberColumn(format="percent"),
                },
            )

    with tab_lob:
        lob = read("report_line_of_business.csv")
        st.caption("NAIC Schedule P, valued at the 2007 annual statement. $ thousands. "
                   "Companies with negative paid losses excluded (SP-03).")
        fig = px.line(lob, x="accident_year", y="net_loss_ratio", color="lob_name", markers=True,
                      title="Net loss ratio by accident year")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(lob, width="stretch", hide_index=True,
                     column_config={c: st.column_config.NumberColumn(format="percent")
                                    for c in ["pct_ceded", "net_loss_ratio", "paid_to_incurred"]})


# ===========================================================================
# PAGE 3: VARIANCE ANALYSIS
# ===========================================================================
def variance_analysis():
    st.title("Variance Analysis")

    st.subheader("Written premium: 2025 actual vs budget")
    prem = read("variance_premium_by_region.csv")
    budget, actual = prem["budget_premium"].sum(), prem["actual_premium"].sum()
    volume, rate = prem["volume_effect"].sum(), prem["rate_effect"].sum()
    fig = go.Figure(go.Waterfall(
        x=["Budget", "Volume effect", "Rate effect", "Actual"],
        measure=["absolute", "relative", "relative", "total"],
        y=[budget, volume, rate, actual],
        text=[eur(v) for v in [budget, volume, rate, actual]],
        textposition="outside",
    ))
    fig.update_yaxes(range=[min(budget, actual) * 0.9, max(budget, actual) * 1.03])
    fig.update_layout(title="Budget to actual: volume and rate", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(prem[["region", "budget_premium", "actual_premium", "variance", "volume_effect",
                       "rate_effect", "variance_pct"]], width="stretch", hide_index=True,
                 column_config={"variance_pct": st.column_config.NumberColumn(format="percent"),
                                **{c: st.column_config.NumberColumn(format="euro")
                                   for c in ["budget_premium", "actual_premium", "variance",
                                             "volume_effect", "rate_effect"]}})

    st.subheader("Loss ratio: attritional vs large losses")
    lr = read("variance_loss_ratio.csv")
    lr["year"] = lr["year"].astype(str)
    fig = px.bar(lr, x="year", y=["attritional_lr", "large_lr"],
                 title=f"Loss ratio split (large = claims ≥ {eur(config.LARGE_LOSS_THRESHOLD)})",
                 labels={"value": "Loss ratio", "variable": ""})
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Industry reserve development (Schedule P)")
    dev = read("variance_reserve_development.csv")
    fig = px.bar(dev.sort_values("development_pct"), x="development_pct", y="lob_name",
                 orientation="h", color="development_pct", color_continuous_scale="RdYlGn_r",
                 title="Incurred losses: change from year 1 to year 10 (positive = adverse)")
    fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Commentary")
    st.markdown((config.OUTPUTS_DIR / "variance_commentary.md").read_text(encoding="utf-8").split("\n", 2)[2])


# ===========================================================================
# PAGE 4: RECONCILIATION
# ===========================================================================
def reconciliation():
    st.title("Reconciliation")
    st.caption("Underwriting system vs claims system vs general ledger.")

    summary = read("recon_summary.csv")
    errors = summary[summary["type"] == "Error"]
    k1, k2, k3 = st.columns(3)
    k1.metric("Reconciling items", len(summary))
    k2.metric("GL errors to correct", f"{int(errors['count'].sum())} entries")
    k3.metric("Net GL error", eur(errors["amount"].sum()))
    st.dataframe(summary, width="stretch", hide_index=True,
                 column_config={"amount": st.column_config.NumberColumn(format="euro")})

    left, right = st.columns(2)
    with left:
        r1 = read("recon_premium_monthly.csv")
        fig = px.bar(r1, x="month", y="difference", title="R1 Premium: GL minus underwriting, by month")
        st.plotly_chart(fig, width="stretch")
        st.caption("Cutoff errors move premium into the next month; they net to zero over time.")
    with right:
        r2 = read("recon_losses_monthly.csv")
        r2 = r2[r2["month"] <= "2025-12"]
        fig = px.line(r2, x="month", y=["claims_system", "general_ledger"], markers=True,
                      title="R2 Losses: claims system (accident month) vs GL (report month)")
        st.plotly_chart(fig, width="stretch")
        st.caption("The GL line runs about a month behind: claims are booked when reported.")

    st.subheader("Claim-level breaks")
    detail = read("recon_claims_detail.csv")
    status = st.selectbox("Status", sorted(detail["status"].unique()))
    rows = detail[detail["status"] == status]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.download_button("Download these rows (CSV)", rows.to_csv(index=False),
                       file_name=f"recon_{status.split(':')[0].lower().replace(' ', '_')}.csv")


# ===========================================================================
# PAGE 5: DATA QUALITY
# ===========================================================================
def data_quality():
    st.title("Data Quality")
    dq = read("dq_results.csv")

    k1, k2, k3 = st.columns(3)
    k1.metric("Rules run", len(dq))
    k2.metric("Passed", int((dq["status"] == "PASS").sum()))
    k3.metric("High-severity failures", int(((dq["status"] == "FAIL") & (dq["severity"] == "High")).sum()))

    def colour(row):
        c = "#d4edda" if row["status"] == "PASS" else ("#f8d7da" if row["severity"] == "High" else "#fff3cd")
        return [f"background-color: {c}; color: black"] * len(row)

    st.dataframe(dq.style.apply(colour, axis=1), width="stretch", hide_index=True)

    st.subheader("Inspect failing rows")
    failed = dq[dq["status"] == "FAIL"]
    rule = st.selectbox("Rule", failed["rule_id"] + " — " + failed["description"])
    rule_id = rule.split(" — ")[0]
    rows = pd.read_csv(config.OUTPUTS_DIR / "dq_failures" / f"{rule_id}.csv")
    st.write(f"{len(rows):,} failing rows")
    st.dataframe(rows.head(1000), width="stretch", hide_index=True)
    st.download_button("Download all failing rows (CSV)", rows.to_csv(index=False),
                       file_name=f"{rule_id}_failures.csv")


# ===========================================================================
# PAGE 6: REGULATORY & MARKET
# ===========================================================================
def regulatory_market():
    st.title("Regulatory & Market")
    tab_iowa, tab_spot = st.tabs(["Iowa state report (2019)", f"{config.SPOTLIGHT_COMPANY} spotlight"])

    with tab_iowa:
        lines = read("report_iowa_lines.csv")
        st.caption("Iowa Insurance Division, direct business in Iowa, 2019. Built from annual statement state pages.")
        top = lines[lines["premiums_written"] > 0].head(15)
        fig = px.bar(top.sort_values("premiums_written"), x="premiums_written", y="line_of_insurance",
                     orientation="h", color="paid_loss_ratio", color_continuous_scale="RdYlGn_r",
                     title="Top 15 lines by premium written (colour = paid loss ratio)")
        fig.update_layout(height=550)
        st.plotly_chart(fig, width="stretch")
        st.dataframe(lines, width="stretch", hide_index=True,
                     column_config={"paid_loss_ratio": st.column_config.NumberColumn(format="percent"),
                                    "implied_tax_rate": st.column_config.NumberColumn(format="percent")})

    with tab_spot:
        spot = read("report_spotlight.csv")
        line = spot[spot["line_of_insurance"] == config.SPOTLIGHT_LINE]
        if not line.empty:
            r = line.iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(f"{config.SPOTLIGHT_LINE} premium", usd(r["premiums_written_company"]))
            k2.metric("Share of company's Iowa premium",
                      pct(r["premiums_written_company"] / spot["premiums_written_company"].sum()))
            k3.metric("Company paid loss ratio", pct(r["company_paid_lr"]))
            k4.metric("Iowa market paid loss ratio", pct(r["market_paid_lr"]))
        fig = px.bar(spot, x="line_of_insurance", y=["company_paid_lr", "market_paid_lr"], barmode="group",
                     title="Paid loss ratio: company vs Iowa market",
                     labels={"value": "Paid loss ratio", "variable": ""})
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(spot, width="stretch", hide_index=True)
        st.caption("Paid loss ratio = losses paid ÷ premiums written. Iowa data has no earned premium or reserves.")


# ===========================================================================
# NAVIGATION: a bar of page links across the top
# Each page is one of the functions above. Only the selected page runs.
# ===========================================================================
pages = [
    st.Page(executive_summary, title="Executive Summary", icon=":material/dashboard:", default=True),
    st.Page(product_performance, title="Product Performance", icon=":material/bar_chart:"),
    st.Page(variance_analysis, title="Variance Analysis", icon=":material/waterfall_chart:"),
    st.Page(reconciliation, title="Reconciliation", icon=":material/balance:"),
    st.Page(data_quality, title="Data Quality", icon=":material/fact_check:"),
    st.Page(regulatory_market, title="Regulatory & Market", icon=":material/account_balance:"),
]
navigation = st.navigation(pages, position="top")
navigation.run()

st.divider()
st.caption(
    "Portfolio project: P&C insurance financial reporting. Policy and claims data are "
    "freMTPL2 with simulated premiums and dates; industry data is NAIC Schedule P (CAS); "
    "state data is the Iowa Insurance Division."
)