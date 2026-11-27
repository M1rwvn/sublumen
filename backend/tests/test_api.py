import io, json, os, hashlib, stat
import numpy as np, pytest
from PIL import Image
from pypdf import PdfReader
from sublumen.api.app import create_app
from sublumen.config import Config
from conftest import make_png

@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    d = tmp_path_factory.mktemp("rt")
    cfg = Config(data_dir=str(d), db_uri=os.environ.get("SS_TEST_DB") or "sqlite:///" + str(d / "t.db"), secret="test-secret", max_upload_bytes=2_000_000,
                 max_pixels=1_000_000, rate_limit=10000, login_rate_limit=1000)
    os.environ["SS_ADMIN_EMAIL"], os.environ["SS_ADMIN_PASSWORD"] = "admin@x.org", "adminpass1"
    app = create_app(cfg)
    c = app.test_client()
    tok = c.post("/api/auth/login", json={"email": "admin@x.org", "password": "adminpass1"}).get_json()["token"]
    return app, c, {"Authorization": "Bearer " + tok}, cfg

def png_file(data=None, name="a.png"): return (io.BytesIO(data or make_png(96, 96, seed=2)), name)

def test_health_and_auth_required(ctx):
    app, c, H, _ = ctx
    assert c.get("/api/health").get_json()["status"] == "ok"
    assert c.get("/api/cases").status_code == 401
    assert c.post("/api/auth/login", json={"email": "admin@x.org", "password": "nope"}).status_code == 401

def test_roles_and_ownership(ctx):
    app, c, H, _ = ctx
    r = c.post("/api/users", json={"email": "an@x.org", "password": "analyst-pass", "role": "analyst"}, headers=H)
    assert r.status_code == 201
    t2 = c.post("/api/auth/login", json={"email": "an@x.org", "password": "analyst-pass"}).get_json()["token"]
    H2 = {"Authorization": "Bearer " + t2}
    assert c.post("/api/users", json={"email": "z@x.org", "password": "analyst-pass"}, headers=H2).status_code == 403
    cid = c.post("/api/cases", json={"title": "admin case"}, headers=H).get_json()["id"]
    assert c.get(f"/api/cases/{cid}", headers=H2).status_code == 404   # analyst cannot see admin's case
    assert c.get(f"/api/cases/{cid}", headers=H).status_code == 200

