import os
import logging
import requests
from flask import Blueprint, request, jsonify, render_template, session
from database import get_db
from routes.auth_utils import login_required

log = logging.getLogger(__name__)
jobs_bp = Blueprint("jobs", __name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


def search_jobs_rapidapi(role, location, experience=""):
    url = "https://jsearch.p.rapidapi.com/search"
    query = f"{role} {experience} in {location}".strip()
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }
    params = {"query": query, "page": "1", "num_pages": "1", "date_posted": "all"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for item in data.get("data", [])[:20]:
            jobs.append({
                "title": item.get("job_title", ""),
                "company": item.get("employer_name", ""),
                "location": f"{item.get('job_city', '')}, {item.get('job_country', '')}".strip(", "),
                "description": item.get("job_description", "")[:500],
                "url": item.get("job_apply_link", ""),
                "source": "jsearch"
            })
        return jobs, None
    except requests.exceptions.HTTPError as e:
        return [], f"RapidAPI HTTP error: {e}"
    except Exception as e:
        return [], f"RapidAPI error: {e}"


@jobs_bp.route("/")
@login_required
def jobs_page():
    return render_template("jobs.html")


@jobs_bp.route("/scrape", methods=["POST"])
@login_required
def scrape_jobs():
    data = request.get_json()
    role = data.get("role", "").strip()
    location = data.get("location", "").strip()
    experience = data.get("experience", "").strip()

    if not role:
        return jsonify({"error": "Role is required"}), 400

    if not RAPIDAPI_KEY or RAPIDAPI_KEY.startswith("your_"):
        jobs = [
            {"title": f"Senior {role}", "company": "TechCorp Inc", "location": location or "Remote",
             "description": f"We are looking for a {role} with {experience} experience...", "url": "#", "source": "demo"},
            {"title": f"{role} Engineer", "company": "StartupXYZ", "location": location or "San Francisco, CA",
             "description": f"Join our team as a {role}...", "url": "#", "source": "demo"},
            {"title": f"Lead {role}", "company": "BigTech LLC", "location": location or "New York, NY",
             "description": f"Leading {role} position...", "url": "#", "source": "demo"},
        ]
        error = None
    else:
        jobs, error = search_jobs_rapidapi(role, location, experience)

    if error:
        log.error("[scrape_jobs] %s", error)
        return jsonify({"error": error, "jobs": []}), 500

    return jsonify({"success": True, "found": len(jobs), "saved": 0, "jobs": jobs})


@jobs_bp.route("/save", methods=["POST"])
@login_required
def save_job():
    uid  = session["user_id"]
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title   = (data.get("title")   or "").strip()
    company = (data.get("company") or "").strip()
    if not title or not company:
        return jsonify({"error": "Title and Company are required"}), 400

    location    = (data.get("location")    or "").strip()
    description = (data.get("description") or "").strip()
    url         = (data.get("url")         or "").strip()
    source      = (data.get("source")      or "jsearch").strip()

    try:
        with get_db() as conn:
            exists = conn.execute(
                "SELECT id FROM jobs WHERE user_id=? AND LOWER(title)=LOWER(?) AND LOWER(company)=LOWER(?)",
                (uid, title, company)
            ).fetchone()
            if exists:
                return jsonify({"success": True, "duplicate": True, "message": "Job already saved"})

            conn.execute(
                "INSERT INTO jobs (user_id, title, company, location, description, url, source, status) VALUES (?,?,?,?,?,?,?,?)",
                (uid, title, company, location, description, url, source, "saved")
            )
            conn.commit()
        return jsonify({"success": True, "duplicate": False, "message": "Job saved to tracker"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@jobs_bp.route("/add", methods=["POST"])
@login_required
def add_job():
    uid  = session["user_id"]
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title   = (data.get("title")   or "").strip()
    company = (data.get("company") or "").strip()
    if not title or not company:
        return jsonify({"error": "Title and Company are required"}), 400

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO jobs (user_id, title, company, location, description, url, source) VALUES (?,?,?,?,?,?,?)",
                (uid, title, company, data.get("location", ""), data.get("description", ""), data.get("url", ""), "manual")
            )
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500