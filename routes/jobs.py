import os
import logging
import requests
from flask import Blueprint, request, jsonify, render_template, session
from database import get_db
from routes.auth_utils import login_required

log = logging.getLogger(__name__)
jobs_bp = Blueprint("jobs", __name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# ── Experience keyword map (matches HTML dropdown values) ─────────────────────
EXP_KEYWORD_MAP = {
    "entry":  ["intern", "fresher", "junior", "associate", "trainee"],
    "mid":    ["mid level", "2 years"],
    "senior": ["senior"],
    "lead":   ["lead", "principal", "manager"],
}

# ── Role alias map — expands shorthand roles into full search terms ───────────
ROLE_ALIASES: dict[str, list[str]] = {
    "aiml":             ["artificial intelligence", "machine learning", "ai ml"],
    "ai ml":            ["artificial intelligence", "machine learning"],
    "ml":               ["machine learning"],
    "ai":               ["artificial intelligence"],
    "nlp":              ["natural language processing", "nlp"],
    "cv":               ["computer vision"],
    "sde":              ["software development engineer", "software engineer"],
    "swe":              ["software engineer"],
    "fullstack":        ["full stack developer"],
    "full stack":       ["full stack developer"],
    "frontend":         ["frontend developer"],
    "front end":        ["frontend developer"],
    "backend":          ["backend developer"],
    "back end":         ["backend developer"],
    "devops":           ["devops engineer"],
    "qa":               ["quality assurance engineer", "qa engineer"],
    "ds":               ["data scientist"],
    "da":               ["data analyst"],
    "de":               ["data engineer"],
    "ba":               ["business analyst"],
    "pm":               ["product manager"],
    "ux":               ["ux designer", "user experience designer"],
    "ui":               ["ui designer"],
    "ui ux":            ["ui ux designer"],
    "ios":              ["ios developer"],
    "android":          ["android developer"],
    "react":            ["react developer"],
    "node":             ["node.js developer"],
    "nodejs":           ["node.js developer"],
    "python":           ["python developer"],
    "java":             ["java developer"],
    "dot net":          ["dotnet developer", ".net developer"],
    "dotnet":           ["dotnet developer", ".net developer"],
    ".net":             [".net developer"],
}

# ── Terms that indicate a senior/management role ──────────────────────────────
SENIOR_SIGNALS = {"senior", "lead", "principal", "manager", "architect"}
YEAR_SIGNALS   = {"3+ years", "5+ years", "4+ years", "6+ years", "7+ years",
                  "3 years", "5 years", "4 years", "6+ year", "5+ year"}

# ── Terms that boost a result's score ─────────────────────────────────────────
BOOST_TERMS    = {"intern", "junior", "fresher", "associate", "trainee"}
PENALIZE_TERMS = {"senior", "lead", "principal", "manager"}

# ── Entry-level suffix keywords ───────────────────────────────────────────────
ENTRY_SUFFIX_TERMS = {"intern", "junior", "fresher", "associate", "trainee"}


def _expand_role_aliases(role: str) -> list[str]:
    """
    Return a list of expanded role strings for a given input.
    If the role matches a known alias key, return its expansions.
    Otherwise return the role as-is (single-element list).
    """
    key = role.lower().strip()
    if key in ROLE_ALIASES:
        return ROLE_ALIASES[key]
    # Partial match: if the entire role string equals an alias key
    for alias_key, expansions in ROLE_ALIASES.items():
        if key == alias_key:
            return expansions
    return [role]


def _role_already_has_exp_terms(role: str) -> bool:
    """Return True if the role string already contains experience-level words."""
    r = role.lower()
    all_terms = ENTRY_SUFFIX_TERMS | SENIOR_SIGNALS
    return any(t in r for t in all_terms)


def build_queries(role: str, location: str, experience: str) -> list[str]:
    """
    Generate multiple targeted search queries based on role / location /
    experience level.

    - Expands role aliases first (e.g. "aiml" → ["artificial intelligence", "machine learning", "ai ml"])
    - For entry-level searches, fans out across synonym terms per expanded role
    - Deduplicates final query list
    """
    loc_suffix = f" {location}".rstrip() if location else ""
    expanded_roles = _expand_role_aliases(role)

    queries: list[str] = []

    for expanded_role in expanded_roles:
        if experience == "entry":
            if _role_already_has_exp_terms(expanded_role):
                queries.append(f"{expanded_role}{loc_suffix}")
            else:
                for kw in EXP_KEYWORD_MAP["entry"]:
                    queries.append(f"{kw} {expanded_role}{loc_suffix}")

        elif experience in EXP_KEYWORD_MAP:
            keywords = EXP_KEYWORD_MAP[experience]
            if _role_already_has_exp_terms(expanded_role):
                queries.append(f"{expanded_role}{loc_suffix}")
            else:
                for kw in keywords:
                    queries.append(f"{expanded_role} {kw}{loc_suffix}")

        else:
            # No experience filter — single broad query per role
            queries.append(f"{expanded_role}{loc_suffix}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_queries: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    return unique_queries


def _score_job(job: dict) -> int:
    """Return a relevance score; higher = more entry-level friendly."""
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    score = 0
    for term in BOOST_TERMS:
        if term in text:
            score += 10
    for term in PENALIZE_TERMS:
        if term in text:
            score -= 8
    return score


def _is_senior_job(job: dict) -> bool:
    """Return True if this job looks like a senior / management role."""
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    if any(s in text for s in SENIOR_SIGNALS):
        return True
    if any(y in text for y in YEAR_SIGNALS):
        return True
    return False


def _fetch_single_query(query: str, headers: dict) -> list[dict]:
    """Run one JSearch query and return normalised job dicts."""
    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query":       query,
        "page":        "1",
        "num_pages":   "1",
        "date_posted": "month",
    }
    print(f"[JSEARCH QUERY] {query}")
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for item in data.get("data", [])[:20]:
        jobs.append({
            "title":       item.get("job_title", ""),
            "company":     item.get("employer_name", ""),
            "location":    f"{item.get('job_city', '')}, {item.get('job_country', '')}".strip(", "),
            "description": item.get("job_description", "")[:500],
            "url":         item.get("job_apply_link", ""),
            "source":      "jsearch",
        })
    return jobs


def _friendly_error(e: Exception, query: str) -> str:
    """Convert a low-level exception into a user-friendly error string."""
    if isinstance(e, requests.exceptions.ConnectionError):
        return "Could not connect to the job search service. Check your internet connection."
    if isinstance(e, requests.exceptions.Timeout):
        return "The job search request timed out. Please try again."
    if isinstance(e, requests.exceptions.HTTPError):
        status = e.response.status_code if e.response is not None else "?"
        if status == 401 or status == 403:
            return "Invalid or expired RapidAPI key. Check your RAPIDAPI_KEY in .env."
        if status == 429:
            return "RapidAPI rate limit reached. Please wait a moment and try again."
        return f"Job search API returned an error (HTTP {status}). Try again later."
    if isinstance(e, requests.exceptions.RequestException):
        return f"Network error while searching for jobs. Please try again."
    return f"Unexpected error during job search: {str(e)[:120]}"


def search_jobs_rapidapi(role: str, location: str, experience: str = ""):
    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    queries = build_queries(role, location, experience)
    all_jobs: list[dict] = []
    error_msgs: list[str] = []

    for q in queries:
        try:
            all_jobs.extend(_fetch_single_query(q, headers))
        except Exception as e:
            msg = _friendly_error(e, q)
            log.warning("[search_jobs_rapidapi] %s — %s", q, msg)
            error_msgs.append(msg)

    # If every query failed with an error and we got nothing, surface the first error
    if not all_jobs and error_msgs:
        return [], error_msgs[0]

    # ── Deduplication by (title, company) ─────────────────────────────────────
    seen: set[tuple] = set()
    unique: list[dict] = []
    for job in all_jobs:
        key = (job["title"].lower().strip(), job["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(job)

    # ── Senior-job filtering (only when experience == "entry") ────────────────
    if experience == "entry":
        unique = [j for j in unique if not _is_senior_job(j)]

    # ── Score & sort ──────────────────────────────────────────────────────────
    unique.sort(key=_score_job, reverse=True)

    return unique[:40], None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@jobs_bp.route("/")
@login_required
def jobs_page():
    return render_template("jobs.html")


@jobs_bp.route("/scrape", methods=["POST"])
@login_required
def scrape_jobs():
    data       = request.get_json()
    role       = data.get("role", "").strip()
    location   = data.get("location", "").strip()
    experience = data.get("experience", "").strip()

    if not role:
        return jsonify({"error": "Role is required"}), 400

    if not RAPIDAPI_KEY or RAPIDAPI_KEY.startswith("your_"):
        # Demo fallback when no API key is configured
        jobs = [
            {"title": f"Junior {role}", "company": "TechCorp Inc",
             "location": location or "Remote",
             "description": f"We are looking for a fresher/junior {role}...",
             "url": "#", "source": "demo"},
            {"title": f"{role} Intern", "company": "StartupXYZ",
             "location": location or "San Francisco, CA",
             "description": f"Join our team as a {role} intern...",
             "url": "#", "source": "demo"},
            {"title": f"Associate {role}", "company": "BigTech LLC",
             "location": location or "New York, NY",
             "description": f"Entry-level {role} position...",
             "url": "#", "source": "demo"},
        ]
        return jsonify({"success": True, "found": len(jobs), "saved": 0, "jobs": jobs})

    jobs, error = search_jobs_rapidapi(role, location, experience)

    if error:
        log.error("[scrape_jobs] %s", error)
        return jsonify({"error": error, "jobs": []}), 500

    # Clean empty response — no error, just no results
    if not jobs:
        return jsonify({"success": True, "found": 0, "saved": 0, "jobs": []})

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