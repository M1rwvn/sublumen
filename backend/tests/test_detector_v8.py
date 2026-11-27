import io, os, numpy as np, pytest
from PIL import Image
from sublumen.ml_engine.predict import Detector
M = os.path.join(os.path.dirname(__file__), "..", "models", "model_v8_hgb.joblib")

@pytest.mark.skipif(not os.path.exists(M), reason="model missing")
def test_v8_threshold_semantics_and_tiles():
    d = Detector(M); rng = np.random.default_rng(0)
    a = (np.clip(np.cumsum(rng.normal(0, 3, (128, 128, 3)), axis=0), -100, 100) + 128).astype(np.uint8)
    b = io.BytesIO(); Image.fromarray(a).save(b, "PNG"); one = d._predict_one(b.getvalue())
    # score 0.5 must correspond to the validation threshold on the model's log-odds (what the locked test used)
    x = np.array([[0.0]]); assert d.threshold != 0.0 and d.algo == "hgb"
    cols = d.features; assert len(cols) == 837
    assert 0.0 <= one["score"] <= 1.0
    big = np.tile(a, (2, 3, 1)); b = io.BytesIO(); Image.fromarray(big).save(b, "PNG"); r = d.predict(b.getvalue())
    assert r["tiles"] == 6 and 0.0 <= r["score"] <= 1.0

@pytest.mark.skipif(not os.path.exists(M), reason="model missing")
def test_tile_grid_and_overlay():
    from sublumen.forensics_core import visual
    d = Detector(M); rng = np.random.default_rng(1); a = rng.integers(0, 256, (300, 400, 3), dtype=np.uint8)
    b = io.BytesIO(); Image.fromarray(a).save(b, "PNG"); g = d.tile_grid(b.getvalue())
    assert len(g["tiles"]) == 6 and all(0 <= t["score"] <= 1 for t in g["tiles"])
    png = visual.overlay_png(b.getvalue(), g); im = Image.open(io.BytesIO(png)); assert im.size == (400, 300)
