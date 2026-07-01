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

JOB_SECTION_HEADERS = {
    "experience", "work experience", "professional experience",
    "internship", "internships", "work history", "employment",
    "employment history", "relevant experience", "industry experience",
}

PROJECT_SECTION_HEADERS = {
    "projects", "project", "academic projects", "personal projects",
    "key projects", "notable projects",
}

RESEARCH_SECTION_HEADERS = {
    "research", "research experience", "research & publications",
    "research and publications", "publications",
}

EXPERIENCE_SECTION_HEADERS = (
    JOB_SECTION_HEADERS | PROJECT_SECTION_HEADERS | RESEARCH_SECTION_HEADERS
)

STOP_SECTION_HEADERS = {
    "education", "skills", "technical skills", "certifications",
    "awards", "achievements", "languages", "hobbies",
    "interests", "references", "volunteer", "extracurricular",
    "summary", "objective", "profile", "about",
}

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


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\u2012\u2013\u2014\u2015\u2212]", "-", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = re.sub(r"[^\x20-\x7E\n\t]", " ", text)
    text = re.sub(r"\.{3,}", "...", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_likely_contact_line(line):
    patterns = [
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        r"(\+?\d[\d\s\-().]{7,}\d)",
        r"linkedin\.com",
        r"github\.com",
        r"gitlab\.com",
        r"twitter\.com",
        r"^\s*[\+\d\s\-().]{8,}\s*$",
        r"^https?://",
        r"^www\.",
    ]
    for p in patterns:
        if re.search(p, line, re.IGNORECASE):
            return True
    return False


def is_section_header(line):
    normalized = line.strip().lower().rstrip(":")
    return (
        normalized in JOB_SECTION_HEADERS
        or normalized in PROJECT_SECTION_HEADERS
        or normalized in RESEARCH_SECTION_HEADERS
        or normalized in STOP_SECTION_HEADERS
    )


def get_section_type(line):
    normalized = line.strip().lower().rstrip(":")
    if normalized in JOB_SECTION_HEADERS:
        return "job"
    if normalized in PROJECT_SECTION_HEADERS:
        return "project"
    if normalized in RESEARCH_SECTION_HEADERS:
        return "research"
    if normalized in STOP_SECTION_HEADERS:
        return "stop"
    return None


def extract_text_from_file(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()

    if ext == "txt":
        try:
            with open(filepath, "r", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading TXT: {e}"

    elif ext == "pdf":
        try:
            import fitz
            pages = []
            with fitz.open(filepath) as doc:
                for page in doc:
                    blocks = page.get_text("blocks", sort=True)
                    page_lines = []
                    for block in blocks:
                        if block[6] == 0:
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


def extract_email(text):
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
    patterns = [
        r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",
        r"\b91[\s\-]?\d{5}[\s\-]?\d{5}\b",
        r"\b[6-9]\d{4}[\s\-]?\d{5}\b",
        r"\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{4,6}",
        r"\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group().strip()
            normalized = re.sub(r"[\s\-]+", "-", raw)
            return normalized
    return ""


def extract_name(lines):
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
        if name_re.match(line):
            return line
    return ""


def extract_skills(text):
    text_lower = text.lower()
    seen = set()
    skills = []
    for skill in SKILL_KEYWORDS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            if skill not in seen:
                seen.add(skill)
                skills.append(skill)
    return skills


_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_TOKEN = rf"(?:{_MONTH}\s+\d{{4}}|\d{{4}})"
_END_TOKEN = rf"(?:Present|Current|Now|{_DATE_TOKEN})"

DATE_PATTERN = re.compile(
    rf"{_DATE_TOKEN}\s*[-–—]\s*{_END_TOKEN}",
    re.IGNORECASE,
)

TITLE_KEYWORDS = (
    "intern", "internship", "developer", "engineer", "scientist", "analyst",
    "research", "researcher", "manager", "consultant", "architect",
    "specialist", "coordinator", "administrator", "designer", "lead",
    "associate", "trainee", "assistant",
)

_TITLE_KEYWORDS_SORTED = sorted(TITLE_KEYWORDS, key=len, reverse=True)
TITLE_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _TITLE_KEYWORDS_SORTED) + r")\b",
    re.IGNORECASE,
)

BULLET_PREFIX_RE = re.compile(r"^[•\-\*▪‣●○·»]\s+")

COMPANY_HINT_RE = re.compile(
    r"\b(Inc|Ltd|LLC|LLP|Pvt|Corp|Corporation|Technologies|Tech|Solutions|"
    r"Systems|Labs|Studio|Group|Company|Co\.|Consulting|Software|Global|"
    r"Industries|Enterprises|AI|Analytics)\b",
    re.IGNORECASE,
)


def _is_bullet_line(line):
    return bool(BULLET_PREFIX_RE.match(line))


def _is_skill_list_line(line):
    if line.count(",") >= 2:
        return True
    lower = line.lower()
    hits = sum(1 for s in SKILL_KEYWORDS if re.search(r"\b" + re.escape(s) + r"\b", lower))
    return hits >= 2


def _is_description_line(line):
    word_count = len(line.split())
    if word_count > 12:
        return True
    if line.endswith(".") and word_count > 6:
        return True
    return False


def _is_noise_line(line):
    return (
        _is_bullet_line(line)
        or is_likely_contact_line(line)
        or _is_skill_list_line(line)
        or _is_description_line(line)
    )


def _split_merged_entry(line):
    date_match = DATE_PATTERN.search(line)
    if not date_match:
        return None

    duration = date_match.group().strip()
    before = line[: date_match.start()].strip(" -|,")

    if not before:
        return None

    if "|" in before:
        parts = [p.strip() for p in before.split("|", 1)]
        title = parts[0]
        company = parts[1] if len(parts) > 1 else ""
        return title, company, duration

    company_hint = COMPANY_HINT_RE.search(before)
    title_kw = TITLE_KEYWORD_RE.search(before)

    if title_kw:
        after_kw = before[title_kw.end():].strip(" -,")
        title_part = before[: title_kw.end()].strip(" -,")
        if after_kw:
            return title_part, after_kw, duration
        return before, "", duration

    if company_hint:
        split_idx = before.rfind(" ", 0, company_hint.start())
        if split_idx > 0:
            title_part = before[:split_idx].strip()
            company_part = before[split_idx:].strip()
            if title_part:
                return title_part, company_part, duration

    return before, "", duration


def _looks_like_entry_title(line):
    if _is_noise_line(line):
        return False
    if DATE_PATTERN.search(line):
        return False
    return bool(TITLE_KEYWORD_RE.search(line))


_VENUE_LINE_RE = re.compile(
    r"^(published|journal|conference|venue|doi|isbn|proceedings)\s*[:\-]",
    re.IGNORECASE,
)
_VENUE_SHORT_RE = re.compile(r"^[A-Z][A-Za-z&.\-]{1,24}(\s+\d{4})?$")


def _is_venue_line(line):
    """
    True if the line is publication/venue metadata belonging to the entry
    directly above it (e.g. "Published: IJCRT", "ICICT 2026") rather than
    a new project/research title or a plain description fragment.
    """
    stripped = line.strip()
    if _VENUE_LINE_RE.match(stripped):
        return True
    if len(stripped.split()) <= 3 and _VENUE_SHORT_RE.match(stripped):
        return True
    return False


def _looks_like_project_title(line):
    """
    True if a standalone line plausibly starts a NEW project/research entry
    (a project name / paper title), as opposed to being a continuation
    fragment of the entry above it.

    Real headings are short noun-phrase lines that do NOT end in sentence
    punctuation and do NOT start with a lowercase letter — bullet-wrapped
    description fragments like "tool calling.", "UPI, and financial
    literacy queries.", or "outperforming standalone baselines by over 4%."
    fail one of those checks and are correctly rejected, so they fold into
    the previous entry instead of becoming their own card.
    """
    if _is_noise_line(line):
        return False
    if DATE_PATTERN.search(line):
        return False
    if _is_venue_line(line):
        return False

    stripped = line.strip()
    word_count = len(stripped.split())
    if word_count == 0 or word_count > 14:
        return False

    if stripped.endswith(('.', ',', ';')):
        return False

    if stripped[0].islower():
        return False

    return True


def _collect_entry(lines, i, n, category="job"):
    line = lines[i]

    merged = _split_merged_entry(line)
    if merged:
        title, company, duration = merged
        return {"title": title, "company": company, "duration": duration}, i + 1

    if "|" in line:
        parts = [p.strip() for p in line.split("|", 1)]
        title = parts[0]
        company = parts[1] if len(parts) > 1 else ""
        duration = ""
        j = i + 1
        if j < n and DATE_PATTERN.search(lines[j]):
            duration = lines[j]
            j += 1
        return {"title": title, "company": company, "duration": duration}, j

    title = line
    company = ""
    duration = ""
    j = i + 1

    if category == "job":
        if j < n and not DATE_PATTERN.search(lines[j]) and not _is_noise_line(lines[j]):
            company = lines[j]
            j += 1

        for k in range(j, min(j + 2, n)):
            if DATE_PATTERN.search(lines[k]):
                duration = lines[k]
                j = k + 1
                break
    else:
        # Projects / Research: keep each card to just a title, plus a
        # venue/duration line if one directly follows (e.g. "Published:
        # IJCRT", "ICICT 2026", or a date range). Skip over any wrapped
        # description lines belonging to this same entry — absorb and
        # discard them instead of turning them into separate cards.
        while j < n:
            nxt = lines[j]
            if DATE_PATTERN.search(nxt):
                duration = nxt
                j += 1
                break
            if _is_venue_line(nxt) and not duration:
                duration = nxt
                j += 1
                break
            if _looks_like_project_title(nxt) or is_section_header(nxt):
                break
            j += 1

    return {"title": title, "company": company, "duration": duration}, j


def _extract_entries_from_lines(lines, category, restrict_to_section=True):
    entries = []
    n = len(lines)
    in_section = not restrict_to_section
    i = 0

    is_title_fn = _looks_like_entry_title if category == "job" else _looks_like_project_title

    while i < n:
        line = lines[i]

        if restrict_to_section:
            section = get_section_type(line)
            if section == category:
                in_section = True
                i += 1
                continue
            if section is not None and section != category:
                if in_section:
                    break
                i += 1
                continue
            if not in_section:
                i += 1
                continue
        else:
            if is_section_header(line):
                i += 1
                continue

        if category == "job" and _is_noise_line(line):
            i += 1
            continue

        if category != "job" and not is_title_fn(line):
            i += 1
            continue

        if DATE_PATTERN.search(line) and category == "job" and not TITLE_KEYWORD_RE.search(line):
            i += 1
            continue

        if is_title_fn(line) or (category == "job" and _split_merged_entry(line)):
            entry, next_i = _collect_entry(lines, i, n, category=category)
            if entry["title"]:
                entries.append(entry)
            i = next_i
            continue

        i += 1

    return entries


def extract_experience(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    has_job_header = any(get_section_type(l) == "job" for l in lines)

    if has_job_header:
        entries = _extract_entries_from_lines(lines, "job", restrict_to_section=True)
        if entries:
            return entries

    return _extract_entries_from_lines(lines, "job", restrict_to_section=False)


def extract_projects(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not any(get_section_type(l) == "project" for l in lines):
        return []
    return _extract_entries_from_lines(lines, "project", restrict_to_section=True)


def extract_research(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not any(get_section_type(l) == "research" for l in lines):
        return []
    return _extract_entries_from_lines(lines, "research", restrict_to_section=True)


def extract_experience_highlights(text):
    return extract_experience(text)


def parse_resume_text(text):
    text = clean_text(text)
    lines = [l for l in text.split("\n") if l.strip()]

    name = extract_name(lines)
    email = extract_email(text)
    phone = extract_phone(text)
    skills = extract_skills(text)
    experience = extract_experience(text)
    projects = extract_projects(text)
    research = extract_research(text)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "research": research,
    }


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