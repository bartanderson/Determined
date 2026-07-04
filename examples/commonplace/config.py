import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    DATABASE = os.path.join(BASE_DIR, "commonplace.db")
    LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://localhost:8080")
    TAGGING_ENABLED = os.environ.get("TAGGING_ENABLED", "false").lower() == "true"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
