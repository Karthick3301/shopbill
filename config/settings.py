"""Django settings for ShopBill.

- Secrets come from environment variables, never hardcoded.
- SQLite by default (local dev); PostgreSQL on Render via DATABASE_URL.
- With DEBUG=False (production default) HTTPS/HSTS/secure cookies turn on.
"""

import os
import sys
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Local .env file for development (ignored if absent). Real environment
# variables always win, so Render's dashboard values keep working as before.
load_dotenv(BASE_DIR / ".env")

# Dev-only fallback so tests/runserver work without an .env file.
# Production MUST set DJANGO_SECRET_KEY in the environment.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-do-not-use-in-production",
)

# Production default is False; local dev sets DJANGO_DEBUG=True in .env.
DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver"
    ).split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    h.strip() for h in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if h.strip()
]

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    # Production (Render): PostgreSQL, connections persist across requests.
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    # Local development: SQLite file in the project root.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps.
    "accounts",
    "inventory",
    "billing",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves static files in production (Render has no separate web server).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level templates (base.html, home, registration, errors).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"  # shop local time: "today" and monthly grouping use IST
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target for Render
STATICFILES_DIRS = [BASE_DIR / "static"]  # project static (css/app.css, favicon)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Compressed + hashed filenames so browsers cache safely.
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user with an Owner/Staff role field (see accounts/models.py).
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

# Plain-http Django test client still needs to work, so skip HTTPS
# enforcement while running the test suite; Render/production unaffected.
_RUNNING_TESTS = "pytest" in sys.modules or "test" in sys.argv

if not DEBUG and not _RUNNING_TESTS:
    # Render terminates TLS at its proxy and forwards http internally.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
