import os
import re
import json
import unicodedata
from flask import Blueprint, request, jsonify, current_app, render_template, session
from werkzeug.utils import secure_filename
from database import get_db
from routes.auth_utils import login_required

resume_bp = Blueprint("resume", __name__)
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

# ---------------------------------------------------------------------------
# Section header keywords used for section-aware parsing
# ---------------------------------------------------------------------------
EXPERIENCE_SECTION_HEADERS = {
    "experience", "work experience", "professional experience",
    "internship", "internships", "research", "research experience",
    "projects", "project", "work history", "employment", "employment history",
    "relevant experience", "industry experience", "academic projects",
}

STOP_SECTION_HEADERS = {
    "education", "skills", "technical skills", "certifications",
    "awards", "achievements", "publications", "languages", "hobbies",
    "interests", "references", "volunteer", "extracurricular",
    "summary", "objective", "profile", "about",
}

# Headings to explicitly skip during name extraction
NON_NAME_HEADINGS = {
    "resume", "curriculum vitae", "cv", "profile", "summary", "objective",
    "skills", "education", "experience", "projects", "contact", "references",
    "about me", "about", "overview",
}

EXPERIENCE_LINE_KEYWORDS = {
    "intern", "internship", "engineer", "developer", "analyst", "scientist",
    "researcher", "research", "project", "ai", "machine learning", "data science",
    "software", "backend", "frontend", "full stack", "fullstack", "devops",
    "architect", "consultant", "manager", "lead", "senior", "junior",
    "associate", "trainee", "assistant", "specialist", "coordinator",
}

SKILL_KEYWORDS = [
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "ruby",
    "react", "vue", "angular", "node", "flask", "django", "fastapi", "express",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "git", "linux", "html", "css", "rest", "graphql", "machine learning",
    "deep learning", "nlp", "data science", "pandas", "numpy", "tensorflow", "pytorch",
    "spark", "hadoop", "kafka", "airflow", "dbt", "tableau", "power bi",
    "agile", "scrum", "jira", "figma", "photoshop",
]

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_text(text):
    """Normalize unicode, remove PDF artifacts, and clean whitespace."""
    # Normalize unicode (e.g. fancy dashes, ligatures)
    text = unicodedata.normalize("NFKD", text)
    # Replace unicode dashes with hyphen
    text = re.sub(r"[\u2012\u2013\u2014\u2015\u2212]", "-", text)
    # Remove broken URL fragments (e.g. http://..., www....)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    # Remove non-printable characters except newlines and tabs
    text = re.sub(r"[^\x20-\x7E\n\t]", " ", text)
    # Collapse repeated punctuation
    text = re.sub(r"\.{3,}", "...", text)
    # Collapse excessive whitespace within lines
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Collapse more than 2 consecutive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_likely_contact_line(line):
    """Return True if line looks like a contact/meta line to be excluded."""
    patterns = [
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # email
        r"(\+?\d[\d\s\-().]{7,}\d)",                           # phone
        r"linkedin\.com",
        r"github\.com",
        r"gitlab\.com",
        r"twitter\.com",
        r"^\s*[\+\d\s\-().]{8,}\s*$",                         # pure phone line
        r"^https?://",
        r"^www\.",
    ]
    for p in patterns:
        if re.search(p, line, re.IGNORECASE):
            return True
    return False


def is_section_header(line):
    """Check if a line is a known section header."""
    normalized = line.strip().lower().rstrip(":")
    return normalized in EXPERIENCE_SECTION_HEADERS | STOP_SECTION_HEADERS


def get_section_type(line):
    """Return 'experience', 'stop', or None."""
    normalized = line.strip().lower().rstrip(":")
    if normalized in EXPERIENCE_SECTION_HEADERS:
        return "experience"
    if normalized in STOP_SECTION_HEADERS:
        return "stop"
    return None


# ---------------------------------------------------------------------------
# File text extraction
# ---------------------------------------------------------------------------

