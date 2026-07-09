import os

from flask import Flask
from dotenv import load_dotenv

from app.errors import register_error_handlers
from app.extensions import bcrypt, csrf, db, login_manager
from config import config_by_name


def create_app(config_name=None):
    load_dotenv()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    config_obj = config_by_name[config_name]
    app.config.from_object(config_obj)
    if hasattr(config_obj, "init_app"):
        config_obj.init_app(app)

    if config_name == "development":
        app.config.setdefault("MAIL_SUPPRESS_SEND", True)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)

    return app


def register_extensions(app):
    @login_manager.user_loader
    def load_user(user_id):
        from app.auth.services import AuthService

        return AuthService.load_user_by_id(user_id)

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        from flask import flash, redirect, request, url_for

        flash("Please sign in to access this page.", "warning")
        return redirect(url_for("auth.login", next=request.url))

    import app.models  # noqa: F401 — register SQLAlchemy models


def register_blueprints(app):
    from app.admin import admin_bp
    from app.auth import auth_bp
    from app.main import main_bp
    from app.recruiter import recruiter_bp
    from app.student import student_bp
    from app.tpo import tpo_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(tpo_bp, url_prefix="/tpo")
    app.register_blueprint(recruiter_bp, url_prefix="/recruiter")
    app.register_blueprint(admin_bp, url_prefix="/admin")
