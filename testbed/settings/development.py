from .base import *

DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default='your-dev-secret-key') 
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=['locahost', '127.0.0.1'])

DATABASES = {
    "default": env.db_url(
        "DJ_DATABASE_CONN_STRING",
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    )
}
