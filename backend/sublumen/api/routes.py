import base64, functools, hashlib, io, json, os
from flask import Blueprint, Response, current_app, g, jsonify, request, send_file
from .. import models as m
from ..evidence_svc import service as ev_svc
from ..evidence_svc.service import EvidenceError, audit
from ..forensics_core import compare as cmp_mod, visual
from ..forensics_core.analyzer import load_array
from ..report_svc import service as rep_svc
from ..security import auth
from ..security.validation import ValidationError, validate_image, sanitize_text
from ..stego_core import studio
from ..stego_core.crypto import StegoError

bp = Blueprint("api", __name__, url_prefix="/api")

def err(code, message, status=400):
    return jsonify({"status": "error", "code": code, "message": message}), status

def db(): return current_app.db

def client_key(): return (request.headers.get("X-Real-IP") or request.remote_addr or "?")

@bp.before_request
def _rate():
    lim = current_app.config_obj.login_rate_limit if request.path.endswith("/auth/login") else current_app.config_obj.rate_limit
    if not current_app.limiter.allow(client_key() + request.path.split("/")[2:3].__str__(), lim):
        return err("rate_limited", "Too many requests. Slow down.", 429)

def login_required(role=None):
    def deco(fn):
        @functools.wraps(fn)
        def w(*a, **k):
            h = request.headers.get("Authorization", "")
            tok = h[7:] if h.startswith("Bearer ") else None
            data = current_app.tokens.load(tok) if tok else None
            if not data:
                return err("unauthorized", "Login required.", 401)
            u = db().get(m.User, data["uid"])
            if not u:
                return err("unauthorized", "Unknown user.", 401)
            if role == "admin" and u.role != "admin":
                return err("forbidden", "Admin role required.", 403)
            g.user = u
            return fn(*a, **k)
        return w
    return deco

def own_case(case_id):
    c = db().get(m.Case, case_id)
    if not c or (g.user.role != "admin" and c.created_by != g.user.id):
        return None
    return c

def ev_json(e, dup=False):
    return {"id": e.id, "case_id": e.case_id, "name": e.original_name, "sha256": e.sha256, "size_bytes": e.size_bytes,
            "format": e.fmt, "width": e.width, "height": e.height, "uploaded_at": e.uploaded_at.isoformat() + "Z", "duplicate": dup}

def upload():
    f = request.files.get("file") or request.files.get("image")
    if not f:
        raise ValidationError("no_file", "Attach an image as form field 'file'.")
    data = f.read(current_app.config_obj.max_upload_bytes + 1)
    return data, f.filename or ""

@bp.errorhandler(ValidationError)
def _ve(e): return err(e.code, e.message, e.status)
@bp.errorhandler(EvidenceError)
def _ee(e): return err(e.code, e.message, e.status)
@bp.errorhandler(StegoError)
def _se(e): return err(e.code, e.message, 400 if e.code != "auth_failed" else 422)

@bp.get("/health")
def health():
    return jsonify({"status": "ok", "version": current_app.version})

# ---------- auth ----------
@bp.post("/auth/login")
def login():
    b = request.get_json(silent=True) or {}
    u = db().query(m.User).filter_by(email=(b.get("email") or "").lower()).first()
    if not u or not auth.verify_password(u.password_hash, b.get("password") or ""):
        audit(db(), None, "auth.login_failed", email=sanitize_text(b.get("email"), 100)); db().commit()
        return err("bad_credentials", "Wrong email or password.", 401)
    audit(db(), u, "auth.login"); db().commit()
    return jsonify({"status": "ok", "token": current_app.tokens.issue(u.id, u.role), "role": u.role, "email": u.email})

