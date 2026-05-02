import os
import json
import re
from flask import Blueprint, request, jsonify, current_app, render_template, session
from werkzeug.utils import secure_filename
from database import get_db
from routes.auth_utils import login_required

resume_bp = Blueprint("resume", __name__)
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()
    if ext == "txt":
        with open(filepath, "r", errors="ignore") as f:
            return f.read()
    elif ext == "pdf":
        try:
            import PyPDF2
            text = []
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text() or "")
            return "\n".join(text)
        except Exception as e:
            return f"Error reading PDF: {e}"
    elif ext == "docx":
        try:
            import docx
            doc = docx.Document(filepath)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception as e:
            return f"Error reading DOCX: {e}"
    return ""


def parse_resume_text(text):
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    email = email_match.group() if email_match else ""
    phone_match = re.search(r"(\+?\d[\d\s\-().]{8,15}\d)", text)
    phone = phone_match.group().strip() if phone_match else ""
    name = ""
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line.split()) >= 2 and len(line) < 60 and "@" not in line:
            name = line
            break
    skill_keywords = [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "ruby",
        "react", "vue", "angular", "node", "flask", "django", "fastapi", "express",
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
        "git", "linux", "html", "css", "rest", "graphql", "machine learning",
        "deep learning", "nlp", "data science", "pandas", "numpy", "tensorflow", "pytorch",
        "spark", "hadoop", "kafka", "airflow", "dbt", "tableau", "power bi",
        "agile", "scrum", "jira", "figma", "photoshop"
    ]
    text_lower = text.lower()
    skills = [s for s in skill_keywords if s in text_lower]
    experience = []
    exp_pattern = re.findall(r"(.{10,80}(?:20\d{2}|19\d{2}).{0,80})", text)
    for e in exp_pattern[:6]:
        experience.append(e.strip())
    return {"name": name, "email": email, "phone": phone, "skills": skills, "experience": experience}


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
    parsed = parse_resume_text(raw_text)

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO resumes (user_id, filename, original_name, name, email, phone, skills, experience, raw_text) VALUES (?,?,?,?,?,?,?,?,?)",
                (uid, filename, file.filename, parsed["name"], parsed["email"], parsed["phone"],
                 json.dumps(parsed["skills"]), json.dumps(parsed["experience"]), raw_text[:5000])
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
                "SELECT id, original_name, name, email, phone, skills, experience, uploaded_at FROM resumes WHERE user_id=? ORDER BY uploaded_at DESC",
                (uid,)
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
            rows = conn.execute("SELECT filename FROM resumes WHERE user_id=?", (uid,)).fetchall()
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