import hashlib
import os
import random
import time
from flask import Blueprint, request, jsonify, render_template, session, redirect

from database import get_db

auth_bp = Blueprint("auth", __name__)

# ── Twilio client (lazy-loaded) ───────────────────────────────────────────────

def _get_twilio():
    from twilio.rest import Client
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )

def send_sms(to: str, msg: str):
    client = _get_twilio()
    print("TWILIO FROM:", os.getenv("TWILIO_PHONE_NUMBER"))
    client.messages.create(
        body=msg,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=to
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    salt = os.getenv("SECRET_KEY", "dev-secret")
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def _generate_and_store_otp(scope: str, target: str):
    otp = str(random.randint(100000, 999999))
    session[f"{scope}_otp"]         = otp
    session[f"{scope}_otp_target"]  = target
    session[f"{scope}_otp_expires"] = time.time() + 300
    return otp


def _validate_otp(scope: str, target: str, otp_input: str):
    stored_otp    = session.get(f"{scope}_otp")
    stored_target = session.get(f"{scope}_otp_target")
    otp_expires   = session.get(f"{scope}_otp_expires", 0)

    if not stored_otp or not stored_target:
        return False, "No OTP was requested. Please request a new one."

    if time.time() > otp_expires:
        for k in (f"{scope}_otp", f"{scope}_otp_target", f"{scope}_otp_expires"):
            session.pop(k, None)
        return False, "OTP has expired. Please request a new one."

    if target != stored_target:
        return False, "Identifier does not match the one used to request the OTP."

    if otp_input != stored_otp:
        return False, "Invalid OTP. Please try again."

    return True, None


def _clear_otp(scope: str):
    for k in (f"{scope}_otp", f"{scope}_otp_target", f"{scope}_otp_expires"):
        session.pop(k, None)


# ── Pages ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect("/")
    return render_template("login.html")


@auth_bp.route("/signup")
def signup_page():
    if session.get("user_id"):
        return redirect("/")
    return render_template("signup.html")


@auth_bp.route("/forgot-password")
def forgot_password_page():
    if session.get("user_id"):
        return redirect("/")
    return render_template("forgot_password.html")


# ── OTP endpoints (login flow) ────────────────────────────────────────────────

@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    data  = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()

    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    if not phone.startswith("+"):
        return jsonify({"error": "Phone number must be in E.164 format (e.g. +91XXXXXXXXXX)"}), 400

    otp = _generate_and_store_otp("login", phone)

    try:
        send_sms(phone, f"Your JobTracker AI verification code is: {otp}. It expires in 5 minutes.")
    except Exception as e:
        return jsonify({"error": f"Failed to send SMS: {str(e)}"}), 500

    return jsonify({"success": True, "message": "OTP sent successfully"})


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    data      = request.get_json(silent=True) or {}
    phone     = (data.get("phone") or "").strip()
    otp_input = (data.get("otp")   or "").strip()

    if not phone or not otp_input:
        return jsonify({"error": "Phone and OTP are required"}), 400

    ok, err = _validate_otp("login", phone, otp_input)
    if not ok:
        status = 401 if "Invalid" in err else 400
        return jsonify({"error": err}), status

    _clear_otp("login")

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE phone = ?", (phone,)
        ).fetchone()

        if not user:
            conn.execute("INSERT INTO users (phone) VALUES (?)", (phone,))
            conn.commit()
            user = conn.execute(
                "SELECT id FROM users WHERE phone = ?", (phone,)
            ).fetchone()

    session["user_id"]    = user["id"]
    session["user_phone"] = phone
    return jsonify({"success": True, "redirect": "/"})


# ── Forgot Password: Phone OTP only ──────────────────────────────────────────

@auth_bp.route("/forgot-password/send-otp", methods=["POST"])
def fp_send_otp():
    data  = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()

    if not phone:
        return jsonify({"error": "Phone number is required"}), 400
    if not phone.startswith("+"):
        return jsonify({"error": "Phone must be in E.164 format (e.g. +91XXXXXXXXXX)"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE phone = ?", (phone,)
        ).fetchone()

    if not user:
        return jsonify({"error": "No account found with that phone number."}), 404

    otp = _generate_and_store_otp("reset", phone)

    try:
        send_sms(phone, f"Your JobTracker AI password reset code is: {otp}. Expires in 5 minutes.")
    except Exception as e:
        return jsonify({"error": f"Failed to send SMS: {str(e)}"}), 500

    return jsonify({"success": True})


@auth_bp.route("/forgot-password/verify", methods=["POST"])
def fp_verify():
    data      = request.get_json(silent=True) or {}
    phone     = (data.get("phone") or "").strip()
    otp_input = (data.get("otp")   or "").strip()

    if not phone or not otp_input:
        return jsonify({"error": "Phone and OTP are required"}), 400

    ok, err = _validate_otp("reset", phone, otp_input)
    if not ok:
        return jsonify({"error": err}), (401 if "Invalid" in err else 400)

    _clear_otp("reset")
    session["reset_verified_for"] = phone

    return jsonify({"success": True})


@auth_bp.route("/forgot-password/reset", methods=["POST"])
def fp_reset():
    data         = request.get_json(silent=True) or {}
    phone        = (data.get("phone")        or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not phone or not new_password:
        return jsonify({"error": "Phone and new password are required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if session.get("reset_verified_for") != phone:
        return jsonify({"error": "OTP not verified. Please complete verification first."}), 403

    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE phone = ?", (phone,)
        ).fetchone()
        if not user:
            return jsonify({"error": "No account found with that phone number."}), 404

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash(new_password), user["id"])
        )
        conn.commit()

    session.pop("reset_verified_for", None)
    return jsonify({"success": True})


# ── Password-based auth ───────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

    if not user or user["password_hash"] != _hash(password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"]    = user["id"]
    session["user_email"] = user["email"]
    return jsonify({"success": True, "redirect": "/"})


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()
        if existing:
            return jsonify({"error": "An account with this email already exists"}), 409

        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, _hash(password))
        )
        conn.commit()

        user = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

    session["user_id"]    = user["id"]
    session["user_email"] = email
    return jsonify({"success": True, "redirect": "/"})


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/auth/login")