@bp.post("/users")
@login_required("admin")
def create_user():
    b = request.get_json(silent=True) or {}
    email, role = (b.get("email") or "").lower().strip(), b.get("role", "analyst")
    if "@" not in email or role not in ("admin", "analyst"):
        return err("bad_input", "Valid email and role (admin|analyst) required.")
    if db().query(m.User).filter_by(email=email).first():
        return err("exists", "User already exists.", 409)
    try:
        u = m.User(email=email, role=role, password_hash=auth.hash_password(b.get("password") or ""))
    except ValueError as e:
        return err("weak_password", str(e))
    db().add(u); audit(db(), g.user, "user.create", email=email, role=role); db().commit()
    return jsonify({"status": "ok", "id": u.id, "email": email, "role": role}), 201

# ---------- M01 studio ----------
@bp.post("/stego/embed")
@login_required()
def stego_embed():
    data, name = upload()
    info = validate_image(data, name, current_app.config_obj.max_upload_bytes, current_app.config_obj.max_pixels, allowed=("PNG", "BMP"))
    msg = request.form.get("message", "")
    pw = request.form.get("password", "")  # body only; never in the URL, logs or responses
    r = studio.embed(data, msg.encode("utf-8"), pw, keyed=request.args.get("keyed") == "1")
    audit(db(), g.user, "stego.embed", bytes=len(msg.encode())); db().commit()
    if request.args.get("format") == "json":
        return jsonify({"status": "ok", "psnr_db": r["psnr_db"], "ssim": r["ssim"], "payload_rate": r["payload_rate"],
                        "capacity_bytes": r["capacity_bytes"], "stego_png_base64": base64.b64encode(r["stego_png"]).decode()})
    resp = Response(r["stego_png"], mimetype="image/png", headers={"Content-Disposition": 'attachment; filename="stego.png"'})
    resp.headers["X-Stego-PSNR"] = f"{r['psnr_db']:.2f}"; resp.headers["X-Stego-SSIM"] = f"{r['ssim']:.5f}"
    resp.headers["X-Stego-Capacity-Bytes"] = str(r["capacity_bytes"])
    return resp

@bp.post("/stego/extract")
@login_required()
def stego_extract():
    data, name = upload()
    validate_image(data, name, current_app.config_obj.max_upload_bytes, current_app.config_obj.max_pixels, allowed=("PNG", "BMP"))
    msg = studio.extract(data, request.form.get("password", ""))
    audit(db(), g.user, "stego.extract"); db().commit()
    return jsonify({"status": "ok", "message": msg.decode("utf-8", errors="replace"), "bytes": len(msg)})

@bp.post("/stego/capacity")
@login_required()
def stego_capacity():
    data, _ = upload()
    return jsonify({"status": "ok", "capacity_bytes": studio.capacity_bytes(data)})

# ---------- M05 cases & evidence ----------
@bp.post("/cases")
@login_required()
def cases_create():
    title = sanitize_text((request.get_json(silent=True) or {}).get("title"))
    if not title:
        return err("bad_input", "Case title required.")
    c = ev_svc.create_case(db(), g.user, title)
    return jsonify({"status": "ok", "id": c.id, "case_code": c.case_code, "title": c.title}), 201

@bp.get("/cases")
@login_required()
def cases_list():
    q = db().query(m.Case)
    if g.user.role != "admin":
        q = q.filter_by(created_by=g.user.id)
    return jsonify({"status": "ok", "cases": [{"id": c.id, "case_code": c.case_code, "title": c.title, "status": c.status,
                                               "created_at": c.created_at.isoformat() + "Z"} for c in q.order_by(m.Case.id.desc())]})

@bp.get("/cases/<int:cid>")
@login_required()
def case_get(cid):
    c = own_case(cid)
    if not c: return err("not_found", "Case not found.", 404)
    runs = db().query(m.AnalysisRun).join(m.Evidence).filter(m.Evidence.case_id == cid).all()
    reps = db().query(m.Report).filter_by(case_id=cid).all()
    return jsonify({"status": "ok", "id": c.id, "case_code": c.case_code, "title": c.title,
                    "evidence": [ev_json(e) for e in c.evidence],
                    "analyses": [{"run_id": r.id, "evidence_id": r.evidence_id} for r in runs],
                    "reports": [{"id": r.id, "pdf_sha256": r.pdf_sha256} for r in reps]})

