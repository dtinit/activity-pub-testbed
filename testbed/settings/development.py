from .base import *


ENVIRONMENT = 'development'
DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default='your-dev-secret-key') 
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=['locahost', '127.0.0.1'])

# Seeding settings
SEED_ADMIN_USERNAME = 'admin',
SEED_ADMIN_EMAIL = 'admin@testing.com',
SEED_ADMIN_PASSWORD = 'admin123',

# Database settings
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": env.db_url(
        "DJ_DATABASE_CONN_STRING",
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    )
}
