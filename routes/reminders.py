from flask import Blueprint, request, jsonify, render_template, session
from database import get_db
from routes.auth_utils import login_required

reminders_bp = Blueprint("reminders", __name__)


@reminders_bp.route("/")
@login_required
def reminders_page():
    return render_template("reminders.html")


@reminders_bp.route("/add", methods=["POST"])
@login_required
def add_reminder():
    uid  = session["user_id"]
    data = request.get_json()
    title = data.get("title", "").strip()
    remind_at = data.get("remind_at", "").strip()
    if not title or not remind_at:
        return jsonify({"error": "Title and remind_at are required"}), 400
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO reminders (user_id, job_id, title, message, remind_at) VALUES (?,?,?,?,?)",
                (uid, data.get("job_id"), title, data.get("message", ""), remind_at)
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reminders_bp.route("/list")
@login_required
def list_reminders():
    uid = session["user_id"]
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT r.id, r.title, r.message, r.remind_at, r.status, r.created_at,
                          j.title as job_title, j.company
                   FROM reminders r
                   LEFT JOIN jobs j ON r.job_id = j.id
                   WHERE r.user_id=?
                   ORDER BY r.remind_at ASC""",
                (uid,)
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reminders_bp.route("/<int:reminder_id>/status", methods=["PATCH"])
@login_required
def update_status(reminder_id):
    uid  = session["user_id"]
    data = request.get_json()
    status = data.get("status")
    if status not in ("pending", "done", "dismissed"):
        return jsonify({"error": "Invalid status"}), 400
    try:
        with get_db() as conn:
            conn.execute("UPDATE reminders SET status=? WHERE id=? AND user_id=?", (status, reminder_id, uid))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@reminders_bp.route("/<int:reminder_id>", methods=["DELETE"])
@login_required
def delete_reminder(reminder_id):
    uid = session["user_id"]
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, uid))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500