@bp.get("/cases/<int:cid>/audit")
@login_required()
def case_audit(cid):
    if not own_case(cid): return err("not_found", "Case not found.", 404)
    rows = db().query(m.AuditEvent).filter_by(case_id=cid).order_by(m.AuditEvent.id).all()
    return jsonify({"status": "ok", "events": [{"id": a.id, "user_id": a.user_id, "action": a.action, "evidence_id": a.evidence_id,
                                                "detail": json.loads(a.detail), "timestamp": a.timestamp.isoformat() + "Z"} for a in rows]})

@bp.post("/evidence")
@login_required()
def evidence_upload():
    case = own_case(int(request.form.get("case_id", 0) or 0))
    if not case: return err("not_found", "Case not found.", 404)
    data, name = upload()
    ev, dup = ev_svc.add_evidence(db(), g.user, case, data, name, current_app.config_obj)
    body = ev_json(ev, dup)
    body["status"] = "ok"
    if dup: body["warning"] = "This exact file (same SHA-256) is already in the case; no new copy stored."
    return jsonify(body), (200 if dup else 201)

def own_evidence(eid):
    e = db().get(m.Evidence, eid)
    if not e or not own_case(e.case_id): return None
    return e

@bp.get("/evidence/<int:eid>")
@login_required()
def evidence_get(eid):
    e = own_evidence(eid)
    if not e: return err("not_found", "Evidence not found.", 404)
    return jsonify({"status": "ok", **ev_json(e)})

@bp.get("/evidence/<int:eid>/visual/<kind>")
@login_required()
def evidence_visual(eid, kind):
    e = own_evidence(eid)
    if not e: return err("not_found", "Evidence not found.", 404)
    data = ev_svc.read_verified(e)  # reads a copy; original untouched
    if kind == "bitplane":
        try:
            png = visual.bitplane_png(data, int(request.args.get("plane", 0)), int(request.args.get("channel", 0)))
        except ValueError:
            return err("bad_input", "plane must be 0-7 and channel 0-2.")
        cap = visual.CAPTIONS["bitplane"]
    elif kind == "heatmap":
        png, cap = visual.heatmap_png(data), visual.CAPTIONS["heatmap"]
    elif kind == "overlay":
        mv = db().query(m.ModelVersion).filter_by(name=ev_svc.DEFAULT_MODEL).first()
        det = ev_svc.get_detector(mv) if mv else None
        if det is None or det.algo != "hgb": return err("bad_input", "The evidence overlay needs the v8 model.", 400)
        png, cap = visual.overlay_png(data, det.tile_grid(data)), visual.CAPTIONS["overlay"]
    else:
        return err("bad_input", "kind must be bitplane, heatmap or overlay.")
    audit(db(), g.user, "visual." + kind, case_id=e.case_id, evidence_id=e.id); db().commit()
    r = Response(png, mimetype="image/png"); r.headers["X-Visual-Caption"] = cap
    return r

# ---------- M02/M03 analysis ----------
@bp.post("/analyses")
@login_required()
def analyses_create():
    b = request.get_json(silent=True) or {}
    e = own_evidence(int(b.get("evidence_id", 0) or 0))
    if not e: return err("not_found", "Evidence not found.", 404)
    out = ev_svc.run_analysis(db(), g.user, e, b.get("model"), use_ml=b.get("use_ml", True))
    return jsonify(out), 201

@bp.get("/analyses/<int:rid>")
@login_required()
def analyses_get(rid):
    r = db().get(m.AnalysisRun, rid)
    if not r or not own_evidence(r.evidence_id): return err("not_found", "Analysis not found.", 404)
    return jsonify(json.loads(r.result_json))

