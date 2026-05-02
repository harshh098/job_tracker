from flask import Blueprint, render_template, request, jsonify, session
from routes.auth_utils import login_required
from database import get_db
import hashlib
import os

settings_bp = Blueprint("settings", __name__)

# ── GET /settings/ (PAGE LOAD) ─────────────────────────────
@settings_bp.route("/", methods=["GET"])
@login_required
def settings_page():
    return render_template("settings.html")


# ── Helper: hash password ─────────────────────────────────────────────────────
# MUST match auth.py exactly: sha256(SECRET_KEY + password)
def _hash_pw(plain: str) -> str:
    salt = os.getenv("SECRET_KEY", "dev-secret")
    return hashlib.sha256(f"{salt}{plain}".encode()).hexdigest()


# ── POST /settings/change-password ───────────────────────────────────────────
@settings_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password     = (data.get("new_password")     or "").strip()

    # OTP users (no password_hash) only need new_password
    if not new_password:
        return jsonify({"error": "New password is required."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400

    user_id = session.get("user_id")

    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if not row:
            return jsonify({"error": "User not found."}), 404

        # ── CHANGED: only validate current password if one exists ──────────
        # OTP users have password_hash = NULL → skip current-password check
        # Password users have a hash      → validate normally
        if row["password_hash"] is not None:
            if not current_password:
                return jsonify({"error": "Current password is required."}), 400
            if row["password_hash"] != _hash_pw(current_password):
                return jsonify({"error": "Current password is incorrect."}), 400
        # ───────────────────────────────────────────────────────────────────

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_pw(new_password), user_id),
        )
        conn.commit()

    return jsonify({"success": True, "message": "Password updated successfully."})