def extract_text_from_file(filepath):
    """Extract raw text from PDF, DOCX, or TXT files."""
    ext = filepath.rsplit(".", 1)[1].lower()

    if ext == "txt":
        try:
            with open(filepath, "r", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading TXT: {e}"

    elif ext == "pdf":
        try:
            import fitz  # PyMuPDF
            pages = []
            with fitz.open(filepath) as doc:
                for page in doc:
                    # Preserve layout with better text extraction flags
                    blocks = page.get_text("blocks", sort=True)
                    page_lines = []
                    for block in blocks:
                        # block: (x0, y0, x1, y1, text, block_no, block_type)
                        if block[6] == 0:  # text block
                            block_text = block[4].strip()
                            if block_text:
                                page_lines.append(block_text)
                    pages.append("\n".join(page_lines))
            return "\n".join(pages)
        except ImportError:
            return "Error: PyMuPDF (fitz) is not installed. Run: pip install pymupdf"
        except Exception as e:
            return f"Error reading PDF: {e}"

    elif ext == "docx":
        try:
            import docx
            doc = docx.Document(filepath)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            return f"Error reading DOCX: {e}"

    return ""


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def extract_email(text):
    """Robust email extraction that avoids merged/corrupted PDF text."""
    # Stricter pattern to avoid grabbing garbage around email
    match = re.search(
        r"(?<![a-zA-Z0-9._%+\-])"
        r"[a-zA-Z0-9._%+\-]{2,64}"
        r"@"
        r"[a-zA-Z0-9\-]{2,63}"
        r"(?:\.[a-zA-Z]{2,6})+"
        r"(?![a-zA-Z0-9._%+\-])",
        text
    )
    return match.group().strip() if match else ""


def extract_phone(text):
    """Extract Indian or international phone numbers and normalize format."""
    # Indian: +91, 91, or 10-digit starting with 6-9
    # International: various formats
    patterns = [
        r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",              # +91 XXXXX XXXXX
        r"\b91[\s\-]?\d{5}[\s\-]?\d{5}\b",            # 91 XXXXX XXXXX
        r"\b[6-9]\d{4}[\s\-]?\d{5}\b",                # 10-digit Indian mobile
        r"\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{4,6}",  # International
        r"\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}",         # US format
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group().strip()
            # Normalize: collapse inner spaces/dashes for cleanliness
            normalized = re.sub(r"[\s\-]+", "-", raw)
            return normalized
    return ""


def extract_name(lines):
    """
    Detect the candidate's name from the first meaningful lines.
    Skips: section headings, emails, URLs, single words, lines >60 chars.
    Expects 2–3 word proper-noun-style tokens.
    """
    name_re = re.compile(r"^[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){1,2}$")
    for line in lines[:15]:
        line = line.strip()
        if not line:
            continue
        if len(line) > 60:
            continue
        if "@" in line or "http" in line.lower() or "www." in line.lower():
            continue
        if line.lower().rstrip(":") in NON_NAME_HEADINGS:
            continue
        if re.search(r"\d", line):
            continue
        # Must look like "Firstname Lastname" or "Firstname Middle Lastname"
        if name_re.match(line):
            return line
    return ""


def extract_skills(text):
    """
    Keyword-based skill detection.
    - Uses word-boundary matching to avoid partial hits (e.g. 'go' inside 'google').
    - Deduplicates while preserving order.
    """
    text_lower = text.lower()
    seen = set()
    skills = []
    for skill in SKILL_KEYWORDS:
        # Use word boundaries; handle multi-word skills too
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            if skill not in seen:
                seen.add(skill)
                skills.append(skill)
    return skills


# ---------------------------------------------------------------------------
# Section-aware experience extraction
# ---------------------------------------------------------------------------

def extract_experience_highlights(text):
    """
    Section-aware, line-by-line experience extraction.

    Strategy:
    1. Walk lines and track which section we are in.
    2. Only collect lines from experience-type sections.
    3. Filter out contact info, URLs, and noise.
    4. Score remaining lines for relevance using keyword signals.
    5. Return top-6 cleaned highlights.
    """
    lines = text.split("\n")
    in_experience_section = False
    collected = []

    year_pattern = re.compile(r"\b(19|20)\d{2}\b")
    bullet_prefix = re.compile(r"^[\-\u2022\u25cf\*\>]\s+")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section transitions
        section_type = get_section_type(stripped)
        if section_type == "experience":
            in_experience_section = True
            continue
        if section_type == "stop":
            in_experience_section = False
            continue

        if not in_experience_section:
            continue

        # Skip contact/meta lines
        if is_likely_contact_line(stripped):
            continue

        # Strip bullet characters
        cleaned = bullet_prefix.sub("", stripped).strip()

        if len(cleaned) < 15 or len(cleaned) > 200:
            continue

        # Must contain at least one experience keyword OR a year
        line_lower = cleaned.lower()
        has_keyword = any(kw in line_lower for kw in EXPERIENCE_LINE_KEYWORDS)
        has_year = bool(year_pattern.search(cleaned))

        if has_keyword or has_year:
            collected.append(cleaned)

    # Fallback: if section detection found nothing, scan whole doc for
    # lines that strongly match experience signals + contain a year
    if not collected:
        for line in lines:
            stripped = line.strip()
            if not stripped or is_likely_contact_line(stripped):
                continue
            if len(stripped) < 15 or len(stripped) > 200:
                continue
            line_lower = stripped.lower()
            has_keyword = any(kw in line_lower for kw in EXPERIENCE_LINE_KEYWORDS)
            has_year = bool(year_pattern.search(stripped))
            if has_keyword and has_year:
                collected.append(stripped)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for item in collected:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique[:6]


# ---------------------------------------------------------------------------
# Main parse orchestrator
# ---------------------------------------------------------------------------

def parse_resume_text(text):
    """
    Orchestrate all extraction steps on cleaned resume text.
    Returns a dict with: name, email, phone, skills, experience.
    """
    text = clean_text(text)
    lines = [l for l in text.split("\n") if l.strip()]

    name = extract_name(lines)
    email = extract_email(text)
    phone = extract_phone(text)
    skills = extract_skills(text)
    experience = extract_experience_highlights(text)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "experience": experience,
    }


# ---------------------------------------------------------------------------
# Routes (unchanged API surface)
# ---------------------------------------------------------------------------

@resume_bp.route("/")
@login_required
def resume_page():
    return render_template("resume.html")


@resume_bp.route("/upload", methods=["POST"])
@login_required
def upload_resume():
    uid = session["user_id"]
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use PDF, DOCX, or TXT"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    raw_text = extract_text_from_file(save_path)
    if raw_text.startswith("Error"):
        return jsonify({"error": raw_text}), 422

    parsed = parse_resume_text(raw_text)

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO resumes (user_id, filename, original_name, name, email, phone, skills, experience, raw_text) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    uid,
                    filename,
                    file.filename,
                    parsed["name"],
                    parsed["email"],
                    parsed["phone"],
                    json.dumps(parsed["skills"]),
                    json.dumps(parsed["experience"]),
                    raw_text[:5000],
                ),
            )
            conn.commit()
    except Exception as e:
        return jsonify({"error": f"DB error: {e}"}), 500

    return jsonify({"success": True, "parsed": parsed, "filename": filename})


@resume_bp.route("/list")
@login_required
def list_resumes():
    uid = session["user_id"]
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, original_name, name, email, phone, skills, experience, uploaded_at "
                "FROM resumes WHERE user_id=? ORDER BY uploaded_at DESC",
                (uid,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["skills"] = json.loads(d["skills"] or "[]")
            d["experience"] = json.loads(d["experience"] or "[]")
            result.append(d)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@resume_bp.route("/clear", methods=["DELETE"])
@login_required
def clear_resumes():
    uid = session["user_id"]
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT filename FROM resumes WHERE user_id=?", (uid,)
            ).fetchall()
            conn.execute("DELETE FROM resumes WHERE user_id=?", (uid,))
            conn.commit()
        upload_folder = current_app.config["UPLOAD_FOLDER"]
        for row in rows:
            path = os.path.join(upload_folder, row["filename"])
            if os.path.exists(path):
                os.remove(path)
        return jsonify({"ok": True, "deleted": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500