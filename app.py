from flask import Flask, render_template, request, redirect, session
from sqlalchemy import create_engine, text
import pandas as pd
import os
from datetime import datetime


# ==========================================================
# APP CONFIG
# ==========================================================
app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = f"sqlite:///{BASE_DIR}/reconciliation.db"
engine = create_engine(DB_PATH, future=True)

ITAM_DIR = os.path.join(BASE_DIR, "data", "itam")
ACTIVE_DIR = os.path.join(BASE_DIR, "data", "active_services")

CURRENT_ITAM_FILE = None
CURRENT_ACTIVE_FILE = None
LAST_RECONCILED_AT = None

# ==========================================================
# UTILITIES
# ==========================================================
def list_csv_files(folder):
    return sorted(
        [f for f in os.listdir(folder) if f.endswith(".csv")],
        key=lambda x: os.path.getmtime(os.path.join(folder, x)),
        reverse=True
    )

def get_latest_file(folder):
    files = list_csv_files(folder)
    return files[0] if files else None

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )
    return df

def normalize_itam_id(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure a single canonical 'itam_id' column exists
    """
    aliases = ["itamid", "asset_id", "assetid", "itam_id"]

    for col in aliases:
        if col in df.columns:
            df["itam_id"] = df[col].astype(str).str.strip()
            break

    if "itam_id" not in df.columns:
        raise ValueError("ITAM file missing ITAM ID column")

    return df

def require_login():
    return "user" in session

# ==========================================================
# RECONCILIATION LOGIC
# ==========================================================
def reconcile(itam_file: str, active_file: str) -> None:
    global CURRENT_ITAM_FILE, CURRENT_ACTIVE_FILE, LAST_RECONCILED_AT

    itam_df = pd.read_csv(os.path.join(ITAM_DIR, itam_file))
    active_df = pd.read_csv(os.path.join(ACTIVE_DIR, active_file))

    itam_df = normalize_columns(itam_df)
    active_df = normalize_columns(active_df)

    # Normalize ITAM ID
    itam_df = normalize_itam_id(itam_df)

    required_cols = {
        "itam_id",
        "hostname",
        "ip_address",
        "department",
        "region",
        "environment"
    }

    missing = required_cols - set(itam_df.columns)
    if missing:
        raise ValueError(f"ITAM file missing columns: {missing}")

    itam_df["ip_address"] = itam_df["ip_address"].astype(str).str.strip()
    active_df["ip_address"] = active_df["ip_address"].astype(str).str.strip()

    # Integration logic
    itam_df["status"] = itam_df["ip_address"].isin(
        active_df["ip_address"]
    ).map({True: "Integrated", False: "Pending"})

    LAST_RECONCILED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    CURRENT_ITAM_FILE = itam_file
    CURRENT_ACTIVE_FILE = active_file

    itam_df["itam_file"] = itam_file
    itam_df["active_file"] = active_file
    itam_df["reconciled_at"] = LAST_RECONCILED_AT

    # Persist full dataset
    with engine.begin() as conn:
        itam_df[
            [
                "itam_id",
                "hostname",
                "ip_address",
                "environment",
                "department",
                "region",
                "status",
                "itam_file",
                "active_file",
                "reconciled_at"
            ]
        ].to_sql(
            "reconciliation_status",
            conn,
            if_exists="replace",
            index=False
        )

# ==========================================================
# INITIAL LOAD
# ==========================================================
def initial_load():
    itam = get_latest_file(ITAM_DIR)
    active = get_latest_file(ACTIVE_DIR)
    if itam and active:
        reconcile(itam, active)

initial_load()

# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def root():
    return redirect("/login")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    # Always load available departments
    with engine.connect() as conn:
        departments = conn.execute(
            text("""
                SELECT DISTINCT department
                FROM reconciliation_status
                ORDER BY department
            """)
        ).scalars().all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        department = request.form.get("department", "").strip().upper()

        # ================= ADMIN LOGIN =================
        if username == "admin" and password == "admin123":
            session["user"] = {
                "username": username,
                "role": "ADMIN"
            }
            return redirect("/dashboard")

        # ================= DEPARTMENT LOGIN =================
        if username and password and department:
            with engine.connect() as conn:
                region = conn.execute(
                    text("""
                        SELECT DISTINCT region
                        FROM reconciliation_status
                        WHERE department = :dept
                        LIMIT 1
                    """),
                    {"dept": department}
                ).scalar()

            if not region:
                error = "No region found for selected department"
            else:
                session["user"] = {
                    "username": username,
                    "role": "DEPT",
                    "department": department,
                    "region": region
                }
                return redirect("/dashboard")
        else:
            error = "All fields are required"

    return render_template(
        "login.html",
        departments=departments,
        error=error
    )



# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect("/login")

    user = session["user"]

    # ================= ADMIN =================
    if user["role"] == "ADMIN":
        with engine.connect() as conn:
            summary = conn.execute(text("""
                SELECT region,
                       department,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status='Integrated' THEN 1 ELSE 0 END) AS integrated,
                       SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending
                FROM reconciliation_status
                GROUP BY region, department
                ORDER BY region, department
            """)).mappings().all()

        return render_template(
            "admin_dashboard.html",
            summary=summary,
            regions=sorted({r["region"] for r in summary}),
            itam_files=list_csv_files(ITAM_DIR),
            active_files=list_csv_files(ACTIVE_DIR),
            itam_file=CURRENT_ITAM_FILE,
            active_file=CURRENT_ACTIVE_FILE,
            reconciled_at=LAST_RECONCILED_AT
        )

    # ================= DEPARTMENT =================
    region = user["region"]
    department = user["department"]

    with engine.connect() as conn:
        pending = conn.execute(text("""
            SELECT itam_id, hostname, ip_address, environment, department, region
            FROM reconciliation_status
            WHERE region=:region
              AND department=:dept
              AND status='Pending'
            ORDER BY environment, hostname
        """), {"region": region, "dept": department}).mappings().all()

        integrated = conn.execute(text("""
            SELECT itam_id, hostname, ip_address, environment, department, region
            FROM reconciliation_status
            WHERE region=:region
              AND department=:dept
              AND status='Integrated'
            ORDER BY environment, hostname
        """), {"region": region, "dept": department}).mappings().all()

    return render_template(
        "dept_dashboard.html",
        region=region,
        department=department,
        pending=pending,
        integrated=integrated
    )

# ---------------- ADMIN DRILLDOWN ----------------
@app.route("/region/<region>/department/<department>")
def region_department_view(region, department):
    if not require_login() or session["user"]["role"] != "ADMIN":
        return redirect("/dashboard")

    with engine.connect() as conn:
        pending = conn.execute(text("""
            SELECT itam_id, hostname, ip_address, environment, department, region
            FROM reconciliation_status
            WHERE region=:region
              AND department=:dept
              AND status='Pending'
            ORDER BY environment, hostname
        """), {"region": region, "dept": department}).mappings().all()

        integrated = conn.execute(text("""
            SELECT itam_id, hostname, ip_address, environment, department, region
            FROM reconciliation_status
            WHERE region=:region
              AND department=:dept
              AND status='Integrated'
            ORDER BY environment, hostname
        """), {"region": region, "dept": department}).mappings().all()

    return render_template(
        "dept_dashboard.html",
        region=region,
        department=department,
        pending=pending,
        integrated=integrated
    )

# ---------------- RECONCILE ----------------
@app.route("/reconcile", methods=["POST"])
def reconcile_now():
    if not require_login() or session["user"]["role"] != "ADMIN":
        return redirect("/dashboard")

    itam_file = request.form.get("itam_file")
    active_file = request.form.get("active_file")

    if itam_file and active_file:
        reconcile(itam_file, active_file)

    return redirect("/dashboard")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==========================================================
# RUN
# ==========================================================
if __name__ == "__main__":
    app.run(debug=True)
