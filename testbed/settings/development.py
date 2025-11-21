# ruff: noqa: F405, F403
import os
from .base import *

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

ENVIRONMENT = "development"
DEBUG = True
ALLOWED_SEED_COMMAND = True
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="your-dev-secret-key")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
BASE_URL = "http://localhost:8000"

# Seeding settings
SEED_ADMIN_USERNAME = "admin"
SEED_ADMIN_EMAIL = "admin@seeding.com"
SEED_ADMIN_PASSWORD = "admin123"

# Test users for login testing (each with both source and destination actors)
SEED_TEST_USERS = [
    {
        "username": "login_user_1",
        "email": "login_user_1@seeding.com",
        "password": "testpass123"
    },
    {
        "username": "login_user_2", 
        "email": "login_user_2@seeding.com",
        "password": "testpass123"
    }
]

# Database: Inherits SQLite from base.py

if DEBUG:
    LOGGING["handlers"]["structured_file"] = {
        "class": "logging.FileHandler", # FileHandler overwrites on each run
        "filename": os.path.join(LOGS_DIR, "structured.log"),
        "formatter": "key_value",
        "mode": "w", # 'w' overwrites the file each time
    }

    LOGGING["loggers"].update({
        # Comment out this section and comment the section below to see django_structlog output in console
        # "django_structlog": {
        #     "handlers": ["console"],
        #     "level": "INFO",
        # },

        # Current active configuration - writes to file, overwriting on each server start
        "django_structlog": {
            "handlers": ["structured_file"],
            "level": "INFO",
        },

    })
