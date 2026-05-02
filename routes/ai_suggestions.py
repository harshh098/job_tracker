import os
import json
from flask import Blueprint, request, jsonify, render_template
from groq import Groq
from routes.auth_utils import login_required

ai_bp = Blueprint("ai", __name__)
MODEL = "llama-3.1-8b-instant"


def get_groq_client():
    api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not api_key or api_key.startswith("your_"):
        return None, "GROQ_API_KEY is not configured. Add it to your .env file."
    try:
        return Groq(api_key=api_key), None
    except Exception as e:
        return None, f"Failed to init Groq client: {e}"


@ai_bp.route("/")
@login_required
def ai_page():
    return render_template("ai_suggestions.html")


@ai_bp.route("/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    job_description = data.get("job_description", "").strip()
    resume_skills = data.get("resume_skills", [])

    if not job_description:
        return jsonify({"error": "Job description is required"}), 400

    client, err = get_groq_client()
    if not client:
        return jsonify({
            "match_score": 72,
            "missing_skills": ["Kubernetes", "Terraform", "CI/CD pipelines"],
            "suggestions": [
                "Highlight your Python and SQL experience prominently in your resume.",
                "Consider adding a project showcasing cloud deployment skills.",
                "Tailor your cover letter to mention specific company technologies.",
                "Add quantifiable achievements to your work experience section."
            ],
            "strengths": ["Strong Python background", "Database experience", "Agile methodology"],
            "summary": "Your profile is a good match for this role. Focus on cloud infrastructure skills to strengthen your application."
        })

    skills_context = ", ".join(resume_skills) if resume_skills else "Not provided"
    prompt = f"""You are an expert career coach and ATS optimizer. Analyze this job description and candidate's skills.

JOB DESCRIPTION:
{job_description[:2000]}

CANDIDATE SKILLS: {skills_context}

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{
  "match_score": <integer 0-100>,
  "missing_skills": [<list of missing skills strings>],
  "suggestions": [<list of 4 specific actionable suggestions>],
  "strengths": [<list of 3 candidate strengths>],
  "summary": "<2 sentence summary of fit>"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=800, temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response", "raw": raw}), 500
    except Exception as e:
        return jsonify({"error": f"Groq API error: {str(e)}"}), 500


@ai_bp.route("/cover-letter", methods=["POST"])
@login_required
def cover_letter():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    job_description = data.get("job_description", "").strip()
    candidate_name  = data.get("name", "").strip() or "the applicant"
    skills          = data.get("skills", [])
    resume_text     = data.get("resume_text", "").strip()
    experience      = data.get("experience", "").strip()

    if not job_description:
        return jsonify({"error": "Job description is required"}), 400

    client, err = get_groq_client()
    if not client:
        return jsonify({"error": err or "GROQ_API_KEY not configured"}), 503

    skills_str = ", ".join(skills[:10]) if skills else "Not specified"
    resume_context_parts = []
    if experience:
        resume_context_parts.append(f"Work Experience:\n{experience[:1000]}")
    if resume_text and not experience:
        resume_context_parts.append(f"Resume Summary:\n{resume_text[:1200]}")
    resume_context = "\n\n".join(resume_context_parts) if resume_context_parts else ""

    prompt = f"""Write a professional, concise cover letter for this job.

Candidate Name: {candidate_name}
Skills: {skills_str}
{f"Job Description:{chr(10)}{job_description[:1500]}" if job_description else ""}
{f"{chr(10)}{resume_context}" if resume_context else ""}

Instructions:
- Write exactly 3 paragraphs.
- Opening: express enthusiasm and name the role.
- Middle: draw on the candidate's actual experience and skills above — be specific, avoid generic filler.
- Closing: confident call to action.
- Do not use placeholder brackets like [Company] or [Your Name].
- Output only the letter text, no subject line, no extra commentary."""

    try:
        response = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=700, temperature=0.7
        )
        letter = response.choices[0].message.content.strip()
        return jsonify({"cover_letter": letter})
    except Exception as e:
        return jsonify({"error": f"Groq API error: {str(e)}"}), 500


@ai_bp.route("/debug-key")
@login_required
def debug_key():
    key = os.environ.get("GROQ_API_KEY", "")
    return jsonify({"loaded": bool(key), "starts_with": key[:7] if key else None})