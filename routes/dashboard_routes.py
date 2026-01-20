from flask import Blueprint, render_template, redirect, session
from sqlalchemy import text
from database import engine
from auth.auth_utils import require_login

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect("/login")

    user = session["user"]

    if user["role"] == "ADMIN":
        with engine.connect() as conn:
            summary = conn.execute(text("""
                SELECT region, department,
                       COUNT(*) total,
                       SUM(status='Integrated') integrated,
                       SUM(status='Pending') pending
                FROM reconciliation_status
                GROUP BY region, department
            """)).mappings().all()

        return render_template("admin_dashboard.html", summary=summary)

    with engine.connect() as conn:
        pending = conn.execute(
            text("""
                SELECT * FROM reconciliation_status
                WHERE region=:region
                AND department=:dept
                AND status='Pending'
            """),
            {
                "region": user["region"],
                "dept": user["department"]
            }
        ).mappings().all()


    return render_template("dept_dashboard.html", pending=pending)
