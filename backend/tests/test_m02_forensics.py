import io, os, subprocess, tempfile
import numpy as np
from PIL import Image
from sublumen.stego_core import studio
from sublumen.forensics_core import analyzer, compare, stats, visual
from conftest import make_png

def test_sha256_matches_sha256sum_on_20_files():
    with tempfile.TemporaryDirectory() as d:
        for i in range(20):
            data = make_png(32 + i, 32, seed=i)
            p = os.path.join(d, f"f{i}.png"); open(p, "wb").write(data)
            ref = subprocess.check_output(["sha256sum", p]).split()[0].decode()
            assert stats.sha256_hex(data) == ref

def test_clean_vs_stego_indicators():
    cover = make_png(256, 256, seed=2)
    clean = analyzer.analyze_bytes(cover)
    assert clean["verdict"] is None and clean["limitations"]
    ind = {i["name"]: i for i in clean["indicators"]}
    assert ind["chi_square"]["level"] == "low"
    full = studio.embed(cover, os.urandom(studio.capacity_bytes(cover)), "pw", with_ssim=False)["stego_png"]
    ind2 = {i["name"]: i for i in analyzer.analyze_bytes(full)["indicators"]}
    assert ind2["chi_square"]["level"] == "high"
    assert ind2["rs_estimate"]["level"] in ("high", "unknown")  # RS undefined for a few % of full embeds (measured)

def test_rs_tracks_embedding_rate_on_synthetic_cover():
    cover = make_png(256, 256, seed=2)
    cap = studio.capacity_bytes(cover)
    for rate in (0.25, 0.5, 1.0):
        img = studio.embed(cover, os.urandom(int(cap * rate)), "pw", with_ssim=False)["stego_png"]
        arr, _ = analyzer.load_array(img)
        est = np.nanmean([stats.rs_estimate(arr[..., c]) for c in range(3)])
        if np.isnan(est):
            assert rate == 1.0   # RS is undefined for ~3% of fully embedded images (measured 3/90); reported as 'unknown'
            continue
        assert abs(est - rate) < (0.2 if rate == 1.0 else 0.12), (rate, est)  # RS is noisier at full capacity

def test_compare_identical_and_different():
    a = make_png(64, 64, seed=1)
    r = compare.compare_bytes(a, a)
    assert r["identical_bytes"] and r["diff_pixels"] == 0
    s = studio.embed(a, b"hi", "pw")["stego_png"]
    r = compare.compare_bytes(a, s)
    assert not r["identical_bytes"] and r["diff_pixels"] > 0 and r["psnr_db"] > 40
    assert compare.diff_map_png(a, s)[:4] == b"\x89PNG"

def test_compare_different_dimensions_is_safe():
    r = compare.compare_bytes(make_png(32, 32), make_png(40, 32))
    assert r["same_dimensions"] is False

def test_bitplane_matches_numpy_on_5_images():
    for s in range(5):
        data = make_png(48, 48, seed=s)
        arr = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
        for plane in (0, 3, 7):
            png = visual.bitplane_png(data, plane, 1)
            got = np.array(Image.open(io.BytesIO(png))) // 255
            assert np.array_equal(got, (arr[..., 1] >> plane) & 1)

def test_heatmap_is_png_and_highlights_embedded_region():
    cover = make_png(128, 128, seed=4)
    part = studio.embed(cover, os.urandom(studio.capacity_bytes(cover) // 2), "pw", with_ssim=False)["stego_png"]
    s = visual.block_scores(part, 32)
    top, bottom = s[:2].mean(), s[2:].mean()
    assert top > bottom + 0.4  # embedded half (scan start) scores higher
    assert visual.heatmap_png(part)[:4] == b"\x89PNG"
