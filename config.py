import os
from datetime import timedelta
from urllib.parse import quote

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'), override=True)


def _to_psycopg_url(url):
    """Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy."""
    return (url
            .replace('postgresql://', 'postgresql+psycopg://', 1)
            .replace('postgres://', 'postgresql+psycopg://', 1))


def get_database_url():
    # Vercel functions are short-lived. Avoid probing the database with a
    # separate socket connection at import time; use the configured Supabase
    # pooler URL directly and let SQLAlchemy establish the actual connection.
    # Falling back to a local SQLite file is not viable in a serverless
    # deployment because its filesystem is not a persistent writable database.
    if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
        vercel_url = (
            os.environ.get('DATABASE_POOLER_URL')
            or os.environ.get('DATABASE_URL')
        )
        if not vercel_url:
            raise RuntimeError(
                'Set DATABASE_POOLER_URL in the Vercel Production environment.'
            )
        print('[DB] Using configured Supabase URL on Vercel')
        return _to_psycopg_url(vercel_url)

    # Prefer the Supabase session pooler for local development. Do not silently
    # switch to SQLite when a configured remote database is temporarily
    # unreachable: the scanner writes to Supabase, so the admin app must read
    # from that same database.
    pooler_url = os.environ.get('DATABASE_POOLER_URL')
    if pooler_url:
        print('[DB] Using configured Supabase session pooler')
        return _to_psycopg_url(pooler_url)

    # Direct Supabase connection (port 5432; may require IPv6).
    direct_url = os.environ.get('DATABASE_URL')
    if not direct_url:
        host     = os.environ.get('SUPABASE_HOST')
        port     = os.environ.get('SUPABASE_PORT', '5432')
        database = os.environ.get('SUPABASE_DATABASE') or 'postgres'
        user     = os.environ.get('SUPABASE_USER') or 'postgres'
        password = os.environ.get('SUPABASE_PASSWORD') or ''
        if host and user:
            direct_url = (
                f"postgresql://{user}:{quote(password, safe='')}@{host}:{port}/{database}"
            )

    if direct_url:
        print("[DB] Using configured direct Supabase URL")
        return _to_psycopg_url(direct_url)

    # Use local SQLite only when no Supabase database URL is configured.
    local_url = os.environ.get('LOCAL_DATABASE_URL') or (
        'sqlite:///' + os.path.join(basedir, 'data', 'thysia_local.db')
    )
    print(f"[DB] Supabase unreachable — using local DB: {local_url}")
    return local_url


_db_url = get_database_url()

# SQLite doesn't support connect_timeout — only pass it for Postgres
_is_sqlite = _db_url.startswith('sqlite')
_engine_options = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 10,
    'max_overflow': 20,
}
if not _is_sqlite:
    _engine_options['connect_args'] = {'connect_timeout': 10}


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'thysia-dev-secret-key-change-in-production'
    RFID_DEVICE_TOKEN = os.environ.get('RFID_DEVICE_TOKEN', '')
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    # Session config — persistent, survives browser close
    SESSION_COOKIE_HTTPONLY  = True        # JS cannot read the cookie
    SESSION_COOKIE_SAMESITE  = 'Lax'      # CSRF protection
    SESSION_COOKIE_SECURE    = False       # set True only when using HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # stay logged in for 7 days
    REMEMBER_COOKIE_DURATION   = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY   = True
    REMEMBER_COOKIE_SAMESITE   = 'Lax'

    # Image upload config — photos are stored in the database as base64, so no
    # upload folder is needed anywhere on disk.
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Email/SMTP configuration for password reset
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_TIMEOUT = int(os.environ.get('MAIL_TIMEOUT') or 20)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')

    # Firebase configuration for announcements
    FIREBASE_CREDENTIALS = os.environ.get('FIREBASE_CREDENTIALS') or os.path.join(basedir, 'firebase-credentials.json')
