# 🎯 JobTracker AI — Production-Ready Job Application Dashboard

A full-stack AI-powered job tracking dashboard with glassmorphism UI.
Built with Flask, SQLite, Groq LLM, and RapidAPI.

---

## 📁 Project Structure

```
jobtracker/
├── app.py                    # Flask app factory & entry point
├── database.py               # SQLite connection & init
├── schema.sql                # DB schema (resumes, jobs, reminders)
├── requirements.txt
├── .env.example
├── routes/
│   ├── __init__.py
│   ├── dashboard.py          # /  /api/stats  /api/jobs/table
│   ├── resume.py             # /resume/  /resume/upload  /resume/list
│   ├── jobs.py               # /jobs/  /jobs/scrape  /jobs/add
│   ├── ai_suggestions.py     # /ai/  /ai/analyze  /ai/cover-letter
│   └── reminders.py          # /reminders/ CRUD
├── static/
│   ├── css/main.css          # Full glassmorphism dark UI
│   └── js/utils.js           # Toast, API helper, sidebar toggle
├── templates/
│   ├── base.html             # Sidebar + Topbar layout
│   ├── dashboard.html        # Stats cards + jobs table
│   ├── resume.html           # Drag & drop upload + parsed data
│   ├── jobs.html             # Scraper form + manual add
│   ├── ai_suggestions.html   # AI match analysis + cover letter
│   └── reminders.html        # Reminder CRUD with quick-add
└── uploads/                  # Uploaded resume files (auto-created)
```

---

## 🚀 Quick Start (Step by Step)

### 1. Clone / extract the project
```bash
cd jobtracker
```

### 2. Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your keys:
```
GROQ_API_KEY=gsk_...           # https://console.groq.com
RAPIDAPI_KEY=...               # https://rapidapi.com (JSearch API)
SECRET_KEY=any-random-string
DATABASE=resume_jobs.db
UPLOAD_FOLDER=uploads
```
> ⚠️ The app works WITHOUT API keys using demo/fallback data.

### 5. Run the app
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```

---

## 🌐 Pages

| URL | Page |
|-----|------|
| `/` | Dashboard — stats cards + jobs table |
| `/resume/` | Resume upload + auto-parse (PDF/DOCX/TXT) |
| `/jobs/` | Job scraper + manual job entry |
| `/ai/` | AI match analysis + cover letter |
| `/reminders/` | Follow-up reminders with quick-add |

---

## 🔌 API Endpoints

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Get application counts |
| GET | `/api/jobs/table` | Get all jobs |
| PATCH | `/api/jobs/<id>/status` | Update job status |
| DELETE | `/api/jobs/<id>` | Delete a job |

### Resume
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/resume/upload` | Upload & parse resume |
| GET | `/resume/list` | List all uploaded resumes |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs/scrape` | Search via RapidAPI JSearch |
| POST | `/jobs/add` | Add job manually |

### AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ai/analyze` | Match score + suggestions (Groq) |
| POST | `/ai/cover-letter` | Generate cover letter (Groq) |

### Reminders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/reminders/add` | Create reminder |
| GET | `/reminders/list` | List all reminders |
| PATCH | `/reminders/<id>/status` | Update status |
| DELETE | `/reminders/<id>` | Delete reminder |

---

## 🗄️ Database Schema

```sql
-- resumes: id, filename, original_name, name, email, phone, skills (JSON), experience (JSON), raw_text
-- jobs:    id, title, company, location, description, url, source, status, match_score, notes, applied_at
-- reminders: id, job_id (FK), title, message, remind_at, status (pending/done/dismissed)
```

---

## 🎨 UI Features

- **Dark glassmorphism** — `#070B14` → `#0F172A` gradient + blur cards
- **Neon accents** — purple/blue/cyan/green/red per context
- **Fixed sidebar** — with active state indicator
- **Sticky topbar** — search + notifications + avatar
- **Status badges** — color-coded (saved/applied/followed_up/offered/rejected)
- **Match score bar** — visual progress indicator
- **Drag & drop** — resume upload zone
- **Toast notifications** — non-blocking success/error/info
- **Responsive** — mobile sidebar toggle
- **Smooth animations** — fade-up stagger on page load

---

## 📦 Dependencies

```
flask==3.0.3
flask-cors==4.0.1
python-dotenv==1.0.1
groq==0.9.0
requests==2.32.3
PyPDF2==3.0.1
python-docx==1.1.2
Werkzeug==3.0.4
```

---

## 🔑 API Keys

| Service | How to get |
|---------|-----------|
| **Groq** | https://console.groq.com → API Keys |
| **RapidAPI / JSearch** | https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch → Subscribe (free tier available) |

> Both services have **free tiers**. The app runs in demo mode without keys.
