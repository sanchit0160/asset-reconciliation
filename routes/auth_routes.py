from flask import Blueprint, render_template, request, redirect, session
from sqlalchemy import text
from database import engine

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        department = request.form.get("department")

        if username == "admin" and password == "admin123":
            session["user"] = {"username": username, "role": "ADMIN"}
            return redirect("/dashboard")

        if username and password and department:
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT DISTINCT region
                        FROM reconciliation_status
                        WHERE department = :dept
                        LIMIT 1
                    """),
                    {"dept": department.upper()}
                ).fetchone()

            if not row:
                return render_template("login.html", error="No region found")

            session["user"] = {
                "username": username,
                "role": "DEPT",
                "department": department.upper(),
                "region": row.region
            }
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