def test_full_flow_case_evidence_analysis_report(ctx):
    app, c, H, cfg = ctx
    case = c.post("/api/cases", json={"title": "Suspicious image"}, headers=H).get_json()
    assert case["case_code"].startswith("CASE-")
    data = make_png(128, 128, seed=9)
    r = c.post("/api/evidence", data={"case_id": case["id"], "file": png_file(data, "img_a.png")}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 201
    ev = r.get_json()
    assert ev["sha256"] == hashlib.sha256(data).hexdigest()
    stored = app.db.get(__import__("sublumen.models", fromlist=["x"]).Evidence, ev["id"]).original_path
    assert not os.access(stored, os.W_OK) or os.geteuid() == 0   # stored original is read-only
    assert stored.startswith(cfg.data_dir) and "img_a" not in stored  # random server-side name
    # duplicate -> same hash, user warned
    d = c.post("/api/evidence", data={"case_id": case["id"], "file": png_file(data, "copy.png")}, headers=H, content_type="multipart/form-data")
    assert d.status_code == 200 and d.get_json()["duplicate"] and d.get_json()["id"] == ev["id"]
    # analysis
    a = c.post("/api/analyses", json={"evidence_id": ev["id"]}, headers=H)
    assert a.status_code == 201
    body = a.get_json()
    assert body["provenance"]["present"] is False and body["verdict"] is None and body["limitations"] and body["model"] == "model_v8_hgb" and body["ml"]["algo"] == "hgb"
    assert {i["name"] for i in body["indicators"]} >= {"chi_square", "rs_estimate"}
    assert c.get(f"/api/analyses/{body['run_id']}", headers=H).get_json()["run_id"] == body["run_id"]
    # report
    rep = c.post("/api/reports", json={"case_id": case["id"]}, headers=H)
    assert rep.status_code == 201
    dl = c.get(rep.get_json()["download"], headers=H)
    assert dl.mimetype == "application/pdf" and dl.data[:4] == b"%PDF"
    assert hashlib.sha256(dl.data).hexdigest() == rep.get_json()["pdf_sha256"]
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(dl.data)).pages)
    for needle in (ev["sha256"][:32], body["model"], "Limitations", case["case_code"], "Indicators are statistical hints"):
        assert needle in text.replace("\n", ""), needle
    # reproducible: same case -> byte-identical PDF
    rep2 = c.post("/api/reports", json={"case_id": case["id"]}, headers=H).get_json()
    assert rep2["pdf_sha256"] == rep.get_json()["pdf_sha256"]
    # audit trail
    acts = [e["action"] for e in c.get(f"/api/cases/{case['id']}/audit", headers=H).get_json()["events"]]
    assert acts[:3] == ["case.create", "evidence.upload", "evidence.duplicate"] and "analysis.run" in acts and "report.generate" in acts
    # visual endpoints
    v = c.get(f"/api/evidence/{ev['id']}/visual/bitplane?plane=0", headers=H)
    assert v.data[:4] == b"\x89PNG" and "LSB" in v.headers["X-Visual-Caption"]
    assert c.get(f"/api/evidence/{ev['id']}/visual/heatmap", headers=H).headers["X-Visual-Caption"].count("NOT a location")
    assert c.get(f"/api/evidence/{ev['id']}/visual/bitplane?plane=9", headers=H).status_code == 400
    ov = c.get(f"/api/evidence/{ev['id']}/visual/overlay", headers=H)   # 96px image: nothing to tile, still a valid PNG with the honest caption
    assert ov.status_code == 200 and ov.data[:4] == b"\x89PNG" and "NOT where" in ov.headers["X-Visual-Caption"]

def test_original_never_modified_by_analysis(ctx):
    app, c, H, _ = ctx
    cid = c.post("/api/cases", json={"title": "integrity"}, headers=H).get_json()["id"]
    ev = c.post("/api/evidence", data={"case_id": cid, "file": png_file(make_png(64, 64, seed=21))}, headers=H, content_type="multipart/form-data").get_json()
    from sublumen import models as m
    path = app.db.get(m.Evidence, ev["id"]).original_path
    before = hashlib.sha256(open(path, "rb").read()).hexdigest()
    c.post("/api/analyses", json={"evidence_id": ev["id"]}, headers=H)
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == before == ev["sha256"]

def test_tampered_evidence_detected(ctx):
    app, c, H, _ = ctx
    from sublumen import models as m
    cid = c.post("/api/cases", json={"title": "tamper"}, headers=H).get_json()["id"]
    ev = c.post("/api/evidence", data={"case_id": cid, "file": png_file(make_png(64, 64, seed=33))}, headers=H, content_type="multipart/form-data").get_json()
    path = app.db.get(m.Evidence, ev["id"]).original_path
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR); open(path, "ab").write(b"x")
    r = c.post("/api/analyses", json={"evidence_id": ev["id"]}, headers=H)
    assert r.status_code == 409 and r.get_json()["code"] == "integrity_failure"

