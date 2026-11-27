"""
Data loaders: one function per source system.

Each function reads a raw file, renames its columns to our standard
names (from config.py), and returns a pandas DataFrame (a table).
The raw files themselves are never changed.
"""
import pandas as pd

import config


def load_schedule_p():
    """Read all six CAS Schedule P files and stack them into one table."""
    tables = []

    # Loop through the dictionary in config: prefix = "ppauto", etc.
    for prefix, (lob_code, lob_name) in config.SCHEDULE_P_FILES.items():

        # Find the file that starts with this prefix, e.g. ppauto_pos_98-07.csv
        matches = list(config.RAW_DIR.glob(f"{prefix}*.csv"))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"Expected 1 file starting with '{prefix}' in raw/, found {len(matches)}"
            )
        path = matches[0]

        df = pd.read_csv(path)                              # read the CSV into a table
        df = df.rename(columns=config.SCHEDULE_P_COLUMNS)   # standard column names

        # The files don't say which line they are, so we add that ourselves
        df.insert(0, "lob_code", lob_code)
        df.insert(1, "lob_name", lob_name)

        tables.append(df)

    # Stack the six tables on top of each other into one
    return pd.concat(tables, ignore_index=True)


def load_iowa():
    """Read the Iowa Insurance Division premiums and losses file."""
    df = pd.read_csv(config.IOWA_FILE)
    df = df.rename(columns=config.IOWA_COLUMNS)
    return df


def load_policies():
    """Read the policy file. Plays the role of the UNDERWRITING system."""
    df = pd.read_csv(config.POLICY_FILE)
    df = df.rename(columns=config.POLICY_COLUMNS)

    # Policy IDs are stored as decimals in the raw file (1.0, 3.0, ...).
    # An ID should be a whole number, so convert it.
    df["policy_id"] = df["policy_id"].astype("int64")
    return df


def load_claims():
    """Read the claims file. Plays the role of the CLAIMS system."""
    df = pd.read_csv(config.CLAIMS_FILE)
    df = df.rename(columns=config.CLAIMS_COLUMNS)
    df["policy_id"] = df["policy_id"].astype("int64")

    # The raw file has no claim number, so we give each claim one: 1, 2, 3 ...
    df.insert(0, "claim_id", range(1, len(df) + 1))
    return df


# A lookup of every loader by name, so other scripts can loop through them
LOADERS = {
    "schedule_p": load_schedule_p,
    "iowa": load_iowa,
    "policies": load_policies,
    "claims": load_claims,
}