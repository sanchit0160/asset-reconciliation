import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = "change-this-secret-key"
DB_PATH = f"sqlite:///{BASE_DIR}/reconciliation.db"

ITAM_DIR = os.path.join(BASE_DIR, "data", "itam")
ACTIVE_DIR = os.path.join(BASE_DIR, "data", "active_services")