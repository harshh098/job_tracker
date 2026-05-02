import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from database import init_db

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    CORS(app)

    upload_folder = os.path.join(os.getcwd(), os.getenv("UPLOAD_FOLDER", "uploads"))
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    with app.app_context():
        init_db()

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.resume import resume_bp
    from routes.jobs import jobs_bp
    from routes.ai_suggestions import ai_bp
    from routes.reminders import reminders_bp
    from routes.settings import settings_bp
    from routes.profile import profile_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(resume_bp, url_prefix="/resume")
    app.register_blueprint(jobs_bp, url_prefix="/jobs")
    app.register_blueprint(ai_bp, url_prefix="/ai")
    app.register_blueprint(reminders_bp, url_prefix="/reminders")
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(profile_bp, url_prefix="/profile")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)