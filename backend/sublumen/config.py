import os, secrets, logging
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class Config:
    def __init__(self, **over):
        self.data_dir = os.environ.get("SS_DATA", os.path.join(BASE, "data", "runtime"))
        self.db_uri = os.environ.get("SS_DB", "sqlite:///" + os.path.join(self.data_dir, "app.db"))
        self.models_dir = os.environ.get("SS_MODELS", os.path.join(BASE, "models"))
        secret = os.environ.get("SS_SECRET")
        if not secret:
            logging.getLogger("sublumen").warning("SS_SECRET not set: using a random per-process secret (tokens reset on restart).")
            secret = secrets.token_hex(32)
        self.secret = secret
        self.max_upload_bytes = int(os.environ.get("SS_MAX_UPLOAD", 10 * 1024 * 1024))
        self.max_pixels = int(os.environ.get("SS_MAX_PIXELS", 25_000_000))
        self.token_ttl = int(os.environ.get("SS_TOKEN_TTL", 8 * 3600))
        self.rate_limit = int(os.environ.get("SS_RATE", 120))   # per minute per client
        self.login_rate_limit = int(os.environ.get("SS_LOGIN_RATE", 10))
        for k, v in over.items():
            setattr(self, k, v)
