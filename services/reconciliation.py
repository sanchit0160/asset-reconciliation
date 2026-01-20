import os
import pandas as pd
from datetime import datetime
from database import engine
from config import ITAM_DIR, ACTIVE_DIR

CURRENT_ITAM_FILE = None
CURRENT_ACTIVE_FILE = None
LAST_RECONCILED_AT = None


def normalize_columns(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )
    return df


def reconcile(itam_file: str, active_file: str):
    global CURRENT_ITAM_FILE, CURRENT_ACTIVE_FILE, LAST_RECONCILED_AT

    itam_df = pd.read_csv(os.path.join(ITAM_DIR, itam_file))
    active_df = pd.read_csv(os.path.join(ACTIVE_DIR, active_file))

    itam_df = normalize_columns(itam_df)
    active_df = normalize_columns(active_df)

    itam_df["ip_address"] = itam_df["ip_address"].astype(str).str.strip()
    active_df["ip_address"] = active_df["ip_address"].astype(str).str.strip()

    itam_df["status"] = itam_df["ip_address"].isin(
        active_df["ip_address"]
    ).map({True: "Integrated", False: "Pending"})

    LAST_RECONCILED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    CURRENT_ITAM_FILE = itam_file
    CURRENT_ACTIVE_FILE = active_file

    itam_df["itam_file"] = itam_file
    itam_df["active_file"] = active_file
    itam_df["reconciled_at"] = LAST_RECONCILED_AT

    with engine.begin() as conn:
        itam_df.to_sql(
            "reconciliation_status",
            conn,
            if_exists="replace",
            index=False
        )
