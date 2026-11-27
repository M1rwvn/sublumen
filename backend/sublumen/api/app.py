import os
from flask import Flask, jsonify, send_from_directory
from .. import __version__
from .. import models as m
from ..config import Config
from ..evidence_svc import service as ev_svc
from ..security import auth
from .routes import bp

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FRONTEND = os.path.join(_ROOT, "frontend-react", "dist") if os.path.exists(os.path.join(_ROOT, "frontend-react", "dist", "index.html")) else os.path.join(_ROOT, "frontend")

def create_app(cfg=None):
    cfg = cfg or Config()
    os.makedirs(cfg.data_dir, exist_ok=True)
    app = Flask(__name__, static_folder=None)
    app.config_obj, app.version = cfg, __version__
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_upload_bytes + 64 * 1024
    app.engine, app.db = m.make_session(cfg.db_uri)
    app.tokens, app.limiter = auth.Tokens(cfg.secret, cfg.token_ttl), auth.RateLimiter()
    with m.startup_lock(app.engine):
        ev_svc.sync_models(app.db, cfg.models_dir)
        ev_svc.sync_benchmarks(app.db, os.environ.get('SS_DOCS', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'docs'))))
        email, pw = os.environ.get("SS_ADMIN_EMAIL"), os.environ.get("SS_ADMIN_PASSWORD")
        if email and pw and not app.db.query(m.User).filter_by(email=email.lower()).first():
            app.db.add(m.User(email=email.lower(), role="admin", password_hash=auth.hash_password(pw))); app.db.commit()
    app.register_blueprint(bp)

    @app.errorhandler(413)
    def _big(e): return jsonify({"status": "error", "code": "too_large", "message": "Upload too large."}), 413
    @app.errorhandler(404)
    def _nf(e): return jsonify({"status": "error", "code": "not_found", "message": "Not found."}), 404
    @app.errorhandler(Exception)
    def _any(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"status": "error", "code": e.name.lower().replace(' ', '_'), "message": e.description}), e.code
        app.logger.exception("unhandled error")  # stack trace to server log only, never to the client
        return jsonify({"status": "error", "code": "internal", "message": "Internal error."}), 500
    @app.teardown_appcontext
    def _rm(exc): app.db.remove()

    @app.get("/")
    def index(): return send_from_directory(FRONTEND, "index.html")
    @app.get("/static/<path:p>")
    def static_files(p): return send_from_directory(FRONTEND, p)
    return app
