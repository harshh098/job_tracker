# 🚀 JobTracker AI — Smart Job Application Dashboard

An AI-powered full-stack job tracking platform that helps users manage applications, analyze resumes, and get intelligent job recommendations — all in one place.

---

## ✨ Overview

JobTracker AI simplifies the job search process by combining:
- Automation ⚡
- AI insights 🤖
- Clean dashboard UI 📊

It allows users to track jobs, upload resumes, and get personalized suggestions efficiently.

---

## 🔥 Key Features

- 📊 **Dashboard** — Track all job applications in one place  
- 🔍 **Job Scraper** — Fetch jobs using RapidAPI  
- 🤖 **AI Suggestions** — Match jobs using LLM (Groq)  
- 📄 **Resume Parser** — Extract skills, experience, contact info  
- 🔔 **Reminders System** — Manage follow-ups  
- 🔐 **Authentication** — Email + OTP login (Twilio)  
- 🔑 **Forgot Password** — OTP-based reset  
- 👤 **Profile Management** — Real-time updates  

---

## 🎨 UI Highlights

- Dark **Glassmorphism UI**  
- Sidebar + Topbar layout  
- Smooth animations  
- Toast notifications  
- Drag & Drop resume upload  
- Responsive design  

---

## 🛠 Tech Stack

| Layer | Technology |
|------|-----------|
| Backend | Flask (Python) |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| APIs | Twilio, Groq, RapidAPI |
| Parsing | PyPDF2, python-docx |

## 📁 Project Structure

jobtracker/
├── app.py
├── database.py
├── schema.sql
├── routes/
├── templates/
├── static/
├── uploads/
├── requirements.txt
└── .gitignore

---

## ⚙️ Installation & Setup

```bash
git clone https://github.com/harshh098/job_tracker.git
cd job_tracker

# create virtual environment
python -m venv venv
venv\Scripts\activate   # Windows

# install dependencies
pip install -r requirements.txt

# run app
python app.py

🔐 Environment Variables

SECRET_KEY=your_secret_key
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=your_number
GROQ_API_KEY=your_key
RAPIDAPI_KEY=your_key

🔌 API Endpoints (Important)
Dashboard
GET /api/stats
GET /api/jobs/table

Jobs
POST /jobs/scrape
POST /jobs/add

Resume
POST /resume/upload
GET /resume/list

AI
POST /ai/analyze
POST /ai/cover-letter

Reminders
POST /reminders/add
GET /reminders/list

💡 Future Improvements
Advanced AI job matching
Email notifications
Cloud deployment (AWS / Render)
Multi-user support

Create .env file:
## 📁 Project Structure
