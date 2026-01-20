from flask import Blueprint, request, redirect, session
from services.reconciliation import reconcile

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/reconcile", methods=["POST"])
def reconcile_now():
    if session["user"]["role"] != "ADMIN":
        return redirect("/dashboard")

    reconcile(
        request.form.get("itam_file"),
        request.form.get("active_file")
    )
    return redirect("/dashboard")