def test_upload_validation(ctx):
    app, c, H, cfg = ctx
    cid = c.post("/api/cases", json={"title": "val"}, headers=H).get_json()["id"]
    def up(data, name):
        return c.post("/api/evidence", data={"case_id": cid, "file": (io.BytesIO(data), name)}, headers=H, content_type="multipart/form-data")
    assert up(b"MZ\x90\x00 fake exe", "evil.png").get_json()["code"] == "unsupported_type"
    assert up(make_png(), "x.jpg").get_json()["code"] == "extension_mismatch"          # PNG content, .jpg name
    assert up(b"", "e.png").get_json()["code"] == "empty_file"
    assert up(make_png()[:60], "t.png").get_json()["code"] in ("corrupt_image",)
    big = up(b"\x89PNG\r\n\x1a\n" + os.urandom(2_100_000), "b.png")
    assert big.status_code == 413
    bomb = io.BytesIO(); Image.new("L", (2000, 2000)).save(bomb, "PNG")      # 4M pixels > 1M cap, tiny file
    r = up(bomb.getvalue(), "bomb.png")
    assert r.status_code == 413 and r.get_json()["code"] == "too_many_pixels"
    assert up(make_png(), "../../etc/passwd.png").status_code == 201                   # path in name is ignored

def test_stego_endpoints_and_password_hygiene(ctx):
    app, c, H, _ = ctx
    cover = make_png(96, 96, seed=4)
    r = c.post("/api/stego/embed?format=json", data={"file": png_file(cover), "message": "سر 123", "password": "S3cret-PW!"}, headers=H, content_type="multipart/form-data")
    j = r.get_json(); assert r.status_code == 200 and j["psnr_db"] > 45
    import base64
    stego = base64.b64decode(j["stego_png_base64"])
    ok = c.post("/api/stego/extract", data={"file": (io.BytesIO(stego), "s.png"), "password": "S3cret-PW!"}, headers=H, content_type="multipart/form-data")
    assert ok.get_json()["message"] == "سر 123"
    bad = c.post("/api/stego/extract", data={"file": (io.BytesIO(stego), "s.png"), "password": "wrong"}, headers=H, content_type="multipart/form-data")
    assert bad.status_code == 422 and bad.get_json()["code"] == "auth_failed" and "wrong" not in json.dumps(bad.get_json())
    assert "S3cret-PW!" not in json.dumps(j)
    # JPEG rejected for embedding
    jpg = make_png(64, 64, fmt="JPEG")
    assert c.post("/api/stego/embed", data={"file": (io.BytesIO(jpg), "a.jpg"), "message": "x", "password": "pw"}, headers=H, content_type="multipart/form-data").status_code == 415
    # too long message
    r = c.post("/api/stego/embed", data={"file": png_file(cover), "message": "A" * 100000, "password": "pw"}, headers=H, content_type="multipart/form-data")
    assert r.get_json()["code"] == "capacity"
    # password never lands in the audit log
    from sublumen import models as m
    assert not any("S3cret" in (a.detail or "") for a in app.db.query(m.AuditEvent))

def test_compare_endpoint(ctx):
    app, c, H, _ = ctx
    a = make_png(64, 64, seed=1)
    from sublumen.stego_core import studio
    s = studio.embed(a, b"hello", "pw")["stego_png"]
    r = c.post("/api/compare?diffmap=1", data={"a": (io.BytesIO(a), "a.png"), "b": (io.BytesIO(s), "b.png")}, headers=H, content_type="multipart/form-data").get_json()
    assert r["diff_pixels"] > 0 and r["diff_map_png_base64"] and not r["identical_bytes"]

def test_models_endpoint_and_unknown_model(ctx):
    app, c, H, _ = ctx
    ms = c.get("/api/models", headers=H).get_json()["models"]
    assert ms and {x["name"] for x in ms} >= {"model_v8_hgb"} and "test" in ms[0]["metrics"]
    cid = c.post("/api/cases", json={"title": "m"}, headers=H).get_json()["id"]
    ev = c.post("/api/evidence", data={"case_id": cid, "file": png_file(make_png(64, 64, seed=77))}, headers=H, content_type="multipart/form-data").get_json()
    assert c.post("/api/analyses", json={"evidence_id": ev["id"], "model": "nope"}, headers=H).status_code == 404
    r = c.post("/api/analyses", json={"evidence_id": ev["id"], "use_ml": False}, headers=H).get_json()
    assert r["ml"] is None
    rf = c.post("/api/analyses", json={"evidence_id": ev["id"], "model": "model_v8_hgb"}, headers=H).get_json()
    assert rf["model"] == "model_v8_hgb" and rf["ml"]["algo"] == "hgb"

