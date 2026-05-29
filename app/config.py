import os


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    DATABASE_PATH = os.path.join(BASE_DIR, "database", "shop.db")
    LOG_FILE = os.path.join(BASE_DIR, "logs", "app.log")
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024
    SUPPORT_PHONE = "8 (999) 544-01-11"
    SUPPORT_PHONE_TEL = "+79995440111"
