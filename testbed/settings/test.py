# ruff: noqa: F405, F403
from .base import *


ENVIRONMENT = 'test'
DEBUG = False

ALLOWED_SEED_COMMAND = True
SEED_ADMIN_USERNAME = 'admin'
SEED_ADMIN_EMAIL = 'admin@testing.com'
SEED_ADMIN_PASSWORD = 'admin123'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:", # Using in-memory database for testing
    }
}

# Faster password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Minimal logging for faster tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default='your-dev-secret-key') 
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=['locahost', '127.0.0.1'])
