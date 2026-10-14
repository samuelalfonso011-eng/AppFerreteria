import os
from dotenv import load_dotenv

# Cargar variables del archivo .env si existe
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))


def normalize_db_url(url: str | None) -> str:
    """
    Normaliza la cadena de conexión de PostgreSQL para Supabase.
    Asegura el uso del driver moderno psycopg v3 (postgresql+psycopg://).
    """
    if not url:
        # Base de datos local SQLite para desarrollo seguro antes de configurar Supabase
        return f"sqlite:///{os.path.join(basedir, 'ferreteria_local.db')}"
    
    # Manejar formatos comunes de proveedores cloud
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    return url


class Config:
    """Configuración base de la aplicación."""
    SECRET_KEY = os.getenv("SECRET_KEY", "ferreteria-dev-secret-key-must-change-in-production-2026")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Base de datos
    SQLALCHEMY_DATABASE_URI = normalize_db_url(os.getenv("DATABASE_URL"))
    
    # Opciones de motor para alta resiliencia y reciclaje de conexiones con Supabase
    # Si la URL es SQLite, evitamos pool options incompatibles
    if "sqlite" in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_ENGINE_OPTIONS = {}
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    
    # Almacenamiento local de imágenes
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads', 'products')
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5MB máximo
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Seguridad de sesiones y cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Caché y optimización de estáticos (12 horas por defecto)
    SEND_FILE_MAX_AGE_DEFAULT = int(os.getenv("SEND_FILE_MAX_AGE_DEFAULT", 43200))


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Configuración para pruebas automatizadas (pytest)."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(Config):
    """Configuración para producción."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
