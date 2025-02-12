from .base import *

DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS") + ['testserver']

DATABASES = {
    "default": env.db_url("DJ_DATABASE_CONN_STRING")
}