@bp.post("/compare")
@login_required()
def compare():
    a, b = request.files.get("a"), request.files.get("b")
    if not a or not b: return err("no_file", "Attach images as form fields 'a' and 'b'.")
    cfg = current_app.config_obj
    da, db_ = a.read(cfg.max_upload_bytes + 1), b.read(cfg.max_upload_bytes + 1)
    validate_image(da, a.filename, cfg.max_upload_bytes, cfg.max_pixels); validate_image(db_, b.filename, cfg.max_upload_bytes, cfg.max_pixels)
    res = cmp_mod.compare_bytes(da, db_); res["status"] = "ok"
    if request.args.get("diffmap") == "1" and res.get("same_dimensions"):
        res["diff_map_png_base64"] = base64.b64encode(cmp_mod.diff_map_png(da, db_)).decode()
        res["diff_map_caption"] = visual.CAPTIONS["diff"]
        res["ssim_map_png_base64"] = base64.b64encode(cmp_mod.ssim_map_png(da, db_)).decode()
        res["ssim_map_caption"] = "SSIM map (relative scale: darkest = the worst 0.5% of windows, so tiny changes are visible; read the SSIM numbers for absolute size). Dark = lower structural similarity. Shows where similarity drops, not why."
    return jsonify(res)

@bp.get("/models")
@login_required()
def models_list():
    rows = db().query(m.ModelVersion).all()
    return jsonify({"status": "ok", "models": [{"name": r.name, "algo": r.algo, "trained_at": r.trained_at, "seed": r.seed,
                                                "metrics": json.loads(r.metrics_json)} for r in rows]})

# ---------- M06 reports ----------
@bp.post("/reports")
@login_required()
def reports_create():
    b = request.get_json(silent=True) or {}
    case = own_case(int(b.get("case_id", 0) or 0))
    if not case: return err("not_found", "Case not found.", 404)
    run_ids = b.get("run_ids")
    content = rep_svc.collect(db(), case, run_ids)
    if not content["items"]:
        return err("no_analyses", "Run at least one analysis before generating a report.", 409)
    pdf = rep_svc.render_pdf(content, g.user.email)
    folder = os.path.join(current_app.config_obj.data_dir, "reports"); os.makedirs(folder, exist_ok=True)
    rep = m.Report(case_id=case.id, run_ids=json.dumps([i["run_id"] for i in content["items"]]), created_by=g.user.id,
                   pdf_sha256=hashlib.sha256(pdf).hexdigest(), content_sha256=rep_svc.content_hash(content),
                   model_version_id=None)
    db().add(rep); db().flush()
    rep.pdf_path = os.path.join(folder, f"report_{rep.id}.pdf")
    open(rep.pdf_path, "wb").write(pdf)
    audit(db(), g.user, "report.generate", case_id=case.id, report_id=rep.id, pdf_sha256=rep.pdf_sha256); db().commit()
    return jsonify({"status": "ok", "report_id": rep.id, "pdf_sha256": rep.pdf_sha256, "content_sha256": rep.content_sha256,
                    "download": f"/api/reports/{rep.id}/download"}), 201

@bp.get("/reports/<int:rid>/download")
@login_required()
def reports_download(rid):
    r = db().get(m.Report, rid)
    if not r or not own_case(r.case_id): return err("not_found", "Report not found.", 404)
    data = open(r.pdf_path, "rb").read()
    if hashlib.sha256(data).hexdigest() != r.pdf_sha256:
        return err("integrity_failure", "Report file no longer matches its stored hash.", 409)
    audit(db(), g.user, "report.download", case_id=r.case_id, report_id=r.id); db().commit()
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="report_{r.id}.pdf"',
                                                              "X-Report-SHA256": r.pdf_sha256})

# ---------- M07 benchmark dashboard (reads recorded runs only; never fabricates numbers) ----------
@bp.get("/benchmarks")
@login_required()
def benchmarks_list():
    rows = db().query(m.BenchmarkRun).order_by(m.BenchmarkRun.id.desc()).all()
    return jsonify({"status": "ok", "benchmarks": [{"id": r.id, "seed": r.seed, "started_at": r.started_at.isoformat() + "Z",
                                                    "result": json.loads(r.result_json)} for r in rows]})