def test_rate_limit_and_error_hygiene(ctx):
    app, c, H, cfg = ctx
    old = cfg.login_rate_limit; cfg.login_rate_limit = 3
    codes = [c.post("/api/auth/login", json={"email": "a@b.c", "password": "x"}).status_code for _ in range(6)]
    cfg.login_rate_limit = old
    assert 429 in codes
    r = c.get("/api/nope", headers=H)
    assert r.status_code == 404 and "Traceback" not in r.get_data(as_text=True)


def test_benchmarks_endpoint_serves_recorded_results(ctx):
    app, c, H, _ = ctx
    b = c.get("/api/benchmarks", headers=H).get_json()["benchmarks"]
    assert b and all(x["result"]["meta"]["seed"] == 2026 for x in b) and len(b) >= 2
    assert any("robustness_recall_at_50pct_replace" in x["result"] for x in b)
    v6 = [x for x in b if x["result"]["meta"].get("models")]
    assert v6 and "model_v6_svm_rbf" in v6[0]["result"]["detectors"] and "ci95" in v6[0]["result"]["detectors"]["model_v6_svm_rbf"]["fullsize:fpr_png_all"]


def test_embed_keyed_flag_roundtrip(ctx):
    app, c, H, _ = ctx
    import base64
    r = c.post("/api/stego/embed?format=json&keyed=1", data={"file": png_file(), "message": "keyed msg", "password": "pw-keyed-1"}, headers=H, content_type="multipart/form-data").get_json()
    st = base64.b64decode(r["stego_png_base64"])
    out = c.post("/api/stego/extract", data={"file": (io.BytesIO(st), "s.png"), "password": "pw-keyed-1"}, headers=H, content_type="multipart/form-data").get_json()
    assert out["message"] == "keyed msg"


def test_arabic_case_and_filename_in_pdf(ctx):
    app, c, H, cfg = ctx
    case = c.post("/api/cases", json={"title": "قضية صورة مشبوهة"}, headers=H).get_json()
    r = c.post("/api/evidence", data={"case_id": case["id"], "file": png_file(make_png(96, 96, seed=31), "صورة.png")}, headers=H, content_type="multipart/form-data")
    assert r.status_code == 201
    assert c.post("/api/analyses", json={"evidence_id": r.get_json()["id"]}, headers=H).status_code == 201
    rep = c.post("/api/reports", json={"case_id": case["id"]}, headers=H)
    pdf = c.get(rep.get_json()["download"], headers=H).data
    assert b"NotoSansArabic" in pdf  # font embedded
    # glyphs are real (not .notdef boxes): rendered text extracts as Arabic letters
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert any("\u0600" <= ch <= "\u06ff" or "\ufb50" <= ch <= "\ufeff" for ch in text)


def test_compare_ssim_dashboard(ctx):
    app, c, H, _ = ctx
    a = make_png(96, 96, seed=5)
    from sublumen.stego_core import studio
    b = studio.embed(a, b"hi there", "pw-ssim-test")["stego_png"]
    assert b
    r = c.post("/api/compare?diffmap=1", data={"a": png_file(a, "a.png"), "b": png_file(b, "b.png")}, headers=H, content_type="multipart/form-data").get_json()
    assert 0.9 < r["ssim"] < 1.0 and r["ssim_min"] <= r["ssim"] and r["max_abs_diff"] == 1 and r["mse"] > 0
    assert r["ssim_map_png_base64"] and r["psnr_db"] > 50
    same = c.post("/api/compare?diffmap=1", data={"a": png_file(a, "a.png"), "b": png_file(a, "a2.png")}, headers=H, content_type="multipart/form-data").get_json()
    assert same["ssim"] == 1.0 and same["diff_pixels"] == 0
