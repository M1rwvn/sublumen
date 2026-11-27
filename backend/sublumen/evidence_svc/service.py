"""M05 evidence manager. All writes to evidence go through here. Originals are read-only and hash-verified."""
import json, os, stat, uuid
from .. import models as m
from ..forensics_core import analyzer, stats
from ..security.validation import validate_image, ValidationError

class EvidenceError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message); self.code, self.message, self.status = code, message, status

def audit(db, user, action, case_id=None, evidence_id=None, **detail):
    detail.pop("password", None)
    db.add(m.AuditEvent(user_id=getattr(user, "id", user), case_id=case_id, evidence_id=evidence_id,
                        action=action, detail=json.dumps(detail, sort_keys=True)))

def create_case(db, user, title):
    c = m.Case(title=title, created_by=user.id, case_code="PENDING")
    db.add(c); db.flush()
    c.case_code = f"CASE-{m.now().year}-{c.id:03d}"
    audit(db, user, "case.create", case_id=c.id, title=title)
    db.commit(); return c

def add_evidence(db, user, case, data, filename, cfg):
    info = validate_image(data, filename, cfg.max_upload_bytes, cfg.max_pixels)
    digest = stats.sha256_hex(data)  # at intake, before any processing
    dup = db.query(m.Evidence).filter_by(case_id=case.id, sha256=digest).first()
    if dup:
        audit(db, user, "evidence.duplicate", case_id=case.id, evidence_id=dup.id, sha256=digest)
        db.commit(); return dup, True
    folder = os.path.join(cfg.data_dir, "evidence", str(case.id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, uuid.uuid4().hex + ".bin")
    with open(path, "xb") as f:
        f.write(data)
    os.chmod(path, stat.S_IRUSR)  # read-only original
    ev = m.Evidence(case_id=case.id, original_name=os.path.basename(filename or "")[:255], original_path=path,
                    sha256=digest, size_bytes=len(data), fmt=info["format"], width=info["width"], height=info["height"],
                    uploaded_by=user.id)
    db.add(ev); db.flush()
    audit(db, user, "evidence.upload", case_id=case.id, evidence_id=ev.id, sha256=digest, size=len(data))
    db.commit(); return ev, False

def read_verified(ev) -> bytes:
    with open(ev.original_path, "rb") as f:
        data = f.read()
    if stats.sha256_hex(data) != ev.sha256:
        raise EvidenceError("integrity_failure", "Stored evidence no longer matches its intake SHA-256.", 409)
    return data

def sync_models(db, models_dir):
    """Register every <name>_<algo>.joblib as its own selectable model (e.g. model_v2_svm_rbf)."""
    import glob
    for p in sorted(glob.glob(os.path.join(models_dir, "*.metrics.json"))):
        meta = json.load(open(p))
        for algo in meta["test"]:
            path = os.path.join(models_dir, f"{meta['name']}_{algo}.joblib")
            name = f"{meta['name']}_{algo}"
            if os.path.exists(path) and not db.query(m.ModelVersion).filter_by(name=name).first():
                test = {k: {x: y for x, y in v.items() if x != "errors"} for k, v in meta["test"].items() if k == algo}
                db.add(m.ModelVersion(name=name, algo=algo, trained_at=meta["trained_at"], seed=meta["seed"],
                                      metrics_json=json.dumps({"cv": {algo: meta["cv"][algo]}, "test": test, "limitations": meta["limitations"],
                                                               "cv_selected": meta["selected"]}), path=path))
    db.commit()

DEFAULT_MODEL = "model_v8_hgb"  # v8 beats v7 on the locked test (docs/locked_eval_v8.json); tile-scored. Revert: model_v7_svm_rbf

_detectors = {}
def get_detector(mv):
    from ..ml_engine.predict import Detector
    if mv.path not in _detectors:
        _detectors[mv.path] = Detector(mv.path)
    return _detectors[mv.path]

def run_analysis(db, user, ev, model_name=None, use_ml=True):
    data = read_verified(ev)
    res = analyzer.analyze_bytes(data)
    warnings = []
    if ev.fmt == "JPEG":
        warnings.append("JPEG is lossy: LSB-based indicators and the model are not meaningful for this format.")
    mv = None
    if use_ml:
        q = db.query(m.ModelVersion)
        mv = q.filter_by(name=model_name).first() if model_name else (q.filter_by(name=DEFAULT_MODEL).first() or q.order_by(m.ModelVersion.id.desc()).first())
        if model_name and not mv:
            raise EvidenceError("unknown_model", f"Model '{model_name}' is not registered.", 404)
    ml = None
    if mv:
        ml = get_detector(mv).predict(data)
    run = m.AnalysisRun(evidence_id=ev.id, model_version_id=mv.id if mv else None, created_by=user.id,
                        params=json.dumps({"model": mv.name if mv else None}))
    db.add(run); db.flush()
    for ind in res["indicators"]:
        if ind["level"] in ("low", "medium", "high", "unknown"):
            db.add(m.DetectionResult(run_id=run.id, method="stats", name=ind["name"], score=ind["value"], level=ind["level"]))
    if ml:
        db.add(m.DetectionResult(run_id=run.id, method="ml", name=ml["model"], score=ml["score"], level=ml["level"]))
    from ..forensics_core.provenance import check_c2pa
    prov = check_c2pa(data, ev.fmt)
    out = {"status": "ok", "run_id": run.id, "provenance": prov, "evidence_id": ev.id, "sha256": ev.sha256,
           "indicators": res["indicators"], "ml": ml, "model": mv.name if mv else None,
           "warnings": warnings, "limitations": res["limitations"] + (
               ["The model is trained on spatial-domain LSB embedding (replacement, keyed order, matching). Other hiding methods, other domains (e.g. JPEG DCT) and recompressed images may not be detected."] if ml else []),
           "verdict": None}
    run.result_json = json.dumps(out)
    audit(db, user, "analysis.run", case_id=ev.case_id, evidence_id=ev.id, run_id=run.id, model=out["model"])
    db.commit(); return out


def sync_benchmarks(db, docs_dir):
    """Load recorded benchmark result files (produced by `python -m sublumen.benchmark.run`)."""
    import glob
    for p in sorted(glob.glob(os.path.join(docs_dir, "benchmark_*.json"))):
        res = json.load(open(p))
        key = json.dumps({"f": os.path.basename(p), "seed": res["meta"]["seed"]})
        if not db.query(m.BenchmarkRun).filter_by(config_json=key).first():
            db.add(m.BenchmarkRun(config_json=key, result_json=json.dumps(res), seed=res["meta"]["seed"]))
    db.commit()
