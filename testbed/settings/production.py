# ruff: noqa: F405, F403
from .base import *


ENVIRONMENT = "production"
DEBUG = False
ALLOWED_SEED_COMMAND = False  # Prevents seeding from being run in production
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

DATABASES = {"default": env.db_url("DJ_DATABASE_CONN_STRING")}

# HTTPS/SSL settings
# https://docs.djangoproject.com/en/5.1/topics/security/#ssl-https
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT")
proxy_header = env.str("SECURE_PROXY_SSL_HEADER")
SECURE_PROXY_SSL_HEADER = tuple(proxy_header.split(",")) if proxy_header else None

# SSL-related security settings
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD")

# Cookie and security headers
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE")
SECURE_BROWSER_XSS_FILTER = env.bool("SECURE_BROWSER_XSS_FILTER")
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF")
