from flask import Blueprint, render_template, request, jsonify, session
from database import get_db
from routes.auth_utils import login_required

# Registered in app.py as: app.register_blueprint(profile_bp, url_prefix="/profile")
profile_bp = Blueprint("profile", __name__)


# ── Page ──────────────────────────────────────────────────────────────────────
@profile_bp.route("/")
@login_required
def profile_page():
    return render_template("profile.html")


# ── GET /profile/api ──────────────────────────────────────────────────────────
@profile_bp.route("/api", methods=["GET"])
@login_required
def get_profile():
    user_id = session.get("user_id")
    db = get_db()

    row = db.execute(
        "SELECT email, display_name, job_title, location, created_at, last_login "
        "FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not row:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "email":        row["email"],
        "display_name": row["display_name"] or "",
        "job_title":    row["job_title"]    or "",
        "location":     row["location"]     or "",
        "created_at":   row["created_at"],
        "last_login":   row["last_login"],
    })


# ── PATCH /profile/api ────────────────────────────────────────────────────────
@profile_bp.route("/api", methods=["PATCH"])
@login_required
def update_profile():
    user_id = session.get("user_id")
    data    = request.get_json(silent=True) or {}
    db      = get_db()

    new_email = data.get("email", "").strip().lower()

    if new_email:
        current = db.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()

        if current and new_email != current["email"]:
            conflict = db.execute(
                "SELECT id FROM users WHERE email = ? AND id != ?",
                (new_email, user_id)
            ).fetchone()
            if conflict:
                return jsonify({"error": "Email already in use"}), 409

    fields = {}
    if new_email:
        fields["email"] = new_email
    if "display_name" in data:
        fields["display_name"] = data["display_name"].strip()
    if "job_title" in data:
        fields["job_title"] = data["job_title"].strip()
    if "location" in data:
        fields["location"] = data["location"].strip()

    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values     = list(fields.values()) + [user_id]

        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        db.commit()

        # Keep server-side session in sync so topbar avatar is correct
        # on the CURRENT request's response — next load always reads from DB.
        if "display_name" in fields:
            session["display_name"] = fields["display_name"]
        if "email" in fields:
            session["email"] = fields["email"]

    return jsonify({"success": True})