from flask import Blueprint, render_template, jsonify, session, request
from database import get_db
from routes.auth_utils import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    return render_template("dashboard.html")


@dashboard_bp.route("/api/stats")
@login_required
def stats():
    uid = session["user_id"]
    try:
        with get_db() as conn:
            total    = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=?", (uid,)).fetchone()[0]
            applied  = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='applied'", (uid,)).fetchone()[0]
            followed = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='followed_up'", (uid,)).fetchone()[0]
            offered  = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='offered'", (uid,)).fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND status='rejected'", (uid,)).fetchone()[0]
        return jsonify({"total": total, "applied": applied, "followed_up": followed, "offered": offered, "rejected": rejected})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/jobs/table")
@login_required
def jobs_table():
    uid = session["user_id"]
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, title, company, location, match_score, source, status, created_at FROM jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 100",
                (uid,)
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/jobs/<int:job_id>/status", methods=["PATCH"])
@login_required
def update_status(job_id):
    uid = session["user_id"]
    data = request.get_json()
    status = data.get("status")
    if status not in {"saved", "applied", "followed_up", "offered", "rejected"}:
        return jsonify({"error": "Invalid status"}), 400
    try:
        with get_db() as conn:
            conn.execute("UPDATE jobs SET status=? WHERE id=? AND user_id=?", (status, job_id, uid))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/jobs/<int:job_id>", methods=["DELETE"])
@login_required
def delete_job(job_id):
    uid = session["user_id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM jobs WHERE id=? AND user_id=?", (job_id, uid))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500