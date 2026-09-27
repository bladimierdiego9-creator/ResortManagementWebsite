import os
import socket
from datetime import timedelta
from urllib.parse import quote, urlparse

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _is_reachable(url):
    """Return True if the host in url can be TCP-connected."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = parsed.hostname
    port = parsed.port or 5432

    if not hostname or hostname in {'localhost', '127.0.0.1'}:
        return True

    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNSPEC):
        try:
            results = socket.getaddrinfo(hostname, port, family, socket.SOCK_STREAM)
            if not results:
                continue
            ip, actual_port = results[0][4][:2]
            s = socket.socket(results[0][0], socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, actual_port))
            s.close()
            return True
        except Exception:
            continue

    return False


def _to_psycopg_url(url):
    """Convert postgresql:// to postgresql+psycopg:// for SQLAlchemy."""
    return (url
            .replace('postgresql://', 'postgresql+psycopg://', 1)
            .replace('postgres://', 'postgresql+psycopg://', 1))


def get_database_url():
    # 1. Direct Supabase connection (port 5432, IPv6 only — may not work on all networks)
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

    if direct_url and _is_reachable(direct_url):
        print("[DB] Connected via direct Supabase URL")
        return _to_psycopg_url(direct_url)

    # 2. Supabase session-mode pooler (IPv4, port 5432 on pooler host)
    #    Session mode fully supports prepared statements — no workarounds needed
    pooler_url = os.environ.get('DATABASE_POOLER_URL')
    if pooler_url and _is_reachable(pooler_url):
        print("[DB] Connected via Supabase session pooler (IPv4)")
        return _to_psycopg_url(pooler_url)

    # 3. Local SQLite fallback
    local_url = os.environ.get('LOCAL_DATABASE_URL') or (
        'sqlite:///' + os.path.join(basedir, 'thysia_local.db')
    )
    print(f"[DB] Supabase unreachable — using local DB: {local_url}")
    return local_url


_db_url = get_database_url()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'thysia-dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'connect_args': {'connect_timeout': 10},
    }
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
