from pathlib import Path
import os

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# ⚠️ Segurança
SECRET_KEY = "django-insecure-su61nhhf-^1)jz0_t6rj_c(g%gfg(7rzknh3l&06g0qk5#gck@"
DEBUG = True
ALLOWED_HOSTS = ["*"]  # Em produção, use o domínio do site

# -----------------------
# APPS
# -----------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # App da barbearia
    "barbearia.apps.BarbeariaConfig",
]

# -----------------------
# MIDDLEWARE
# -----------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# -----------------------
# URLs e Templates
# -----------------------
ROOT_URLCONF = "setup.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],  # pasta global
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "setup.wsgi.application"

# -----------------------
# BANCO DE DADOS
# -----------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# -----------------------
# SENHAS E AUTENTICAÇÃO
# -----------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------
# LOCALIZAÇÃO E HORÁRIO
# -----------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Maceio"
USE_I18N = True
USE_TZ = True

# -----------------------
# ARQUIVOS ESTÁTICOS
# -----------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# Caso tenha uploads futuramente (fotos de agendamentos, etc.)
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# -----------------------
# PADRÕES DJANGO
# -----------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------
# LOGIN E REDIRECIONAMENTOS
# -----------------------
LOGIN_URL = "login_admin"
LOGIN_REDIRECT_URL = "painel_admin"
LOGOUT_REDIRECT_URL = "login_admin"

# -----------------------
# CONFIGURAÇÃO DE E-MAIL
# -----------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if os.getenv("EMAIL_HOST")
    else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1").lower() in {"1", "true", "yes"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0").lower() in {"1", "true", "yes"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@barbearia.com")
