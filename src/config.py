"""
Project settings: file locations, line-of-business names, and constants.
Every other script imports from this file.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. FOLDER LOCATIONS
# ---------------------------------------------------------------------------
# __file__ is the location of this file (src/config.py).
# .resolve() turns it into a full path, e.g.
#   /Users/you/Desktop/insurance_reporting/src/config.py
# .parent goes up one folder (to src/), .parent again goes up to the project.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_ROOT / "raw"              # original downloads, never edited
PROCESSED_DIR = PROJECT_ROOT / "processed"  # cleaned tables our code creates
OUTPUTS_DIR = PROJECT_ROOT / "outputs"      # reports and check results

# ---------------------------------------------------------------------------
# 2. RAW FILE NAMES
# ---------------------------------------------------------------------------
# The six CAS Schedule P files.
# Key   = start of the file name
# Value = (NAIC Schedule P line code, readable line-of-business name)
SCHEDULE_P_FILES = {
    "ppauto":   ("B",  "Private Passenger Auto Liability"),
    "comauto":  ("C",  "Commercial Auto Liability"),
    "wkcomp":   ("D",  "Workers' Compensation"),
    "medmal":   ("F2", "Medical Malpractice - Claims Made"),
    "othliab":  ("H1", "Other Liability - Occurrence"),
    "prodliab": ("R1", "Products Liability - Occurrence"),
}

IOWA_FILE = RAW_DIR / "iowa_property_casualty_insurance_premiums_and_losses_987_rows.csv"
POLICY_FILE = RAW_DIR / "freMTPL2freq.csv"   # plays the UNDERWRITING system
CLAIMS_FILE = RAW_DIR / "freMTPL2sev.csv"    # plays the CLAIMS system

# ---------------------------------------------------------------------------
# 3. STANDARD COLUMN NAMES
# ---------------------------------------------------------------------------
# Raw files use names like "EarnedPremNet". We rename them to clear,
# consistent names so every report uses the same vocabulary.
# Format:  "raw name": "our standard name"
SCHEDULE_P_COLUMNS = {
    "GRCODE": "group_code",
    "GRNAME": "group_name",
    "AccidentYear": "accident_year",
    "DevelopmentYear": "development_year",
    "DevelopmentLag": "development_lag",
    "IncurredLosses": "incurred_loss",
    "CumPaidLoss": "cum_paid_loss",
    "BulkLoss": "bulk_ibnr_reserve",
    "EarnedPremDIR": "earned_prem_direct",
    "EarnedPremCeded": "earned_prem_ceded",
    "EarnedPremNet": "earned_prem_net",
    "Single": "single_entity_flag",
    "PostedReserves2007": "posted_reserves_2007",
}

IOWA_COLUMNS = {
    "cname": "company_name",
    "cstate": "domicile_state",
    "description": "line_of_insurance",
    "co_code": "naic_company_code",
}

POLICY_COLUMNS = {
    "IDpol": "policy_id",
    "ClaimNb": "claim_count",
    "Exposure": "exposure_years",
    "VehPower": "vehicle_power",
    "VehAge": "vehicle_age",
    "DrivAge": "driver_age",
    "BonusMalus": "bonus_malus",
    "VehBrand": "vehicle_brand",
    "VehGas": "fuel_type",        # we'll use this as "policy type"
    "Area": "area_code",
    "Density": "pop_density",
    "Region": "region",           # we'll use this as "geographic segment"
}

CLAIMS_COLUMNS = {
    "IDpol": "policy_id",
    "ClaimAmount": "claim_amount",
}

# ---------------------------------------------------------------------------
# 4. OTHER SETTINGS
# ---------------------------------------------------------------------------
# A fixed "seed" makes random numbers repeat exactly every run, so anyone
# rerunning the project gets the same results. (Used in Step 6.)
RANDOM_SEED = 42

# The simulated reporting window for monthly reports (Step 6 onward)
REPORT_START = "2024-01-01"
REPORT_MONTHS = 24

# The company we spotlight in the Iowa data
SPOTLIGHT_COMPANY = "Jewelers Mutual"

# ---------------------------------------------------------------------------
# 5. DATA QUALITY DECISIONS (from docs/data_quality_log.md)
# ---------------------------------------------------------------------------
# PC-02: exposure above 1 year is capped at 1 year for premium calculations
EXPOSURE_CAP = 1.0

# PC-05: claims are only complete for policy IDs above this number.
# Loss reporting uses only policies where claims_complete is True.
CLAIMS_COMPLETE_MIN_ID = 1_000_000

# ---------------------------------------------------------------------------
# 6. SIMULATION ASSUMPTIONS (Step 6). Every value here is documented in
#    docs/assumptions.md. Change a number here and rerun to test sensitivity.
# ---------------------------------------------------------------------------
# Premium = base rate x rating factors x exposure
BASE_RATE = 375.0          # euros per policy-year for an average risk
                           # (set so the expected loss ratio is about 70%)

AREA_FACTORS = {"A": 0.85, "B": 0.95, "C": 1.00, "D": 1.10, "E": 1.20, "F": 1.30}
FUEL_FACTORS = {"Regular": 1.00, "Diesel": 1.05}
POWER_STEP = 0.03          # +3% premium per vehicle power level above 6

# Expenses
COMMISSION_RATE = 0.15     # 15% of written premium paid to agents
ADMIN_COST_PER_POLICY = 20.0   # euros to issue and service one policy

# Claims: days between the accident and the claim being reported
MAX_REPORT_LAG_DAYS = 45

# ---------------------------------------------------------------------------
# 7. REPORTING (Step 7)
# ---------------------------------------------------------------------------
# IA-03: correct the misspellings in the Iowa source's line names
LINE_NAME_FIXES = {"Commerical": "Commercial", "Occcurence": "Occurrence"}

# Schedule P is reported "as of" this annual statement year
SCHEDULE_P_AS_OF_YEAR = 2007

# The Iowa line that covers jewelry
SPOTLIGHT_LINE = "Inland Marine"
# ---------------------------------------------------------------------------
# 8. RECONCILIATION (Step 8)
# Errors deliberately planted in the simulated general ledger, so the
# reconciliation has real breaks to find. Documented in docs/assumptions.md.
# ---------------------------------------------------------------------------
GL_PREMIUM_CUTOFF_ERRORS = 20   # policies booked in the month AFTER they were written
GL_DUPLICATE_CLAIMS = 2         # claims posted to the ledger twice
GL_MISSING_CLAIMS = 3           # claims never posted to the ledger
GL_DECIMAL_ERRORS = 2           # claims posted at 10x the correct amount
# ---------------------------------------------------------------------------
# 9. VARIANCE ANALYSIS (Step 9)
# ---------------------------------------------------------------------------
# A claim at or above this amount is a "large loss", analysed separately
LARGE_LOSS_THRESHOLD = 100_000

# 2025 budget, set from 2024 actuals for each region:
BUDGET_POLICY_GROWTH = 0.02        # plan to write 2% more policies
BUDGET_AVG_PREMIUM_CHANGE = 0.03   # plan a 3% rate increase
BUDGET_LOSS_RATIO = 0.65
BUDGET_EXPENSE_RATIO = 0.30