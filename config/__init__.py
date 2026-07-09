import os
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or os.environ.get("SESSION_SECRET")
        or "dev-secret-change-in-production"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Resume upload
    RESUME_UPLOAD_FOLDER = os.path.join(
        os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
        "uploads",
        "resumes",
    )
    MAX_RESUME_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx"}
    ALLOWED_RESUME_MIME_TYPES = {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        "binary/octet-stream",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_REFRESH_EACH_REQUEST = True

    # Remember me
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Auth
    PASSWORD_RESET_TOKEN_MAX_AGE = int(os.environ.get("PASSWORD_RESET_TOKEN_MAX_AGE", 3600))
    BCRYPT_LOG_ROUNDS = int(os.environ.get("BCRYPT_LOG_ROUNDS", 12))

    # Email
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@campushire.ai")

    # App URLs (used in password reset emails)
    APP_NAME = os.environ.get("APP_NAME", "CampusHire AI")
    SERVER_NAME = os.environ.get("SERVER_NAME")
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/campushire",
    )


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    @classmethod
    def init_app(cls, app):
        if not app.config.get("SECRET_KEY") or app.config["SECRET_KEY"] == "dev-secret-change-in-production":
            raise ValueError("SECRET_KEY must be set in production.")
        if not app.config.get("SQLALCHEMY_DATABASE_URI"):
            raise ValueError("DATABASE_URL must be set in production.")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/campushire_test",
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
