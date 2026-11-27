"""Hostile-upload checks: every file-taking endpoint must answer with a 4xx JSON error (never 500, never hang) for junk input."""
import io, os, struct, zlib
import numpy as np, pytest
from conftest import make_png
from test_api import ctx, png_file  # noqa: F401 (fixture)

def bomb_png(w=20000, h=20000):
    """A tiny PNG that declares a huge canvas (decompression-bomb shape)."""
    def chunk(t, d): c = struct.pack(">I", len(d)) + t + d; return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 64)) + chunk(b"IEND", b"")

rng = np.random.default_rng(5)
good = make_png(64, 64, seed=1)
CASES = {
    "empty": b"", "one_byte": b"\x00", "random_1k": rng.bytes(1024), "random_100k": rng.bytes(100_000),
    "png_magic_only": b"\x89PNG\r\n\x1a\n", "truncated_png": good[: len(good) // 2], "png_bad_crc": good[:40] + bytes([good[40] ^ 255]) + good[41:],
    "bomb_png": bomb_png(), "svg": b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", "html": b"<script>alert(1)</script>",
    "gif_header": b"GIF89a" + rng.bytes(50), "jpeg_magic_only": b"\xff\xd8\xff\xe0", "exif_junk": b"\xff\xd8\xff\xe1" + rng.bytes(200) + b"\xff\xd9",
    "path_in_bytes": b"../../etc/passwd",
}

def post_file(c, H, url, data, name="x.png", extra=None, field="file"):
    d = {field: (io.BytesIO(data), name)}; d.update(extra or {})
    return c.post(url, data=d, headers=H, content_type="multipart/form-data")

@pytest.mark.parametrize("name", list(CASES))
def test_embed_capacity_reject_junk(ctx, name):
    app, c, H, _ = ctx
    for url, extra in (("/api/stego/capacity", {}), ("/api/stego/embed?format=json", {"message": "hi", "password": "pw-long-enough"})):
        r = post_file(c, H, url, CASES[name], extra=extra)
        assert r.status_code in (400, 413, 415, 422), (url, name, r.status_code)
        assert r.is_json and r.get_json().get("status") == "error"

@pytest.mark.parametrize("name", list(CASES))
def test_extract_compare_reject_junk(ctx, name):
    app, c, H, _ = ctx
    r = post_file(c, H, "/api/stego/extract", CASES[name], extra={"password": "pw-long-enough"})
    assert r.status_code in (400, 413, 415, 422), (name, r.status_code)
    r = c.post("/api/compare", data={"a": (io.BytesIO(CASES[name]), "a.png"), "b": (io.BytesIO(good), "b.png")}, headers=H, content_type="multipart/form-data")
    assert r.status_code in (400, 413, 415, 422), ("compare", name, r.status_code)

@pytest.mark.parametrize("name", list(CASES))
def test_evidence_upload_never_500(ctx, name):
    app, c, H, _ = ctx
    cid = c.post("/api/cases", json={"title": "fuzz"}, headers=H).get_json()["id"]
    r = post_file(c, H, "/api/evidence", CASES[name], extra={"case_id": str(cid)})
    assert r.status_code < 500, (name, r.status_code)
    if r.status_code == 201 or r.status_code == 200:   # accepted as opaque evidence: analysis must still fail cleanly, never 500
        eid = r.get_json()["id"]
        a = c.post("/api/analyses", json={"evidence_id": eid}, headers=H)
        assert a.status_code < 500, (name, "analysis", a.status_code)

def test_oversize_upload_rejected(ctx):
    app, c, H, cfg = ctx
    r = post_file(c, H, "/api/stego/capacity", b"\x00" * (cfg.max_upload_bytes + 10))
    assert r.status_code in (400, 413) and r.get_json()["status"] == "error"

def test_hostile_filenames_and_ids(ctx):
    app, c, H, _ = ctx
    for nm in ("../../x.png", "a\x00b.png", "x" * 1000 + ".png", "<img src=x onerror=1>.png", "..\\..\\win.png"):
        r = post_file(c, H, "/api/stego/capacity", good, name=nm)
        assert r.status_code < 500, nm
    for u in ("/api/evidence/999999", "/api/analyses/999999", "/api/cases/999999", "/api/reports/999999/download", "/api/evidence/1/visual/../../etc"):
        assert c.get(u, headers=H).status_code in (404, 400)
