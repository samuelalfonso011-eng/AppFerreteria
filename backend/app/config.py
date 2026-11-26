import os
import secrets
from datetime import timedelta
from decimal import Decimal

from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


def normalize_db_url(url):
    if not url:
        return None
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _engine_options(uri):
    if not uri or uri.startswith("sqlite"):
        return {}
    return {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 15,
        "connect_args": {"connect_timeout": 10},
    }


class Config:
    ML_ARTIFACT_DIR = os.getenv("ML_ARTIFACT_DIR") or os.path.join(BACKEND_DIR, "ml_artifacts")
    ML_LABEL_FILE = os.getenv("ML_LABEL_FILE")
    ML_EPOCHS = 16
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = normalize_db_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sesion: cookie firmada, inaccesible desde JS, con vida limitada
    SESSION_COOKIE_NAME = "ferrepro_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_ABSOLUTE_SECONDS = 12 * 3600

    # Las peticiones JSON de la API son pequenas; cualquier cosa mayor se rechaza
    MAX_CONTENT_LENGTH = 64 * 1024

    TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
    TRUSTED_HOSTS = [h.strip() for h in os.getenv("TRUSTED_HOSTS", "").split(",") if h.strip()] or None

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"

    CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
    ORDER_PENDING_EXPIRY_MINUTES = int(os.getenv("ORDER_PENDING_EXPIRY_MINUTES", "2880"))
    INVOICE_TAX_RATE = Decimal(os.getenv("INVOICE_TAX_RATE", "0"))
    AUTO_CREATE_DB = False
    FRONTEND_DIR = PROJECT_ROOT

    # Cuentas: vida de los enlaces enviados por correo (segundos)
    PASSWORD_RESET_MAX_AGE = int(os.getenv("PASSWORD_RESET_MAX_AGE", "1800"))        # 30 minutos
    ACCOUNT_ACTIVATION_MAX_AGE = int(os.getenv("ACCOUNT_ACTIVATION_MAX_AGE", "172800"))  # 48 horas
    # URL publica para los enlaces de los correos; vacio = el host de la peticion (validado por TRUSTED_HOSTS)
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    # Correo saliente (SMTP). La activacion requiere un servidor configurado.
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "FerrePro")
    SMTP_SSL = os.getenv("SMTP_SSL", "false").lower() in ("1", "true", "yes")
    SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes")


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    AUTO_CREATE_DB = False


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-" + "x" * 32
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AUTO_CREATE_DB = True
    ORDER_PENDING_EXPIRY_MINUTES = 0


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
