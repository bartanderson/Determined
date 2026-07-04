import os

DATABASE = os.environ.get("COMMONPLACE_DB", "commonplace.db")
DEBUG = os.environ.get("DEBUG", "0") == "1"
TAGGING_ENABLED = False
